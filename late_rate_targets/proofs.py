"""Proof that the control-chart method catches a real bad month, stays quiet on pure chance, and can fail.

Every check is a function that returns (passed, detail). selftest.py feeds each one deliberately broken input and
requires it to report failure, so a check that cannot fail would be caught there.
"""
import numpy as np
import spc

SEEDS = 5000
PLANT_PP = 0.06            # a planted bad month: 6 percentage points above the baseline (the real peaks sit 8 to 14 above)
PLANT_AT = 14              # position in the 20-month series (March 2018 is index 14)
# pass thresholds, fixed before looking at results
MAX_SERIES_FALSE_ALARM = 0.15   # share of pure-noise 20-month series with any flagged month (ideal about 5%)
MIN_DETECTION = 0.95            # share of planted series where the planted month is flagged


def simulate(n, base, seeds, rng, plant=None, extra_sd=0.0):
    """Counts k[s, i] ~ Binomial(n_i, p_si). p_si = base (+ plant at one month) (+ month-to-month noise of sd extra_sd)."""
    n = np.asarray(n).astype(int)
    p = np.full((seeds, len(n)), base)
    if extra_sd:
        p = np.clip(p + rng.normal(0, extra_sd, p.shape), 0.001, 0.5)
    if plant is not None:
        p[:, plant[0]] = np.clip(p[:, plant[0]] + plant[1], 0, 0.9)
    return rng.binomial(n, p)


def _detector(kind):
    if kind == "plain":
        return lambda k, n: spc.fit_plain(k, n)["signal"]
    if kind == "laney":
        return lambda k, n: spc.fit_laney(k, n)["signal"]
    raise ValueError(kind)


def rates(n, base, kind, seeds=SEEDS, seed=1, plant=None, extra_sd=0.0, detector=None):
    """Return {series_with_any_flag, point_flag_rate, planted_month_flagged} over many seeds."""
    rng = np.random.default_rng(seed)
    ks = simulate(n, base, seeds, rng, plant, extra_sd)
    det = detector or _detector(kind)
    sig = np.array([det(k, n) for k in ks])
    out = {"series_any_flag": float(sig.any(axis=1).mean()), "point_flag_rate": float(sig.mean())}
    if plant is not None:
        out["planted_flagged"] = float(sig[:, plant[0]].mean())
        others = np.delete(sig, plant[0], axis=1)
        out["other_months_flag_rate"] = float(others.mean())
    return out


def check_planted_month_is_flagged(n, base, kind, detector=None, seeds=SEEDS):
    r = rates(n, base, kind, seeds, seed=2, plant=(PLANT_AT, PLANT_PP), detector=detector)
    return r["planted_flagged"] >= MIN_DETECTION, r


def check_pure_noise_is_quiet(n, base, kind, detector=None, seeds=SEEDS):
    r = rates(n, base, kind, seeds, seed=3, detector=detector)
    return r["series_any_flag"] <= MAX_SERIES_FALSE_ALARM, r


def check_holdout_flags_month(months, k, n, fit_months, target_month, kind="laney"):
    """Fit the limits on `fit_months` only, then judge every other month; the target month must be flagged."""
    months = list(months)
    k, n = np.asarray(k, float), np.asarray(n, float)
    idx = np.array([m in fit_months for m in months])
    fit = spc.fit_plain(k[idx], n[idx]) if kind == "plain" else spc.fit_laney(k[idx], n[idx])
    judged = spc.apply_limits(fit["centre"], fit["sigma_z"], k[~idx], n[~idx])
    out_months = [m for m, i in zip(months, idx) if not i]
    flagged = {m: bool(s) for m, s in zip(out_months, judged["signal"])}
    rows = {m: {"rate": float(k[months.index(m)] / n[months.index(m)]), "ucl": float(u), "flagged": flagged[m]}
            for m, u in zip(out_months, judged["ucl"])}
    return flagged[target_month], {"centre": float(fit["centre"]), "sigma_z": float(fit["sigma_z"]), "months": rows}


def check_dispersion_test_discriminates(n, base, real_k, seeds=2000):
    """The dispersion test must say 'chance' for chance-only data and 'more than chance' for the real months."""
    rng = np.random.default_rng(4)
    ks = rng.binomial(np.asarray(n).astype(int), base, size=(seeds, len(n)))
    rej = np.mean([spc.dispersion_test(k, n)["p_value"] < 0.01 for k in ks])
    real = spc.dispersion_test(real_k, n)
    return (rej <= 0.03 and real["p_value"] < 0.01), {"noise_rejected_at_1pct": float(rej), "real": real}


def check_stretch_is_like_for_like(stretch, goal, rate_stable, whatif_stable):
    """The goal line is the median of the stable months' real late rates. The stretch line must be the median of the same
    months' what-if rates (late handoffs no later than on-time ones), so goal minus stretch is the what-if alone.
    A stretch taken at another percentile (the retired 25th, 2.25%) mixes the what-if with a better month and fails."""
    goal_ok = abs(goal - float(np.median(rate_stable))) < 1e-12
    same_months = len(rate_stable) == len(whatif_stable)
    stretch_ok = abs(stretch - float(np.median(whatif_stable))) < 1e-12
    return bool(goal_ok and same_months and stretch_ok and stretch < goal), {"gap_pp": 100 * (goal - stretch)}
