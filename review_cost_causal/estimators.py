"""Estimators for 'does late delivery cause bad reviews'. Pure functions on a DataFrame.
Columns used: y (0/1 bad review), x (days past END of promised day; late iff x >= 0), seller (cluster/FE id),
category, ym (purchase month), late (0/1), lprice, lfreight, promised_days.
"""
import numpy as np, pandas as pd
import statsmodels.api as sm
from statsmodels.discrete.conditional_models import ConditionalLogit

Z = 1.959963984540054

def _cluster_vcov(X, e, groups, w=None):
    """Sandwich covariance with CR1 small-sample factor. X already includes weights if WLS (pass w)."""
    if w is None: w = np.ones(len(e))
    Xw = X * w[:, None]
    bread = np.linalg.pinv(X.T @ Xw)
    codes = pd.factorize(groups)[0]; G = codes.max() + 1
    S = np.zeros((G, X.shape[1]))
    np.add.at(S, codes, Xw * e[:, None])
    meat = S.T @ S
    n, k = X.shape
    c = G / (G - 1) * (n - 1) / max(n - k, 1)
    return c * bread @ meat @ bread

# ---------------------------------------------------------------- regression discontinuity
def rd_local_linear(x, y, groups, h, cutoff=0.0, donut=0.0, kernel="triangular", slopes=True):
    """Local linear RD: separate lines each side within |x-c|<h, triangular weights, seller-clustered SE.
    slopes=False is the deliberately BROKEN variant (plain difference in means) used to prove checks can fail."""
    x = np.asarray(x, float) - cutoff; y = np.asarray(y, float); groups = np.asarray(groups)
    m = (np.abs(x) < h) & (np.abs(x) >= donut)
    x, y, g = x[m], y[m], groups[m]
    t = (x >= 0).astype(float)
    w = np.clip(1 - np.abs(x) / h, 0, None) if kernel == "triangular" else np.ones_like(x)
    X = np.column_stack([np.ones_like(x), t, x, t * x]) if slopes else np.column_stack([np.ones_like(x), t])
    Xw = X * w[:, None]
    beta = np.linalg.lstsq(Xw.T @ X, Xw.T @ y, rcond=None)[0]
    e = y - X @ beta
    V = _cluster_vcov(X, e, g, w)
    se = float(np.sqrt(V[1, 1]))
    return {"jump": float(beta[1]), "se": se, "lo": float(beta[1] - Z * se), "hi": float(beta[1] + Z * se),
            "n_left": int((t == 0).sum()), "n_right": int((t == 1).sum()), "h": h, "donut": donut}

def rd_placebo(x, y, groups, cutoff, h):
    """Placebo cutoff using only one side of the real cutoff, so the real jump cannot leak in."""
    x = np.asarray(x, float)
    side = x < 0 if cutoff < 0 else x >= 0
    return rd_local_linear(x[side], np.asarray(y)[side], np.asarray(groups)[side], h, cutoff=cutoff)

# ---------------------------------------------------------------- fixed effects (within transformation)
def demean(arrs, fes, tol=1e-10, iters=500):
    """Alternating projections: remove every fixed effect in `fes` (list of integer code arrays) from each column."""
    out = np.array(arrs, float, copy=True)
    if out.ndim == 1: out = out[:, None]
    counts = [np.bincount(f) for f in fes]
    for _ in range(iters):
        prev = out.copy()
        for f, c in zip(fes, counts):
            sums = np.zeros((c.size, out.shape[1])); np.add.at(sums, f, out)
            out -= (sums / np.maximum(c, 1)[:, None])[f]
        if np.max(np.abs(out - prev)) < tol: break
    return out

BINS = [(0, 1, "late_d1"), (1, 2, "late_d2"), (2, 3, "late_d3"), (3, 6, "late_d4_6"), (6, 13, "late_d7_13"), (13, 1e9, "late_d14p")]

def late_bins(x):
    x = np.asarray(x, float)
    return np.column_stack([((x >= a) & (x < b)).astype(float) for a, b, _ in BINS])

def fe_lpm_att(df, fe_cols=("seller", "category", "ym"), extra=("lprice", "lfreight", "promised_days"), use_bins=True, early_slope=False):
    """Linear probability model with absorbed fixed effects. Effect of lateness by days-late bin; the
    extra-bad-review count = sum over reviewed late orders of their bin's effect. Seller-clustered SE.
    fe_cols without 'seller' is the deliberately BROKEN variant used to prove the confounding check can fail."""
    d = df
    D = late_bins(d.x) if use_bins else d[["late"]].to_numpy(float)
    names = [b[2] for b in BINS] if use_bins else ["late"]
    C = d[list(extra)].to_numpy(float) if extra else np.zeros((len(d), 0))
    if early_slope:   # on-time side trend: days early (capped at 30). Makes the counterfactual 'arrived just on time', not 'arrived early'.
        C = np.column_stack([C, np.clip(np.minimum(d.x.to_numpy(float), 0), -30, 0)])
    X = np.column_stack([D, C])
    fes = [pd.factorize(d[c])[0] for c in fe_cols] if fe_cols else []
    if fes:
        R = demean(np.column_stack([d.y.to_numpy(float), X]), fes)
        yd, Xd = R[:, 0], R[:, 1:]
    else:
        yd, Xd = d.y.to_numpy(float), np.column_stack([np.ones(len(d)), X])
        names = ["const"] + names
    beta = np.linalg.lstsq(Xd, yd, rcond=None)[0]
    e = yd - Xd @ beta
    V = _cluster_vcov(Xd, e, d.seller.to_numpy())
    off = 1 if not fes else 0
    nb = D.shape[1]
    counts = D[d.late.to_numpy() == 1].sum(0)            # reviewed late orders per bin (df is reviewed rows)
    b = beta[off:off + nb]; Vb = V[off:off + nb, off:off + nb]
    extra_n = float(counts @ b); se = float(np.sqrt(counts @ Vb @ counts))
    return {"bins": dict(zip(names[off:off + nb], map(float, b))), "bin_se": dict(zip(names[off:off + nb], map(float, np.sqrt(np.diag(Vb))))),
            "bin_counts": dict(zip(names[off:off + nb], map(int, counts))),
            "extra": extra_n, "se": se, "lo": extra_n - Z * se, "hi": extra_n + Z * se,
            "att_pp": 100 * extra_n / counts.sum(), "n": len(d)}

