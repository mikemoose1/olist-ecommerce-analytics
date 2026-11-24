"""Scores for a predicted range: CRPS (approximated by pinball loss over evenly spaced levels) and calibration."""
from __future__ import annotations

import numpy as np

from predict import CRPS_LEVELS, LEVELS


def pinball(y, q, level):
    d = y - q
    return np.maximum(level * d, (level - 1) * d)


def crps_per_order(y: np.ndarray, Q: np.ndarray) -> np.ndarray:
    """2 x mean pinball loss over the levels 0.05 ... 0.95 (lower is better; in days)."""
    idx = [int(np.where(np.isclose(LEVELS, a))[0][0]) for a in CRPS_LEVELS]
    return 2 * np.mean([pinball(y, Q[:, j], a) for j, a in zip(idx, CRPS_LEVELS)], axis=0)


def calibration(y: np.ndarray, Q: np.ndarray) -> dict:
    """Share of orders delivered within each predicted quantile, and the largest gap from the level over 0.5 ... 0.95."""
    cov = {f"{a:.2f}": float((y <= Q[:, j]).mean()) for j, a in enumerate(LEVELS)}
    gap = max(abs(cov[f"{a:.2f}"] - a) for a in LEVELS if 0.5 <= a <= 0.95 + 1e-9)
    return {"coverage": cov, "max_gap_0.5_to_0.95_pp": 100 * gap}


def paired_boot_mean(diff: np.ndarray, n_boot: int, seed: int) -> dict:
    rng = np.random.default_rng(seed); n = len(diff)
    m = np.array([diff[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
    return {"point": float(diff.mean()), "p025": float(np.quantile(m, 0.025)), "p975": float(np.quantile(m, 0.975)), "n_boot": n_boot, "seed": seed}
