"""Delivery date as a predicted range plus a separate rule (pre-registered in docs/preregistration_v2.md, part d).

1. Prediction layer (predict.py): three candidates and a no-model baseline predict delivery-day quantiles, walk-forward.
2. Pick the candidate with the lowest CRPS on the tune block (Nov 2017 - Feb 2018), before the holdout is scored.
3. Score every candidate once on the locked holdout (Mar - Aug 2018): CRPS and calibration.
4. Decision layer (decide.py) on the picked candidate's holdout quantiles: sweep rule T (tau) and rule C (lambda); for each
   point, extra late-delivery bad reviews vs Olist's printed date and the days added. No point is picked.
Writes evidence/delivery_range_report.json and recommendation/delivery_range/tradeoff.png. About 20-30 minutes on 8 cores.
Needs: make build, and the packages in recommendation/delivery_range/requirements.txt.
Set DELIVERY_RANGE_CACHE=<folder> to keep the predictions between runs.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "delivery_date_model")); sys.path.insert(0, str(HERE.parent / "promise_backtest"))
import holdout as H  # noqa: E402
import model as M  # noqa: E402
from evaluate import bin_of, load_v2  # noqa: E402
import decide as D  # noqa: E402
import predict as P  # noqa: E402
import scores as S  # noqa: E402

DB = os.environ.get("OLIST_DB_PATH", str(ROOT / "olist.duckdb"))
CACHE = os.environ.get("DELIVERY_RANGE_CACHE")
LOCKED = {  # docs/preregistration_v2.md: judged order IDs, sorted, newline-joined, SHA-256
    "tune": (26121, "adc1fe4666756906ac51d45ac508bb3292001ee278f0f0193f0759b0b20d0648"),
    "holdout": (38511, "0d98b704ef12780ace89020dd89a1bb5be931ba07e2b601d5f0765ff3cad2440"),
}
N_BOOT = 2000
SEED = 20261123
GUARD_MEAN_DAYS, GUARD_MEDIAN_DAYS = 1.0, 1


def check_lock(rows: pd.DataFrame, block: str):
    ids = sorted(rows["order_id"])
    n, h = LOCKED[block]
    got = hashlib.sha256("\n".join(ids).encode()).hexdigest()
    assert len(ids) == n and got == h, f"{block} block is not the pre-registered one ({len(ids)} orders, {got})"


def predictions(df, name):
    months = M.TUNE_MONTHS + M.HOLDOUT_MONTHS
    f = Path(CACHE) / f"{name}.pkl" if CACHE else None
    if f and f.exists():
        return pd.read_pickle(f)
    t0 = time.time()
    rows, Q = P.route_history(df, months) if name == "route_history" else P.walk_forward(df, months, name)
    out = (rows[["order_id", "year_month", "actual_days", "olist_lead", "review_score", "route_p95_lead"]].reset_index(drop=True), Q, time.time() - t0)
    if f:
        f.parent.mkdir(parents=True, exist_ok=True); pd.to_pickle(out, f)
    return out


def prediction_scores(rows, Q):
    y = rows["actual_days"].to_numpy(dtype=float)
    c = S.crps_per_order(y, Q)
    return c, {"crps_days": float(c.mean()), **S.calibration(y, Q), "mean_width_p10_p90_days": float((Q[:, list(P.LEVELS).index(0.9)] - Q[:, list(P.LEVELS).index(0.1)]).mean())}


def effect_of(days_late: np.ndarray, v2: dict) -> np.ndarray:
    return np.array([0.0 if bin_of(int(d)) is None else v2[bin_of(int(d))]["effect"] for d in days_late])


def boot_counts(n, seed):
    rng = np.random.default_rng(seed)
    for _ in range(N_BOOT):
        yield np.bincount(rng.integers(0, n, n), minlength=n)


def score_points(rows: pd.DataFrame, leads: dict[str, np.ndarray]) -> dict:
    """For each named lead vector: extra bad reviews (reviewed orders, V2 effects) vs Olist, bootstrap, days added, coverage."""
    v2 = load_v2()
    actual = rows["actual_days"].to_numpy(dtype=int); olist = rows["olist_lead"].to_numpy(dtype=int)
    rev = rows["review_score"].notna().to_numpy(); march = (rows["year_month"] == "2018-03").to_numpy()
    e_ol = effect_of(actual - olist, v2)
    names = list(leads)
    E = np.column_stack([effect_of(actual - leads[k], v2) for k in names])
    delta = (e_ol[:, None] - E)[rev]                      # per reviewed order: how many fewer extra bad reviews than Olist
    boots = np.array([c @ delta for c in boot_counts(int(rev.sum()), SEED)])
    out = {"olist": {"extra_v2": float(e_ol[rev].sum()), "march_extra_v2": float(e_ol[rev & march].sum()),
                     "on_time_pct": 100 * float((actual <= olist).mean()), "mean_lead": float(olist.mean()), "median_lead": float(np.median(olist))}}
    for j, k in enumerate(names):
        L = leads[k]
        red = float(delta[:, j].sum())
        mean_add = float((L - olist).mean()); med = float(np.median(L))
        out[k] = {"extra_v2": float(E[rev, j].sum()), "reduction_vs_olist": red,
                  "reduction_p025": float(np.quantile(boots[:, j], 0.025)), "reduction_p975": float(np.quantile(boots[:, j], 0.975)),
                  "mean_days_added_vs_olist": mean_add, "median_lead": med, "on_time_pct": 100 * float((actual <= L).mean()),
                  "march_extra_v2": float(E[rev & march, j].sum()),
                  "within_guardrail": bool(mean_add <= GUARD_MEAN_DAYS and med <= out["olist"]["median_lead"] + GUARD_MEDIAN_DAYS)}
    return out


def plot(points: dict, path: Path, title: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    for prefix, lab, mk in (("T_", "Rule T: print the tau quantile", "o-"), ("C_", "Rule C: per-order cost rule", "s-")):
        ks = [k for k in points if k.startswith(prefix)]
        xs = [points[k]["mean_days_added_vs_olist"] for k in ks]; ys = [points[k]["extra_v2"] for k in ks]
        o = np.argsort(xs); ax.plot(np.array(xs)[o], np.array(ys)[o], mk, ms=4, label=lab)
        if prefix == "T_":
            for k, x, y in zip(ks, xs, ys):
                ax.annotate(k[2:], (x, y), textcoords="offset points", xytext=(4, 4), fontsize=7, color="0.35")
    ax.plot([0], [points["olist"]["extra_v2"]], "k*", ms=12, label="Olist's printed date")
    if "route_p95" in points:
        ax.plot([points["route_p95"]["mean_days_added_vs_olist"]], [points["route_p95"]["extra_v2"]], "D", color="tab:red", label="Route p95 date")
    ax.axvline(GUARD_MEAN_DAYS, color="tab:orange", ls="--", lw=1.2, label="1-day guardrail (mean)")
    off = [k for k in points if k[:2] in ("T_", "C_") and (abs(points[k]["mean_days_added_vs_olist"]) > 12 or points[k]["extra_v2"] > 4600)]
    ax.set_xlim(-12, 12); ax.set_ylim(0, 4600)
    if off:
        ax.text(0.01, 0.01, "Off the chart (too few days, far more bad reviews): " + ", ".join(off), transform=ax.transAxes, fontsize=7, color="0.35")
    ax.set_xlabel("Mean days added to the printed date vs Olist's"); ax.set_ylabel("Extra late-delivery bad reviews (holdout, reviewed orders)")
    ax.set_title(title, fontsize=10); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


def main():
    t0 = time.time()
    con = duckdb.connect(DB, read_only=True)
    df = H.build_frame(con); con.close()
    out = {"split": {"train_from": str(M.TRAIN_FROM.date()), "tune_months": M.TUNE_MONTHS, "holdout_months": M.HOLDOUT_MONTHS,
                     "label_lag_days": P.LABEL_LAG_DAYS, "note": "holdout months were scored by earlier models in this repo: locked, not fresh"},
           "levels": [float(x) for x in P.LEVELS]}
    names = list(P.CANDIDATES) + ["route_history"]
    preds = {n: predictions(df, n) for n in names}
    rows0 = preds["route_history"][0]
    for n in names:
        assert preds[n][0]["order_id"].tolist() == rows0["order_id"].tolist(), n
    tune = (rows0["year_month"].isin(M.TUNE_MONTHS)).to_numpy(); hold = ~tune
    check_lock(rows0[tune], "tune"); check_lock(rows0[hold], "holdout")
    # 2. selection on the tune block only
    out["tune"] = {n: prediction_scores(rows0[tune], preds[n][1][tune])[1] for n in names}
    selected = min(P.CANDIDATES, key=lambda n: out["tune"][n]["crps_days"])
    out["selected_on_tune"] = selected
    # 3. holdout, scored once
    hold_c = {}
    out["holdout"] = {}
    for n in names:
        c, s = prediction_scores(rows0[hold], preds[n][1][hold]); hold_c[n] = c; out["holdout"][n] = s
        out["holdout"][n]["fit_minutes"] = preds[n][2] / 60
    pb = S.paired_boot_mean(hold_c["route_history"] - hold_c[selected], N_BOOT, SEED)
    cal = out["holdout"][selected]["max_gap_0.5_to_0.95_pp"]
    out["pass_rules"] = [
        {"id": "D-1 selected model's holdout CRPS below the route-history baseline, paired bootstrap 2.5th percentile above 0",
         "pass": bool(pb["point"] > 0 and pb["p025"] > 0), "observed": pb},
        {"id": "D-2 selected model's holdout calibration error at most 3 points", "pass": bool(cal <= 3.0), "observed": cal}]
    # 4. decision layer on the selected candidate's holdout quantiles
    rows = rows0[hold].reset_index(drop=True); Q = preds[selected][1][hold]
    F = D.cdf_on_days(Q, D.MAX_LEAD + 60)
    leads = {f"T_{t:.2f}": D.rule_t(Q, t) for t in D.TAUS}
    leads.update({f"C_{lam:g}": D.rule_c(Q, lam, F) for lam in D.LAMBDAS})
    has_route = rows["route_p95_lead"].notna().to_numpy()
    pts = score_points(rows, leads)
    rp = score_points(rows[has_route].reset_index(drop=True), {"route_p95": rows.loc[has_route, "route_p95_lead"].astype(int).to_numpy()})
    pts["route_p95"] = rp["route_p95"]; pts["route_p95"]["note"] = f"scored on the {int(has_route.sum())} holdout orders with a route p95 date; Olist on the same orders: {rp['olist']['extra_v2']:.1f}"
    out["decision_points"] = pts
    ok = [k for k, v in pts.items() if k[:2] in ("T_", "C_") and v["within_guardrail"] and v["reduction_vs_olist"] > 0 and v["reduction_p025"] > 0]
    out["pass_rules"].append({"id": "D-3 (finding, not a launch decision) a point inside the 1-day guardrail cuts extra bad reviews vs Olist, bootstrap 2.5th percentile above 0",
                              "pass": bool(ok), "observed": {"points": ok}})
    out["minutes"] = (time.time() - t0) / 60
    json.dump(out, open(ROOT / "evidence" / "delivery_range_report.json", "w"), indent=1, default=float)
    plot(pts, HERE / "tradeoff.png", f"Holdout Mar-Aug 2018, decision rules on the {selected} range (no point picked)")
    for r in out["pass_rules"]:
        print(("PASS " if r["pass"] else "FAIL ") + r["id"], json.dumps(r["observed"], default=float))
    print("selected on tune:", selected, {n: round(out["tune"][n]["crps_days"], 4) for n in names})


if __name__ == "__main__":
    main()
