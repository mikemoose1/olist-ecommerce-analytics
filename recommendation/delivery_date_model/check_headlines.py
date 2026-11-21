#!/usr/bin/env python3
"""Rebuild the delivery-date model's holdout results from the warehouse and fail if they drift.

Usage: python recommendation/delivery_date_model/check_headlines.py [--write]
Needs `make build`. OLIST_DB_PATH picks the warehouse file (default: olist.duckdb in the repo root).
--write records a new expected.json; it is for a deliberate, reviewed change only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

EXPECTED = HERE / "expected.json"
README = HERE / "README.md"
TUNE = HERE / "tune_results.json"
ABS_TOL = 1e-6
BOOT_TOL = {"reduction": 2.0, "percent": 0.2}


def db_path() -> Path:
    path = Path(os.environ.get("OLIST_DB_PATH", str(ROOT / "olist.duckdb")))
    if not path.exists():
        sys.exit(f"warehouse not found: {path} (run make build, or set OLIST_DB_PATH)")
    return path


def flatten(prefix, obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten(f"{prefix}.{k}" if prefix else k, v, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            flatten(f"{prefix}.{i}", v, out)
    else:
        out[prefix] = obj


def near(a, b, tol=ABS_TOL) -> bool:
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


def compare(got: dict, expected: dict) -> list[str]:
    g, e = {}, {}
    flatten("", got, g)
    flatten("", expected, e)
    bad = [f"unexpected new key {k}" for k in g if k not in e]
    for key, ev in e.items():
        if key not in g:
            bad.append(f"missing {key}")
            continue
        gv = g[key]
        is_boot = ".bootstrap_vs_olist." in key or key.startswith("paired_model_vs_route_p95.")
        if isinstance(ev, bool) or isinstance(gv, bool) or isinstance(ev, str) or ev is None:
            if gv != ev:
                bad.append(f"{key}: got {gv!r}, expected {ev!r}")
        elif is_boot and ("reduction_p" in key or "percent_p" in key):
            tol = BOOT_TOL["reduction"] if "reduction_p" in key else BOOT_TOL["percent"]
            if abs(float(gv) - float(ev)) > tol:
                bad.append(f"{key}: got {gv!r}, expected {ev!r} (tol {tol})")
        elif not near(gv, ev):
            bad.append(f"{key}: got {gv!r}, expected {ev!r}")
    return bad


def display(r: dict, s: dict, tune: dict) -> dict:
    m, rt, ol = r["model"], r["route_p95"], r["olist"]
    mar = r["months"]["2018-03"]
    pb = r["paired_model_vs_route_p95"]
    st = m["four_states"]
    info = next(x for x in tune["results"] if x["cfg"] == r["cfg"])
    return {
        "n_configs": tune["n_configs"],
        "tune_info_reduction": round(info["summary"]["reduction_v2"]),
        "tune_info_extra_days_1dp": round(info["summary"]["mean_extra_days_vs_olist"], 1),
        "tune_info_nov_model": round(info["summary"]["spikes"]["2017-11"]["model"]),
        "tune_info_nov_olist": round(info["summary"]["spikes"]["2017-11"]["olist"]),
        "tune_route_reduction": round(tune["route_p95_tune"]["v2"]["reduction"]),
        "tune_olist_mean_lead_1dp": round(tune["olist_tune"]["mean_lead"], 1),
        "n_scored": r["n_scored"],
        "n_reviewed": r["n_reviewed"],
        "olist_extra": round(ol["extra_v2"]),
        "olist_mean_lead_1dp": round(ol["mean_lead"], 1),
        "olist_median_lead": round(ol["median_lead"]),
        "olist_coverage_1dp": round(ol["coverage_pct"], 1),
        "model_extra": round(m["v2"]["extra_policy"]),
        "model_reduction": round(m["v2"]["reduction"]),
        "model_reduction_pct": round(100 * m["v2"]["reduction"] / ol["extra_v2"]),
        "model_boot_lo": round(m["bootstrap_vs_olist"]["reduction_p025"]),
        "model_boot_hi": round(m["bootstrap_vs_olist"]["reduction_p975"]),
        "model_per_1000": round(1000 * m["v2"]["reduction"] / r["n_reviewed"]),
        "model_coverage_1dp": round(m["coverage_pct"], 1),
        "model_extra_days_1dp": round(m["mean_extra_days_vs_olist"], 1),
        "model_median_lead": round(m["median_lead"]),
        "model_newly_on_time_n": st["newly_on_time"]["n"],
        "model_newly_on_time_avoided": round(-st["newly_on_time"]["sum_delta"]),
        "model_newly_late_n": st["newly_late"]["n"],
        "model_newly_late_added": round(st["newly_late"]["sum_delta"]),
        "model_still_late_reduction": round(-st["still_late"]["sum_delta"]),
        "model_v4_reduction": round(m["v4"]["reduction"]),
        "route_extra": round(rt["v2"]["extra_policy"]),
        "route_reduction": round(rt["v2"]["reduction"]),
        "route_boot_lo": round(rt["bootstrap_vs_olist"]["reduction_p025"]),
        "route_boot_hi": round(rt["bootstrap_vs_olist"]["reduction_p975"]),
        "route_extra_days_1dp": round(rt["mean_extra_days_vs_olist"], 1),
        "route_coverage_1dp": round(rt["coverage_pct"], 1),
        "model_vs_route": round(pb["point"]),
        "model_vs_route_lo": round(pb["reduction_p025"]),
        "model_vs_route_hi": round(pb["reduction_p975"]),
        "march_olist": round(mar["olist_extra_v2"]),
        "march_model": round(mar["model_extra_v2"]),
        "march_route": round(mar["route_p95_extra_v2"]),
        "march_olist_coverage_1dp": round(mar["olist_coverage_pct"], 1),
        "march_model_coverage_1dp": round(mar["model_coverage_pct"], 1),
        "later_than_olist_pct": round(r["risk_flag"]["flagged_share_pct"]),
        "coverage_target_pct": r["coverage_target_pct"],
        "top_features": [x["feature"] for x in r["importance_march2018"][:5]],
        "sellers_flagged_first": s["flagged_sellers_first_month"],
        "sellers_flagged_last": s["flagged_sellers_last_month"],
        "sellers_handoff_flagged_1dp": round(s["handoff_late_flagged_pct"], 1),
        "sellers_handoff_other_1dp": round(s["handoff_late_other_pct"], 1),
        "sellers_late_flagged_1dp": round(s["late_rate_flagged_pct"], 1),
        "sellers_late_other_1dp": round(s["late_rate_other_pct"], 1),
        "sellers_late_share_1dp": round(s["flagged_late_share_pct"], 1),
        "sellers_order_share_1dp": round(s["flagged_order_share_pct"], 1),
    }


def tradeoff_problems(tune: dict, d: dict) -> list[str]:
    """What the trade-off chart and its caption say about the tuning grid: the best setting within the 1-day cap is the
    labelled one, and every setting that prevented more ran over the cap."""
    rs = [x["summary"] for x in tune["results"]]
    inside = [s for s in rs if s["mean_extra_days_vs_olist"] <= 1.0]
    bad = []
    if round(max(s["reduction_v2"] for s in inside)) != d["tune_info_reduction"]:
        bad.append("trade-off: the best setting within the cap is not the labelled one")
    if any(s["mean_extra_days_vs_olist"] <= 1.0 for s in rs if s["reduction_v2"] > max(x["reduction_v2"] for x in inside)):
        bad.append("trade-off: a setting that prevented more stayed within the cap")
    if len(rs) != d["n_configs"]:
        bad.append("trade-off: tune_results.json does not hold every setting")
    return bad


def identity_problems(payload: dict) -> list[str]:
    """Four-state parts add up to the net, unrounded and rounded; decision fields follow the bar."""
    d = payload["display"]
    st = payload["holdout"]["model"]["four_states"]
    red = payload["holdout"]["model"]["v2"]["reduction"]
    parts = -st["newly_on_time"]["sum_delta"] - st["newly_late"]["sum_delta"] - st["still_late"]["sum_delta"]
    bad = []
    if abs(parts - red) > 1e-6:
        bad.append(f"four-state identity failed: {parts} vs {red}")
    if d["model_newly_on_time_avoided"] - d["model_newly_late_added"] + d["model_still_late_reduction"] != d["model_reduction"]:
        bad.append("rounded four-state parts do not equal the rounded net")
    if d["olist_extra"] - d["model_extra"] != d["model_reduction"]:
        bad.append("rounded Olist minus model extra does not equal the rounded reduction")
    dec = payload["holdout"]["decision"]
    if dec["model_adopted"] and not (dec["model_passed_tuning"] and dec["model_passes_holdout"]):
        bad.append("model adopted without passing tuning and holdout")
    if dec["model_passes_holdout"] != payload["holdout"]["bar"]["model"]["overall_pass"]:
        bad.append("decision disagrees with the bar")
    return bad


def readme_fragments(d: dict) -> list[str]:
    return [
        f"extra late-delivery bad reviews fall from about {d['olist_extra']:,} under Olist's printed promise to about {d['model_extra']}, a cut of about {d['model_reduction']} ({d['model_reduction_pct']}%; bootstrap range {d['model_boot_lo']} to {d['model_boot_hi']})",
        f"about {d['model_vs_route']} fewer than the route p95 date (paired range {d['model_vs_route_lo']} to {d['model_vs_route_hi']})",
        f"March 2018: {d['march_olist']} under Olist, {d['march_model']} under the model, {d['march_route']} under route p95",
        f"{d['model_coverage_1dp']}% of orders arrive by the model's date, against {d['olist_coverage_1dp']}% for Olist's",
        f"on average {d['model_extra_days_1dp']} days longer than Olist's (median {d['model_median_lead']} days against {d['olist_median_lead']})",
        f"None of the {d['n_configs']} settings passed tuning",
        "**FAIL**",
        f"On {d['n_reviewed']:,} reviewed orders bought March to August 2018",
        f"about {d['model_newly_on_time_avoided']} avoided on {d['model_newly_on_time_n']:,} orders that turn on time, minus about {d['model_newly_late_added']} added on {d['model_newly_late_n']} orders that turn late, plus about {d['model_still_late_reduction']} fewer on orders late either way",
        f"which cut about {d['route_reduction']} (range {d['route_boot_lo']} to {d['route_boot_hi']})",
        f"The coverage target set on the tune block was {d['coverage_target_pct']}%",
        f"The route p95 date was {d['route_extra_days_1dp']} days longer. The model's date is later than Olist's on {d['later_than_olist_pct']}% of orders",
        f"an average of {d['olist_mean_lead_1dp']} days in the holdout against {d['tune_olist_mean_lead_1dp']} in the tune block",
        f"cut {d['tune_info_reduction']} bad reviews over the tune block at {d['tune_info_extra_days_1dp']} days longer, but had {d['tune_info_nov_model']} extra bad reviews in November 2017 against Olist's {d['tune_info_nov_olist']}",
        f"with {-d['tune_route_reduction']} more extra bad reviews than Olist" if d["tune_route_reduction"] < 0 else "TUNE_ROUTE_SIGN",
        f"were {top_features_text(d['top_features'])}",
        f"{d['sellers_flagged_first']} sellers in March 2018, {d['sellers_flagged_last']} by August",
        f"handed parcels over late more often ({d['sellers_handoff_flagged_1dp']}% against {d['sellers_handoff_other_1dp']}%)",
        f"did not arrive late more often ({d['sellers_late_flagged_1dp']}% against {d['sellers_late_other_1dp']}%)" if d["sellers_late_flagged_1dp"] <= d["sellers_late_other_1dp"] else "SELLER_DIRECTION",
        f"They carried {d['sellers_late_share_1dp']}% of late orders on {d['sellers_order_share_1dp']}% of orders",
    ]


FEATURE_WORDS = {
    "customer_state_code": "the customer's state", "seller_state_code": "the seller's state", "distance_km": "the distance",
    "olist_lead": "Olist's printed lead", "route_p90": "the route's 90th-percentile time", "route_p95": "the route's 95th-percentile time",
    "route_p50": "the route's median time", "seller_handoff_days": "the seller's past handoff speed", "freight": "the freight",
    "weight_g": "the parcel weight", "seller_mean_days": "the seller's past delivery time", "global_buys_7d": "platform orders in the last 7 days",
    "global_open": "platform orders in transit", "cstate_p95": "the customer state's 95th-percentile time",
}


def top_features_text(names: list[str]) -> str:
    words = [FEATURE_WORDS.get(n, n) for n in names]
    return ", ".join(words[:-1]) + " and " + words[-1]


def readme_drift(d: dict, text: str) -> list[str]:
    return [f"missing fragment: {f!r}" for f in readme_fragments(d) if f not in text]


def build_payload(con) -> dict:
    import holdout
    import seller_flags
    tune = json.loads(TUNE.read_text())
    cfg, cov = holdout.info_cfg_from_tune(tune)
    if cfg != holdout.INFO_CFG or cov != holdout.COVERAGE_TARGET_PCT:
        sys.exit(f"tune_results.json no longer picks the setting locked in PASS_BAR.md: {cfg} / {cov}")
    if tune["pick"] is not None:
        sys.exit("tune_results.json now has an eligible setting; PASS_BAR.md says none passed tuning")
    df = holdout.build_frame(con)
    r = holdout.run(con, df=df)
    s = seller_flags.run(con)
    return {"holdout": r, "seller_flags": s, "display": display(r, s, tune), "_tune_recheck": tune_recheck(df, tune)}


def tune_recheck(df, tune: dict) -> list[str]:
    """Re-run the tuning block for the setting the trade-off chart labels and for the route p95 date, and fail if
    tune_results.json (which the chart plots) no longer matches. The full 56-setting grid is rerun by tune.py."""
    import model as M
    import tune as T
    import holdout
    rows, _ = M.walk_forward(df, M.TUNE_MONTHS, holdout.INFO_CFG)
    rows = rows[rows["route_p95_lead"].notna()].copy()
    rows["route_p95_lead"] = rows["route_p95_lead"].astype(int)
    res = M.score_block(rows, {"model": "model_lead", "route_p95": "route_p95_lead"})
    got = T.summarize(res)
    want = next(x["summary"] for x in tune["results"] if x["cfg"] == holdout.INFO_CFG)
    bad = []
    for k in ("reduction_v2", "mean_extra_days_vs_olist", "median_lead", "olist_median_lead", "coverage_pct"):
        if not near(got[k], want[k]):
            bad.append(f"tune_results.json {k} for the labelled setting: file {want[k]!r}, rerun {got[k]!r}")
    for mo, v in want["spikes"].items():
        for side in ("model", "olist"):
            if not near(got["spikes"][mo][side], v[side]):
                bad.append(f"tune_results.json spike {mo} {side}: file {v[side]!r}, rerun {got['spikes'][mo][side]!r}")
    rt = tune["route_p95_tune"]
    for got_v, want_v, name in ((res["route_p95"]["v2"]["reduction"], rt["v2"]["reduction"], "route p95 reduction"),
                                (res["route_p95"]["mean_extra_days_vs_olist"], rt["mean_extra_days_vs_olist"], "route p95 extra days"),
                                (res["olist"]["mean_lead"], tune["olist_tune"]["mean_lead"], "Olist mean lead")):
        if not near(got_v, want_v):
            bad.append(f"tune_results.json {name}: file {want_v!r}, rerun {got_v!r}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    import duckdb
    con = duckdb.connect(str(db_path()), read_only=True)
    got = json.loads(json.dumps(build_payload(con), default=float))
    recheck = got.pop("_tune_recheck")
    if args.write:
        EXPECTED.write_text(json.dumps(got, indent=2) + "\n")
        print(f"wrote {EXPECTED.name}")
    expected = json.loads(EXPECTED.read_text())
    bad = compare(got, expected) + identity_problems(got) + readme_drift(got["display"], README.read_text()) + recheck + tradeoff_problems(json.loads(TUNE.read_text()), got["display"])
    for line in bad:
        print("FAIL ", line)
    d = got["display"]
    print(f"{'FAIL' if bad else 'PASS'}  delivery-date model: holdout {d['n_reviewed']:,} reviewed orders, model cut {d['model_reduction']} "
          f"vs Olist, {d['model_extra_days_1dp']} days longer; bar {'PASS' if got['holdout']['bar']['model']['overall_pass'] else 'FAIL'}; {len(bad)} problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