# ---------------------------------------------------------------- logistic
def conditional_logit(df, chunk=40, seed=0, extra=("lprice", "lfreight", "promised_days")):
    """Conditional logit on the late flag, conditioning out seller intercepts. Big sellers are split at random into
    chunks of <= `chunk` orders (a finer conditioning set still removes the seller effect) so the exact
    conditional likelihood stays computable. Category and month enter as dummies. Returns odds ratio for late."""
    d = df.copy()
    rng = np.random.default_rng(seed)
    d["_r"] = rng.random(len(d))
    d["_k"] = d.groupby("seller")["_r"].rank(method="first").sub(1).floordiv(chunk).astype(int)
    d["grp"] = d.seller.astype(str) + "#" + d._k.astype(str)
    g = d.groupby("grp").y.agg(["min", "max"])
    keep = g.index[(g["min"] != g["max"])]
    d = d[d.grp.isin(keep)]
    Xc = pd.get_dummies(d[["category", "ym"]].astype(str), drop_first=True, dtype=float)
    X = pd.concat([d[["late"]].astype(float), d[list(extra)].astype(float), Xc], axis=1)
    X = X.loc[:, X.std() > 0]
    res = ConditionalLogit(d.y.to_numpy(float), X, groups=d.grp.to_numpy()).fit(method="bfgs", maxiter=2000, disp=0,
                                                                                 cov_type="cluster", cov_kwds={"groups": pd.factorize(d.seller)[0]})
    b, se = float(res.params["late"]), float(res.bse["late"])
    return {"or": float(np.exp(b)), "or_lo": float(np.exp(b - Z * se)), "or_hi": float(np.exp(b + Z * se)),
            "beta": b, "se": se, "n_used": int(len(d)), "groups": int(d.grp.nunique()), "converged": bool(getattr(res, "converged", True))}

def mundlak_logit_att(df, extra=("lprice", "lfreight", "promised_days"), boot=0, seed=1, early_slope=False):
    """Correlated-random-effects (Mundlak) logit: late-bin dummies + covariates + each seller's MEAN of those
    (absorbs seller quality that correlates with lateness) + category and month dummies.
    Extra bad reviews = sum over reviewed late orders of P(bad | as observed) - P(bad | bins switched off).
    Interval from a seller-cluster bootstrap."""
    def fit_once(d):
        D = pd.DataFrame(late_bins(d.x), columns=[b[2] for b in BINS], index=d.index)
        base = pd.concat([D, d[list(extra)].astype(float)], axis=1)
        if early_slope: base["early"] = np.clip(np.minimum(d.x.to_numpy(float), 0), -30, 0)
        means = base.groupby(d.seller.to_numpy()).transform("mean").add_prefix("sm_")
        Xc = pd.get_dummies(d[["category", "ym"]].astype(str), drop_first=True, dtype=float)
        X = sm.add_constant(pd.concat([base, means, Xc], axis=1), has_constant="add")
        X = X.loc[:, (X.std() > 0) | (X.columns == "const")]
        r = sm.Logit(d.y.to_numpy(float), X).fit(disp=0, maxiter=200, method="newton")
        late = d.late.to_numpy() == 1
        X0 = X[late].copy(); X0[[c for c in D.columns if c in X0.columns]] = 0.0
        p1 = r.predict(X[late]); p0 = r.predict(X0)
        return float((p1 - p0).sum()), r
    est, r = fit_once(df)
    out = {"extra": est, "att_pp": 100 * est / int(df.late.sum()), "or_bins": {c: float(np.exp(r.params[c])) for c in r.params.index if c.startswith("late_")}}
    if boot:
        rng = np.random.default_rng(seed); sellers = df.seller.unique(); idx = df.groupby("seller").indices
        vals = []
        for _ in range(boot):
            pick = rng.choice(sellers, len(sellers), replace=True)
            rows = np.concatenate([idx[s] for s in pick])
            d = df.iloc[rows].copy(); d["seller"] = np.repeat(np.arange(len(pick)), [len(idx[s]) for s in pick])
            try: vals.append(fit_once(d)[0])
            except Exception: pass
        out.update({"lo": float(np.percentile(vals, 2.5)), "hi": float(np.percentile(vals, 97.5)), "boot_ok": len(vals)})
    return out

def naive_gap(df):
    a = df[df.late == 1].y.mean(); b = df[df.late == 0].y.mean()
    return {"gap_pp": 100 * (a - b), "extra": float((a - b) * (df.late == 1).sum())}
