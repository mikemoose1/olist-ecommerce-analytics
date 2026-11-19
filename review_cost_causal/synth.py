"""Synthetic orders with a KNOWN answer. Seller quality drives both lateness and bad reviews (confounding),
so a method that ignores sellers sees an effect even when lateness does nothing."""
import numpy as np, pandas as pd
expit = lambda z: 1 / (1 + np.exp(-z))

def make(seed, effect=True, n_sellers=3000, n=95000, J=1.0, k=0.45, cap=6.0):
    rng = np.random.default_rng(seed)
    size = rng.pareto(1.3, n_sellers) + 1; size = np.maximum(1, np.round(size / size.sum() * n)).astype(int)
    seller = np.repeat(np.arange(n_sellers), size); N = len(seller)
    q = rng.normal(0, 1, n_sellers)[seller]                       # seller quality (bad = high)
    cat = rng.integers(0, 30, N); ym = rng.integers(0, 20, N)
    ceff = rng.normal(0, .3, 30)[cat]; meff = rng.normal(0, .2, 20)[ym]
    x = rng.normal(-11 + 2.2 * q + 1.5 * (meff > .2), 6.5)         # days past end of promised day
    lin = -2.6 + 0.7 * q + ceff + meff
    dose = (J + k * np.minimum(np.maximum(x, 0), cap)) * (x >= 0) if effect else np.zeros(N)
    p1 = expit(lin + dose); p0 = expit(lin)
    y = (rng.random(N) < p1).astype(int)
    df = pd.DataFrame({"seller": seller, "category": cat, "ym": ym, "x": x, "late": (x >= 0).astype(int), "y": y,
                       "lprice": rng.normal(4, 1, N) + .1 * q, "lfreight": rng.normal(3, .5, N), "promised_days": rng.integers(10, 40, N)})
    late = df.late.to_numpy() == 1
    near = np.abs(x) < 0.25
    truth = {"extra": float((p1 - p0)[late].sum()),
             "jump": float((expit(lin + J) - expit(lin))[near].mean()) if effect else 0.0}
    return df, truth
