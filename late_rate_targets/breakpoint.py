"""Is there a break where lateness starts to cost reviews? Segmented and logistic fits, with a test for 'no break'.

Two views:
  days   : share of 1-2 star reviews against days after the promised day (grouped by whole day, capped at -30 and +30).
  months : each month's bad-review share against that month's late rate (20 points).
A "hinge" term (x - t)+ is zero until x passes t, then grows: it lets the slope change at t (a break).
A break location is searched on a grid, so the usual chi-square p-value does not apply; the p-value comes from a
parametric bootstrap (simulate data with NO break from the fitted straight line, search again, see how large the gain gets).
"""
import itertools

import numpy as np


def _ll(X, beta, y, n):
    mu = np.clip(1 / (1 + np.exp(-np.clip(X @ beta, -30, 30))), 1e-12, 1 - 1e-12)
    return float((y * np.log(mu) + (n - y) * np.log(1 - mu)).sum())


def _irls(X, y, n, iters=100):
    """Binomial logistic regression on grouped counts (y bad of n), Newton steps with step-halving. Returns beta, log-likelihood."""
    beta = np.zeros(X.shape[1])
    p0 = np.clip((y.sum() + .5) / (n.sum() + 1), 1e-6, 1 - 1e-6)
    beta[0] = np.log(p0 / (1 - p0))
    cur = _ll(X, beta, y, n)
    for _ in range(iters):
        mu = 1 / (1 + np.exp(-np.clip(X @ beta, -30, 30)))
        w = np.maximum(n * mu * (1 - mu), 1e-10)
        grad = X.T @ (y - n * mu)
        step = np.linalg.solve((X * w[:, None]).T @ X + 1e-9 * np.eye(X.shape[1]), grad)
        t = 1.0
        while t > 1e-6:
            cand = beta + t * step
            val = _ll(X, cand, y, n)
            if val >= cur - 1e-12:
                break
            t /= 2
        if t <= 1e-6:
            break
        done = abs(val - cur) < 1e-10
        beta, cur = cand, val
        if done:
            break
    return beta, cur


def _design(x, knots):
    return np.column_stack([np.ones_like(x, float), x] + [np.maximum(x - t, 0) for t in knots])


def logit_fit(x, y, n, knots=()):
    X = _design(np.asarray(x, float), knots)
    beta, ll = _irls(X, np.asarray(y, float), np.asarray(n, float))
    return beta, ll


def logit_search(x, y, n, grid, n_knots):
    """Best hinge position(s) by log-likelihood. Returns (knots, beta, loglik)."""
    best = None
    if n_knots == 1:
        cands = [(t,) for t in grid]
    elif n_knots == 2:
        cands = [(a, b) for a in grid for b in grid if b >= a + 2]
    else:
        cands = [kn for kn in itertools.combinations(grid, 3) if kn[1] - kn[0] >= 2 and kn[2] - kn[1] >= 2]
    for kn in cands:
        beta, ll = logit_fit(x, y, n, kn)
        if best is None or ll > best[2]:
            best = (kn, beta, ll)
    return best


def logit_predict(x, knots, beta):
    return 1 / (1 + np.exp(-(_design(np.asarray(x, float), knots) @ beta)))


def aic_bic(ll, k_params, n_obs):
    return -2 * ll + 2 * k_params, -2 * ll + k_params * np.log(n_obs)


def davies_logit(x, y, n, grid, B, seed):
    """Test straight line vs one break (logit scale). p-value by parametric bootstrap from the straight-line fit."""
    x, y, n = map(lambda a: np.asarray(a, float), (x, y, n))
    b0, ll0 = logit_fit(x, y, n)
    _, _, ll1 = logit_search(x, y, n, grid, 1)
    obs = 2 * (ll1 - ll0)
    rng = np.random.default_rng(seed)
    mu = logit_predict(x, (), b0)
    gains = []
    for _ in range(B):
        yb = rng.binomial(n.astype(int), mu).astype(float)
        _, l0 = logit_fit(x, yb, n)
        _, _, l1 = logit_search(x, yb, n, grid, 1)
        gains.append(2 * (l1 - l0))
    gains = np.array(gains)
    return {"lr_gain": float(obs), "p_value": float((1 + (gains >= obs).sum()) / (B + 1)), "boot_95th_gain": float(np.percentile(gains, 95))}


