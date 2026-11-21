"""Score the holdout (purchases March - August 2018) once, against the locked bar in PASS_BAR.md."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import features as F  # noqa: E402
import model as M  # noqa: E402
from baselines import route_p95_leads  # noqa: E402

# The setting scored for information (PASS_BAR.md): the largest tune-block reduction among settings
# that met the length cap. check_headlines.py confirms it against tune_results.json.
INFO_CFG = {"quantile": 0.97, "label_lag_days": 45, "learning_rate": 0.05, "max_iter": 300,
            "max_leaf_nodes": 15, "min_samples_leaf": 200}
COVERAGE_TARGET_PCT = 90


def info_cfg_from_tune(tune: dict) -> tuple[dict, int]:
    ok = [r for r in tune["results"]
          if r["summary"]["mean_extra_days_vs_olist"] <= 1.0
          and r["summary"]["median_lead"] <= r["summary"]["olist_median_lead"] + 1]
    best = max(ok, key=lambda r: r["summary"]["reduction_v2"])
    return best["cfg"], int(np.floor(best["summary"]["coverage_pct"]))


def apply_bar(res: dict, name: str, march: dict, paired: dict | None) -> dict:
    p = res[name]
    ol = res["olist"]
    boot = p["bootstrap_vs_olist"]
    checks = [
        {"id": 1, "name": "Net reduction vs Olist above 0, bootstrap 2.5th percentile above 0",
         "pass": bool(p["v2"]["reduction"] > 0 and boot["reduction_p025"] > 0),
         "observed": [p["v2"]["reduction"], boot["reduction_p025"], boot["reduction_p975"]]},
        {"id": 2, "name": "Mean promise at most 1.0 day longer than Olist, median at most 1 day longer",
         "pass": bool(p["mean_extra_days_vs_olist"] <= 1.0 and p["median_lead"] <= ol["median_lead"] + 1),
         "observed": [p["mean_extra_days_vs_olist"], p["median_lead"], ol["median_lead"]]},
        {"id": 3, "name": "March 2018 extra not higher than Olist",
         "pass": bool(march[f"{name}_extra_v2"] <= march["olist_extra_v2"]),
         "observed": [march[f"{name}_extra_v2"], march["olist_extra_v2"]]},
        {"id": 4, "name": f"Coverage at least {COVERAGE_TARGET_PCT}%",
         "pass": bool(p["coverage_pct"] >= COVERAGE_TARGET_PCT), "observed": p["coverage_pct"]},
    ]
    if paired is not None:
        checks.append({"id": 5, "name": "Fewer extra bad reviews than route p95, paired bootstrap 2.5th percentile above 0",
                       "pass": bool(paired["point"] > 0 and paired["reduction_p025"] > 0),
                       "observed": [paired["point"], paired["reduction_p025"], paired["reduction_p975"]]})
    return {"checks": checks, "overall_pass": all(c["pass"] for c in checks),
            "failed": [c["name"] for c in checks if not c["pass"]]}


def importance(models: dict, df_rows: pd.DataFrame, month: str = "2018-03", n_repeats: int = 3) -> list:
    """Permutation importance (pinball loss) of the March 2018 model on March 2018 orders."""
    from sklearn.inspection import permutation_importance
    from sklearn.metrics import make_scorer, mean_pinball_loss
    from threadpoolctl import threadpool_limits
    model, _ = models[month]
    rows = df_rows[df_rows["year_month"] == month]
    scorer = make_scorer(mean_pinball_loss, alpha=INFO_CFG["quantile"], greater_is_better=False)
    with threadpool_limits(limits=1):
        r = permutation_importance(model, rows[F.FEATURES].to_numpy(dtype=float), rows["actual_days"].to_numpy(dtype=float),
                                   scoring=scorer, n_repeats=n_repeats, random_state=M.RANDOM_STATE, n_jobs=1)
    order = np.argsort(-r.importances_mean)
    return [{"feature": F.FEATURES[i], "pinball_increase": float(r.importances_mean[i])} for i in order]


def risk_flag(rows: pd.DataFrame) -> dict:
    """Orders where the model's date is later than Olist's printed date: a late-risk list at checkout.
    Fixed rule, not tuned: flagged = model lead > Olist lead."""
    from evaluate import bin_of, load_v2
    v2 = load_v2()
    flagged = rows["model_lead"] > rows["olist_lead"]
    late = rows["olist_days_late"] > 0
    rev = rows["review_score"].notna()
    eff = rows["olist_days_late"].map(lambda d: 0.0 if bin_of(int(d)) is None else v2[bin_of(int(d))]["effect"]) * rev
    return {
        "n_orders": int(len(rows)), "n_flagged": int(flagged.sum()),
        "flagged_share_pct": 100.0 * float(flagged.mean()),
        "n_late": int(late.sum()), "late_flagged": int((late & flagged).sum()),
        "late_caught_pct": 100.0 * float((late & flagged).sum()) / float(late.sum()),
        "late_rate_flagged_pct": 100.0 * float(late[flagged].mean()),
        "late_rate_unflagged_pct": 100.0 * float(late[~flagged].mean()),
        "extra_v2_olist": float(eff.sum()), "extra_v2_olist_flagged": float(eff[flagged].sum()),
        "extra_caught_pct": 100.0 * float(eff[flagged].sum()) / float(eff.sum()),
    }


def build_frame(con) -> pd.DataFrame:
    df = F.build(con)
    df["route_p95_lead"] = df["order_id"].map(route_p95_leads(con))
    return df


def run(con, with_importance: bool = True, df: pd.DataFrame | None = None) -> dict:
    df = build_frame(con) if df is None else df
    rows, models = M.walk_forward(df, M.HOLDOUT_MONTHS, INFO_CFG, keep_models=with_importance)
    missing_route = int(rows["route_p95_lead"].isna().sum())
    rows = rows[rows["route_p95_lead"].notna()].copy()
    rows["route_p95_lead"] = rows["route_p95_lead"].astype(int)
    res = M.score_block(rows, {"model": "model_lead", "route_p95": "route_p95_lead"}, with_boot=True)
    rev_mask = rows.sort_values("order_id", kind="mergesort")["review_score"].notna().to_numpy()
    assert rev_mask.sum() == res["n_reviewed"]
    pb = M.paired_boot(res["model"]["_eff"], res["route_p95"]["_eff"])
    pb["point"] = res["route_p95"]["v2"]["extra_policy"] - res["model"]["v2"]["extra_policy"]
    march = res["months"]["2018-03"]
    out = M.strip(res)
    out["integrity"] = {"holdout_months": M.HOLDOUT_MONTHS, "tune_months": M.TUNE_MONTHS,
                        "missing_route_p95": missing_route, "train_from": str(M.TRAIN_FROM.date()),
                        "n_train_by_month": {m: int(rows.loc[rows["year_month"] == m, "n_train"].iloc[0]) for m in M.HOLDOUT_MONTHS}}
    out["cfg"] = INFO_CFG
    out["coverage_target_pct"] = COVERAGE_TARGET_PCT
    out["paired_model_vs_route_p95"] = pb
    out["bar"] = {"model": apply_bar(res, "model", march, pb), "route_p95": apply_bar(res, "route_p95", march, None)}
    out["decision"] = {
        "model_passed_tuning": False,
        "model_passes_holdout": out["bar"]["model"]["overall_pass"],
        "model_adopted": False,
        "route_p95_meets_1_to_3": all(c["pass"] for c in out["bar"]["route_p95"]["checks"] if c["id"] <= 3),
    }
    out["risk_flag"] = risk_flag(rows)
    if with_importance:
        out["importance_march2018"] = importance(models, rows)
    return out
