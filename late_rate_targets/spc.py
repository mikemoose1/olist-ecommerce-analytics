"""p-chart control limits for a monthly late rate: plain and Laney p-prime, plus the dispersion test.

Pure functions on counts, no database. The dbt model metrics.metric_late_rate_control_chart does the same fit in SQL;
analyze.py requires the two to agree to 1e-9.

  late k_i of n_i orders in month i.   centre p = sum(k)/sum(n) over the months in the fit.
  sigma_i = sqrt(p(1-p)/n_i)           what chance alone gives for a month of n_i orders
  z_i     = (k_i/n_i - p)/sigma_i      how many chance-sized steps the month sits from the centre
  plain limits : p +/- 3 sigma_i
  Laney limits : p +/- 3 sigma_i * sigma_z, sigma_z = mean(|z_i - z_(i-1)|)/1.128, never below 1
                 (moving range of neighbouring months; two months count only when both are in the fit)
  Laney is fitted in passes: months outside the limits leave the fit, centre and sigma_z are refitted, until no month moves.
"""
import numpy as np
from scipy import stats

D2 = 1.128   # mean moving range of two standard-normal draws is 1.128


def limits(centre, sigma_z, n):
    sig = np.sqrt(centre * (1 - centre) / n)
    return np.maximum(0.0, centre - 3 * sigma_z * sig), centre + 3 * sigma_z * sig


def sigma_z_of(z, in_fit):
    """Typical size of a month's standardised swing, from neighbouring months that are both in the fit."""
    both = in_fit[1:] & in_fit[:-1]
    if not both.any():
        return 1.0
    return max(1.0, float(np.abs(np.diff(z))[both].mean() / D2))


def fit_plain(k, n):
    """Classic p-chart: centre = overall rate, one pass, nothing set aside."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    centre = k.sum() / n.sum()
    lcl, ucl = limits(centre, 1.0, n)
    p = k / n
    return {"centre": centre, "sigma_z": 1.0, "lcl": lcl, "ucl": ucl, "signal": (p > ucl) | (p < lcl),
            "in_fit": np.ones(len(k), bool), "passes": 1}


def fit_laney(k, n, max_passes=100, laney=True, iterate=True):
    """Laney p-prime fitted in passes. laney=False, iterate=True is the plain chart refitted the same way."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    p = k / n
    in_fit = np.ones(len(k), bool)
    for i in range(1, max_passes + 1):
        centre = k[in_fit].sum() / n[in_fit].sum()
        z = (p - centre) / np.sqrt(centre * (1 - centre) / n)
        sz = sigma_z_of(z, in_fit) if laney else 1.0
        lcl, ucl = limits(centre, sz, n)
        new = (p >= lcl) & (p <= ucl)
        if not iterate or (new == in_fit).all():
            break
        in_fit = new
    return {"centre": centre, "sigma_z": sz, "lcl": lcl, "ucl": ucl, "signal": ~new, "in_fit": in_fit, "passes": i}


def apply_limits(centre, sigma_z, k, n):
    """Judge months the fit never saw (the 2017-only holdout)."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    lcl, ucl = limits(centre, sigma_z, n)
    p = k / n
    return {"lcl": lcl, "ucl": ucl, "signal": (p > ucl) | (p < lcl)}


def dispersion_test(k, n):
    """Do months differ more than chance alone explains? Pearson chi-square of equal rates, k-1 degrees of freedom.
    phi = chi2/df is about 1 when chance explains the spread; much larger means real month-to-month change."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    p = k.sum() / n.sum()
    chi2 = float((((k - n * p) ** 2) / (n * p * (1 - p))).sum())
    df = len(k) - 1
    return {"chi2": chi2, "df": df, "phi": chi2 / df, "p_value": float(stats.chi2.sf(chi2, df))}