def boot_knots(x, y, n, knots, beta, grid, B, seed):
    """Percentile interval for two break positions: simulate from the fitted two-break curve, search again."""
    x, y, n = map(lambda a: np.asarray(a, float), (x, y, n))
    rng = np.random.default_rng(seed)
    mu = logit_predict(x, knots, beta)
    out = []
    for _ in range(B):
        yb = rng.binomial(n.astype(int), mu).astype(float)
        kn, _, _ = logit_search(x, yb, n, grid, 2)
        out.append(kn)
    out = np.array(out)
    return {"first_break_95": [float(np.percentile(out[:, 0], 2.5)), float(np.percentile(out[:, 0], 97.5))],
            "second_break_95": [float(np.percentile(out[:, 1], 2.5)), float(np.percentile(out[:, 1], 97.5))]}


# ---- probability-scale segmented regression (straight pieces on the share itself), weighted by group size
def _wls(X, y, w):
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    r = y - X @ beta
    return beta, float((w * r * r).sum())


def seg_search(x, share, w, grid, n_knots):
    x = np.asarray(x, float)
    cands = [(t,) for t in grid] if n_knots == 1 else [(a, b) for a in grid for b in grid if b >= a + 2]
    if n_knots == 0:
        cands = [()]
    best = None
    for kn in cands:
        beta, rss = _wls(_design(x, kn), share, w)
        if best is None or rss < best[2]:
            best = (kn, beta, rss)
    return best


def davies_seg(x, share, w, grid, B, seed, n_counts):
    """Straight line vs one break on the share scale; bootstrap from the straight line with binomial noise."""
    x, share, w = map(lambda a: np.asarray(a, float), (x, share, w))
    _, b0, rss0 = seg_search(x, share, w, grid, 0)
    _, _, rss1 = seg_search(x, share, w, grid, 1)
    obs = rss0 - rss1
    rng = np.random.default_rng(seed)
    fit0 = _design(x, ()) @ b0
    gains = []
    for _ in range(B):
        sb = rng.binomial(np.asarray(n_counts, int), np.clip(fit0, 0.001, 0.999)) / np.asarray(n_counts, float)
        _, bb, r0 = seg_search(x, sb, w, grid, 0)
        _, _, r1 = seg_search(x, sb, w, grid, 1)
        gains.append(r0 - r1)
    gains = np.array(gains)
    return {"rss_gain": float(obs), "rss_straight": float(rss0), "rss_one_break": float(rss1),
            "p_value": float((1 + (gains >= obs).sum()) / (B + 1))}


def davies_seg_wild(x, share, w, grid, B, seed):
    """Straight line vs one break on the share scale, for data scattered MORE than binomial chance (the monthly points).
    Wild bootstrap: keep the straight-line fit, flip the sign of each real residual at random, search again.
    The binomial bootstrap would call almost any bend 'real' here because the straight line misses by far more than chance."""
    x, share, w = map(lambda a: np.asarray(a, float), (x, share, w))
    _, b0, rss0 = seg_search(x, share, w, grid, 0)
    _, _, rss1 = seg_search(x, share, w, grid, 1)
    obs = rss0 - rss1
    rng = np.random.default_rng(seed)
    fit0 = _design(x, ()) @ b0
    res = share - fit0
    gains = []
    for _ in range(B):
        sb = fit0 + res * rng.choice([-1.0, 1.0], len(x))
        _, _, r0 = seg_search(x, sb, w, grid, 0)
        _, _, r1 = seg_search(x, sb, w, grid, 1)
        gains.append(r0 - r1)
    gains = np.array(gains)
    return {"rss_gain": float(obs), "rss_straight": float(rss0), "rss_one_break": float(rss1),
            "p_value": float((1 + (gains >= obs).sum()) / (B + 1))}


def leave_one_out_break(x, share, w, grid_fn):
    """Where the one-break fit puts its break when each point is left out in turn."""
    x, share, w = map(lambda a: np.asarray(a, float), (x, share, w))
    out = []
    for i in range(len(x)):
        keep = np.arange(len(x)) != i
        out.append(float(seg_search(x[keep], share[keep], w[keep], grid_fn(x[keep]), 1)[0][0]))
    return out
