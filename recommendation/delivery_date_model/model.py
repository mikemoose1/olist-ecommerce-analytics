"""Walk-forward per-order delivery-date model and its scoring.

Each month gets its own model, trained only on orders delivered before the 1st of that month,
then used to print a date for every judged order bought in that month.
"""
from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "promise_backtest"))
sys.path.insert(0, str(HERE))
from evaluate import BIN_ORDER, Z95, bin_of, load_v2, load_v4  # noqa: E402
from features import CATEGORICAL, FEATURES  # noqa: E402

TRAIN_FROM = pd.Timestamp("2017-01-01")
TUNE_MONTHS = ["2017-11", "2017-12", "2018-01", "2018-02"]
HOLDOUT_MONTHS = ["2018-03", "2018-04", "2018-05", "2018-06", "2018-07", "2018-08"]
SPIKE_MONTHS = {"2017-11", "2018-02", "2018-03"}
BOOT_SEED = 20261121
N_BOOT = 5000
RANDOM_STATE = 20261121


def fit(train: pd.DataFrame, cfg: dict) -> HistGradientBoostingRegressor:
    m = HistGradientBoostingRegressor(
        loss="quantile",
        quantile=cfg["quantile"],
        learning_rate=cfg["learning_rate"],
        max_iter=cfg["max_iter"],
        max_leaf_nodes=cfg["max_leaf_nodes"],
        min_samples_leaf=cfg["min_samples_leaf"],
        l2_regularization=1.0,
        categorical_features=[FEATURES.index(c) for c in CATEGORICAL],
        early_stopping=False,
        random_state=RANDOM_STATE,
    )
    with threadpool_limits(limits=1):
        m.fit(train[FEATURES].to_numpy(dtype=float), train["actual_days"].to_numpy(dtype=float))
    return m


def training_rows(df: pd.DataFrame, cutoff: pd.Timestamp, lag_days: int) -> pd.DataFrame:
    """Orders delivered strictly before the cutoff (the 1st of the scored month), and bought at least
    lag_days before it. Without the lag, the newest purchases in training would be only the fast ones
    (slow ones have not arrived yet), which teaches the model that busy weeks deliver fast."""
    m = (df["in_history"] & (df["purchased_at"] >= TRAIN_FROM) & (df["delivered_at"] < cutoff)
         & (df["purchased_at"] < cutoff - pd.Timedelta(days=lag_days)))
    return df[m]


def walk_forward(df: pd.DataFrame, months: list[str], cfg: dict, keep_models: bool = False):
    """Return scored rows (judged orders in the months) with model_lead, and optionally the models."""
    ym = df["purchase_date"].dt.strftime("%Y-%m")
    parts, models = [], {}
    for month in months:
        cutoff = pd.Timestamp(f"{month}-01")
        train = training_rows(df, cutoff, cfg["label_lag_days"])
        model = fit(train, cfg)
        rows = df[df["is_judged"] & (ym == month)].copy()
        with threadpool_limits(limits=1):
            pred = model.predict(rows[FEATURES].to_numpy(dtype=float))
        rows["model_pred"] = pred
        rows["model_lead"] = np.maximum(1, np.ceil(np.round(pred, 6))).astype(int)
        rows["year_month"] = month
        rows["n_train"] = len(train)
        parts.append(rows)
        if keep_models:
            models[month] = (model, train)
    return pd.concat(parts), models


def _counts(days) -> Counter:
    c = Counter()
    for d in days:
        b = bin_of(int(d))
        if b is not None:
            c[b] += 1
    return c


def _extra(c: Counter, eff: dict) -> float:
    return sum(c[b] * eff[b]["effect"] for b in BIN_ORDER)


def _net(c_pol: Counter, c_base: Counter, eff: dict) -> dict:
    e_p, e_b = _extra(c_pol, eff), _extra(c_base, eff)
    se = math.sqrt(sum((c_pol[b] - c_base[b]) ** 2 * eff[b]["se"] ** 2 for b in BIN_ORDER))
    red = e_b - e_p
    return {"extra_policy": e_p, "extra_base": e_b, "reduction": red, "se": se,
            "ci_reduction_lo": red - Z95 * se, "ci_reduction_hi": red + Z95 * se}


