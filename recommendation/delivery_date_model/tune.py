#!/usr/bin/env python3
"""Pick the quantile and tree settings on the tune block (Nov 2017 - Feb 2018) only.

Writes tune_results.json. The holdout is never touched here.
Selection rule: keep settings whose mean extra promise vs Olist is at most +1.0 day (and median
lead at most Olist's median + 1) and whose spike months (Nov 2017, Feb 2018) are no worse than Olist;
pick the largest net reduction in extra bad reviews vs Olist; ties within 1 review go to the
smaller quantile, then fewer iterations. Holdout coverage target = the pick's tune coverage, floored.
"""
from __future__ import annotations

import itertools
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
import duckdb  # noqa: E402

import features as F  # noqa: E402
import model as M  # noqa: E402
from baselines import route_p95_leads  # noqa: E402

QUANTILES = [0.90, 0.93, 0.95, 0.96, 0.97, 0.98, 0.99]
LAGS = [30, 45]  # days between a training order's purchase and the retrain date
TREES = [  # (learning_rate, max_iter, max_leaf_nodes, min_samples_leaf)
    (0.05, 300, 15, 200), (0.05, 300, 31, 200), (0.10, 300, 15, 200), (0.10, 300, 31, 200),
]


def grid():
    for q, lag, (lr, it, leaves, msl) in itertools.product(QUANTILES, LAGS, TREES):
        yield {"quantile": q, "label_lag_days": lag, "learning_rate": lr, "max_iter": it,
               "max_leaf_nodes": leaves, "min_samples_leaf": msl}


def summarize(res: dict) -> dict:
    m = res["model"]
    spikes = {mo: {"model": v["model_extra_v2"], "olist": v["olist_extra_v2"]}
              for mo, v in res["months"].items() if mo in M.SPIKE_MONTHS}
    return {
        "reduction_v2": m["v2"]["reduction"],
        "mean_extra_days_vs_olist": m["mean_extra_days_vs_olist"],
        "median_lead": m["median_lead"],
        "olist_median_lead": res["olist"]["median_lead"],
        "coverage_pct": m["coverage_pct"],
        "spikes": spikes,
        "eligible": (m["mean_extra_days_vs_olist"] <= 1.0
                     and m["median_lead"] <= res["olist"]["median_lead"] + 1
                     and all(s["model"] <= s["olist"] for s in spikes.values())),
    }


def pick(results: list[dict]):
    ok = [r for r in results if r["summary"]["eligible"]]
    if not ok:
        return None
    best = max(r["summary"]["reduction_v2"] for r in ok)
    tied = [r for r in ok if r["summary"]["reduction_v2"] >= best - 1.0]
    tied.sort(key=lambda r: (r["cfg"]["quantile"], r["cfg"]["max_iter"], -r["summary"]["reduction_v2"]))
    return tied[0]


def main():
    db = os.environ.get("OLIST_DB_PATH", str(ROOT / "olist.duckdb"))
    con = duckdb.connect(db, read_only=True)
    df = F.build(con)
    df["route_p95_lead"] = df["order_id"].map(route_p95_leads(con))
    results = []
    for cfg in grid():
        rows, _ = M.walk_forward(df, M.TUNE_MONTHS, cfg)
        rows = rows[rows["route_p95_lead"].notna()]
        rows["route_p95_lead"] = rows["route_p95_lead"].astype(int)
        res = M.score_block(rows, {"model": "model_lead", "route_p95": "route_p95_lead"})
        s = summarize(res)
        results.append({"cfg": cfg, "summary": s})
        print(json.dumps(cfg), f"red={s['reduction_v2']:.1f} extra={s['mean_extra_days_vs_olist']:.2f} cov={s['coverage_pct']:.2f} eligible={s['eligible']}", flush=True)
    chosen = pick(results)
    base = M.score_block(rows, {"route_p95": "route_p95_lead"})
    out = {
        "tune_months": M.TUNE_MONTHS,
        "n_configs": len(results),
        "olist_tune": base["olist"],
        "route_p95_tune": M.strip({k: base["route_p95"][k] for k in ("v2", "coverage_pct", "mean_extra_days_vs_olist", "median_lead")}),
        "results": results,
        "pick": chosen["cfg"] if chosen else None,
        "pick_summary": chosen["summary"] if chosen else None,
        "coverage_target_pct": math.floor(chosen["summary"]["coverage_pct"]) if chosen else None,
    }
    (HERE / "tune_results.json").write_text(json.dumps(out, indent=2) + "\n")
    print("pick", out["pick"], out["pick_summary"], "coverage target", out["coverage_target_pct"])


if __name__ == "__main__":
    main()
