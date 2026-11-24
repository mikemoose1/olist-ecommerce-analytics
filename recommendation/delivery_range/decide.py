"""Decision layer: turn a predicted range into a printed date. Reads only the predicted quantiles and the published
late-to-bad-review effects; it never sees the model. Two rules, each swept over its one setting:

  Rule T (tau):    lead = the predicted quantile at level tau, rounded up (at least 1 day).
  Rule C (lambda): per order, the whole-day lead that minimizes  expected extra bad reviews + lambda x lead days,
                   with the expected extra bad reviews worked out from the predicted distribution and the V2 effects.

Choosing tau or lambda is a business call (Mike's), not made here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "promise_backtest"))
from evaluate import BIN_ORDER, load_v2  # noqa: E402

from predict import LEVELS  # noqa: E402

TAUS = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.97, 0.99]
LAMBDAS = [0.0005, 0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.0075, 0.01, 0.015, 0.02, 0.03, 0.05, 0.1]
MAX_LEAD = 120
TAIL_DAYS = 14          # the 1% beyond the 0.99 quantile is put 14 days past it (the worst bin)


def effect_by_days_late(max_days: int) -> np.ndarray:
    """V2 effect of being k days late, k = 0 ... max_days (0 = on time)."""
    v2 = load_v2(); e = np.zeros(max_days + 1)
    edges = {"late_d1": (1, 1), "late_d2": (2, 2), "late_d3": (3, 3), "late_d4_6": (4, 6), "late_d7_13": (7, 13), "late_d14p": (14, max_days)}
    for b in BIN_ORDER:
        lo, hi = edges[b]; e[lo:hi + 1] = v2[b]["effect"]
    return e


def rule_t(Q: np.ndarray, tau: float) -> np.ndarray:
    j = int(np.where(np.isclose(LEVELS, tau))[0][0])
    return np.maximum(1, np.ceil(np.round(Q[:, j], 6))).astype(int)


def cdf_on_days(Q: np.ndarray, max_day: int) -> np.ndarray:
    """P(delivery days <= d) for d = 0 ... max_day, by straight lines between the predicted quantiles; 0 below the 0.05
    quantile minus its distance to the 0.10 one, and the last 1% spread to TAIL_DAYS past the 0.99 quantile."""
    n = len(Q); days = np.arange(max_day + 1)
    F = np.empty((n, max_day + 1))
    lo = Q[:, 0] - (Q[:, 1] - Q[:, 0]); hi = Q[:, -1] + TAIL_DAYS
    xs = np.column_stack([lo, Q, hi]); ps = np.concatenate([[0.0], LEVELS, [1.0]])
    for i in range(n):
        x = np.maximum.accumulate(xs[i] + np.arange(len(ps)) * 1e-9)   # strictly increasing for interp
        F[i] = np.interp(days, x, ps, left=0.0, right=1.0)
    return F


def rule_c(Q: np.ndarray, lam: float, F: np.ndarray | None = None) -> np.ndarray:
    """Per-order lead minimizing E[extra bad reviews] + lam * lead."""
    max_day = F.shape[1] - 1 if F is not None else MAX_LEAD + 60
    F = cdf_on_days(Q, max_day) if F is None else F
    p = np.diff(np.concatenate([np.zeros((len(F), 1)), F], axis=1), axis=1)   # P(days = d)
    p[:, -1] += 1 - F[:, -1]
    eff = effect_by_days_late(max_day)
    leads = np.arange(1, MAX_LEAD + 1)
    best = np.full(len(F), np.inf); arg = np.ones(len(F), dtype=int)
    for L in leads:
        k = np.clip(np.arange(max_day + 1) - L, 0, None)   # days late if delivered on day d
        cost = p @ eff[k] + lam * L
        better = cost < best
        best[better] = cost[better]; arg[better] = L
    return arg