def _boot(delta: np.ndarray, base: np.ndarray, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n = len(delta)
    red = np.empty(N_BOOT)
    bs = np.empty(N_BOOT)
    for i in range(N_BOOT):
        j = rng.integers(0, n, size=n)
        red[i] = delta[j].sum()
        bs[i] = base[j].sum()
    pct = 100.0 * red / bs
    return {"n_boot": N_BOOT, "seed": seed,
            "reduction_p025": float(np.quantile(red, 0.025)), "reduction_p975": float(np.quantile(red, 0.975)),
            "percent_p025": float(np.quantile(pct, 0.025)), "percent_p975": float(np.quantile(pct, 0.975))}


def score_block(rows: pd.DataFrame, policies: dict[str, str], with_boot: bool = False) -> dict:
    """policies maps a name to its lead column. Olist's printed promise is the baseline."""
    v2, v4 = load_v2(), load_v4()
    rows = rows.copy()
    rows["olist_dl"] = rows["olist_days_late"].astype(int)
    for name, col in policies.items():
        rows[f"{name}_dl"] = ((rows["delivered_date"] - rows["purchase_date"]).dt.days - rows[col]).astype(int)
    rev = rows[rows["review_score"].notna()].sort_values("order_id", kind="mergesort")
    out = {"n_scored": int(len(rows)), "n_reviewed": int(len(rev)),
           "olist": {"extra_v2": _extra(_counts(rev["olist_dl"]), v2),
                     "coverage_pct": 100.0 * float((rows["olist_dl"] <= 0).mean()),
                     "mean_lead": float(rows["olist_lead"].mean()),
                     "median_lead": float(rows["olist_lead"].median())},
           "months": {}}
    c_ol = _counts(rev["olist_dl"])
    eff_ol = rev["olist_dl"].map(lambda d: 0.0 if bin_of(int(d)) is None else v2[bin_of(int(d))]["effect"]).to_numpy()
    for name, col in policies.items():
        c_p = _counts(rev[f"{name}_dl"])
        eff_p = rev[f"{name}_dl"].map(lambda d: 0.0 if bin_of(int(d)) is None else v2[bin_of(int(d))]["effect"]).to_numpy()
        res = {
            "v2": _net(c_p, c_ol, v2),
            "v4": _net(c_p, c_ol, v4),
            "coverage_pct": 100.0 * float((rows[f"{name}_dl"] <= 0).mean()),
            "mean_lead": float(rows[col].mean()),
            "median_lead": float(rows[col].median()),
            "mean_extra_days_vs_olist": float((rows[col] - rows["olist_lead"]).mean()),
            "counts_policy": {b: int(c_p[b]) for b in BIN_ORDER},
        }
        ol_late = (rev["olist_dl"] > 0).to_numpy()
        p_late = (rev[f"{name}_dl"] > 0).to_numpy()
        d = eff_p - eff_ol
        res["four_states"] = {
            "newly_on_time": {"n": int((ol_late & ~p_late).sum()), "sum_delta": float(d[ol_late & ~p_late].sum())},
            "newly_late": {"n": int((~ol_late & p_late).sum()), "sum_delta": float(d[~ol_late & p_late].sum())},
            "still_late": {"n": int((ol_late & p_late).sum()), "sum_delta": float(d[ol_late & p_late].sum())},
            "still_on_time": {"n": int((~ol_late & ~p_late).sum()), "sum_delta": float(d[~ol_late & ~p_late].sum())},
        }
        if with_boot:
            res["bootstrap_vs_olist"] = _boot(eff_ol - eff_p, eff_ol, BOOT_SEED)
        res["_eff"] = eff_p
        out[name] = res
    out["counts_olist"] = {b: int(c_ol[b]) for b in BIN_ORDER}
    for month in sorted(rows["year_month"].unique()):
        r_m = rev[rev["year_month"] == month]
        a_m = rows[rows["year_month"] == month]
        mo = {"n_reviewed": int(len(r_m)), "olist_extra_v2": _extra(_counts(r_m["olist_dl"]), v2),
              "olist_coverage_pct": 100.0 * float((a_m["olist_dl"] <= 0).mean())}
        for name in policies:
            mo[f"{name}_extra_v2"] = _extra(_counts(r_m[f"{name}_dl"]), v2)
            mo[f"{name}_coverage_pct"] = 100.0 * float((a_m[f"{name}_dl"] <= 0).mean())
            mo[f"{name}_mean_extra_days"] = float((a_m[policies[name]] - a_m["olist_lead"]).mean())
        out["months"][month] = mo
    return out


def paired_boot(eff_a: np.ndarray, eff_b: np.ndarray, seed: int = BOOT_SEED + 1) -> dict:
    """Range for extra(b) - extra(a): how many fewer bad reviews a gives than b."""
    return _boot(eff_b - eff_a, eff_b, seed)


def strip(obj):
    if isinstance(obj, dict):
        return {k: strip(v) for k, v in obj.items() if not k.startswith("_")}
    return obj
