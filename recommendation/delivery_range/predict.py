"""Prediction layer: a range of delivery days for each order, as quantiles. Knows nothing about promises or reviews.

Every candidate is walk-forward, exactly like ../delivery_date_model: one model per scored month, trained on orders
delivered before the 1st of that month and bought at least 45 days before it, on the same checkout-time features.
Output for each candidate: an (orders x LEVELS) array of predicted delivery days (purchase date to delivery date),
sorted along the levels so quantiles never cross.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "delivery_date_model"))
sys.path.insert(0, str(HERE.parent / "promise_backtest"))
import model as M  # noqa: E402
from features import CATEGORICAL, FEATURES  # noqa: E402
from score import quantile_disc  # noqa: E402

LEVELS = np.array([round(0.05 * k, 2) for k in range(1, 20)] + [0.97, 0.99])
CRPS_LEVELS = LEVELS[:19]                      # 0.05 ... 0.95, evenly spaced, used for the CRPS approximation
LABEL_LAG_DAYS = 45                            # the tuned lag of ../delivery_date_model
GBM = {"learning_rate": 0.05, "n_iter": 300, "leaves": 15, "min_leaf": 200}   # the setting ../delivery_date_model scored
N_JOBS = 8


def _X(df):
    return df[FEATURES].to_numpy(dtype=float)


def _fit_hgb(train, q):
    from sklearn.ensemble import HistGradientBoostingRegressor
    m = HistGradientBoostingRegressor(loss="quantile", quantile=q, learning_rate=GBM["learning_rate"], max_iter=GBM["n_iter"],
                                      max_leaf_nodes=GBM["leaves"], min_samples_leaf=GBM["min_leaf"], l2_regularization=1.0,
                                      categorical_features=[FEATURES.index(c) for c in CATEGORICAL], early_stopping=False,
                                      random_state=M.RANDOM_STATE)
    with threadpool_limits(limits=1):
        m.fit(_X(train), train["actual_days"].to_numpy(dtype=float))
    return m


def _fit_lgb(train, q):
    import lightgbm as lgb
    m = lgb.LGBMRegressor(objective="quantile", alpha=q, learning_rate=GBM["learning_rate"], n_estimators=GBM["n_iter"],
                          num_leaves=GBM["leaves"], min_child_samples=GBM["min_leaf"], reg_lambda=1.0, n_jobs=1,
                          random_state=M.RANDOM_STATE, verbose=-1)
    m.fit(train[FEATURES], train["actual_days"].to_numpy(dtype=float), categorical_feature=CATEGORICAL)
    return m


def _per_level(fit, train, rows):
    def one(q):
        m = fit(train, q)
        with threadpool_limits(limits=1):
            return m.predict(rows[FEATURES] if fit is _fit_lgb else _X(rows))
    cols = Parallel(n_jobs=N_JOBS)(delayed(one)(float(q)) for q in LEVELS)
    return np.column_stack(cols)


def _ngboost(train, rows):
    """NGBoost, log-normal on (days + 1) so a same-day delivery is allowed. NaN features filled with -1 (trees split on it)."""
    from ngboost import NGBRegressor
    from ngboost.distns import LogNormal
    from scipy.stats import lognorm
    Xt = np.nan_to_num(_X(train), nan=-1.0); Xs = np.nan_to_num(_X(rows), nan=-1.0)
    m = NGBRegressor(Dist=LogNormal, n_estimators=400, learning_rate=0.03, minibatch_frac=0.5, random_state=M.RANDOM_STATE, verbose=False)
    m.fit(Xt, train["actual_days"].to_numpy(dtype=float) + 1.0)
    d = m.pred_dist(Xs)
    s, scale = d.params["s"], d.params["scale"]
    return np.column_stack([lognorm.ppf(q, s, scale=scale) - 1.0 for q in LEVELS])


CANDIDATES = {
    "hgb_quantile": lambda train, rows: _per_level(_fit_hgb, train, rows),
    "lightgbm_quantile": lambda train, rows: _per_level(_fit_lgb, train, rows),
    "ngboost_lognormal": _ngboost,
}


def walk_forward(df: pd.DataFrame, months: list[str], name: str) -> tuple[pd.DataFrame, np.ndarray]:
    """Scored rows (judged orders bought in the months) and their predicted quantiles."""
    ym = df["purchase_date"].dt.strftime("%Y-%m")
    parts, preds = [], []
    for month in months:
        cutoff = pd.Timestamp(f"{month}-01")
        train = M.training_rows(df, cutoff, LABEL_LAG_DAYS)
        rows = df[df["is_judged"] & (ym == month)].copy()
        rows["year_month"] = month
        rows["n_train"] = len(train)
        parts.append(rows)
        preds.append(CANDIDATES[name](train, rows))
    return pd.concat(parts), np.sort(np.vstack(preds), axis=1)


def route_history(df: pd.DataFrame, months: list[str]) -> tuple[pd.DataFrame, np.ndarray]:
    """Baseline with no model: the route's own past delivery days (deliveries strictly before the purchase), read at each
    level. Falls back to the customer state, then to all routes, when a cell has fewer than 30 past deliveries."""
    ym = df["purchase_date"].dt.strftime("%Y-%m")
    rows = pd.concat([df[df["is_judged"] & (ym == m)].assign(year_month=m) for m in months])   # same row order as walk_forward
    hist = df[df["in_history"]].sort_values("delivered_at")
    t_h = hist["delivered_at"].to_numpy(); a_h = hist["actual_days"].to_numpy(dtype=int)
    by_route = {k: (g["delivered_at"].to_numpy(), g["actual_days"].to_numpy(dtype=int)) for k, g in hist.groupby("route")}
    by_state = {k: (g["delivered_at"].to_numpy(), g["actual_days"].to_numpy(dtype=int)) for k, g in hist.groupby("customer_state")}
    out = np.empty((len(rows), len(LEVELS)))
    for i, (t, route, st) in enumerate(zip(rows["purchased_at"].to_numpy(), rows["route"], rows["customer_state"])):
        vals = None
        for table, key in ((by_route, route), (by_state, st)):
            if key in table:
                tt, aa = table[key]; n = np.searchsorted(tt, t, side="left")
                if n >= 30:
                    vals = np.sort(aa[:n]); break
        if vals is None:
            vals = np.sort(a_h[:np.searchsorted(t_h, t, side="left")])
        out[i] = [vals[quantile_disc(len(vals), q)] for q in LEVELS]
    return rows, out
