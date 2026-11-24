"""(b) How strong would a hidden confounder have to be to halve the ~3,110 estimate? (pre-registered in
docs/preregistration_v2.md). E-value (VanderWeele and Ding 2017) and an Oster (2019) style bound.
Writes evidence/sensitivity_report.json. About 1 minute.
Usage: python review_cost_causal/stress/sensitivity.py
"""
import json, math, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import E, ROOT, load, published  # noqa: E402


def e_value(rr):
    """Smallest risk ratio a hidden factor needs with BOTH lateness and bad reviews to move the estimate by rr."""
    rr = max(rr, 1 / rr)
    return rr + math.sqrt(rr * (rr - 1))


def evalues(p1, att):
    """p1 = observed bad-review rate of reviewed late orders; att = average effect on them (share points as a fraction)."""
    p0 = p1 - att; rr = p1 / p0
    p0_half = p1 - att / 2; rr_half = p1 / p0_half
    return {"p1": p1, "p0": p0, "rr": rr, "rr_if_halved": rr_half, "rr_to_remove_for_half": rr / rr_half,
            "e_value_explain_away": e_value(rr), "e_value_halve": e_value(rr / rr_half)}


def r2_and_beta(R, fe_cols, cov, early_slope):
    """Single late indicator. Returns (beta_late, R-squared of the full model, fixed effects included)."""
    y = R.y.to_numpy(float)
    X = R[["late"] + cov].to_numpy(float)
    if early_slope:
        X = np.column_stack([X, np.clip(np.minimum(R.x.to_numpy(float), 0), -30, 0)])
    if fe_cols:
        M = E.demean(np.column_stack([y, X]), [pd.factorize(R[c])[0] for c in fe_cols])
        yd, Xd = M[:, 0], M[:, 1:]
    else:
        yd, Xd = y, np.column_stack([np.ones(len(y)), X])
    b = np.linalg.lstsq(Xd, yd, rcond=None)[0]
    ssr = float(((yd - Xd @ b) ** 2).sum()); sst = float(((y - y.mean()) ** 2).sum())
    return float(b[0] if fe_cols else b[1]), 1 - ssr / sst


def oster_delta(b_u, r_u, b_c, r_c, target, rmax):
    """delta such that beta* = target, from beta* = b_c - delta (b_u - b_c)(rmax - r_c)/(r_c - r_u)."""
    den = (b_u - b_c) * (rmax - r_c)
    return float("inf") if den == 0 else (b_c - target) * (r_c - r_u) / den


if __name__ == "__main__":
    R = load(); pub = published(); v2 = pub["fe"]["V2_preferred"]
    late = R.late == 1; n_late = int(late.sum()); p1 = float(R[late].y.mean())
    out = {"n_reviewed": len(R), "n_reviewed_late": n_late, "v2_extra": v2["extra"], "v2_ci95": [v2["lo"], v2["hi"]]}
    out["e_value_point"] = evalues(p1, v2["extra"] / n_late)
    out["e_value_ci_low"] = evalues(p1, v2["lo"] / n_late)
    # Oster: uncontrolled vs the V2 controls, one late coefficient
    b_u, r_u = r2_and_beta(R, (), [], False)
    b_c, r_c = r2_and_beta(R, ("seller", "category", "ym"), ["lprice", "lfreight", "promised_days"], True)
    out["oster"] = {"beta_uncontrolled": b_u, "r2_uncontrolled": r_u, "beta_controlled": b_c, "r2_controlled": r_c,
                    "controls_moved_estimate": "down" if b_c < b_u else "up"}
    for name, rmax in (("rmax_1.3x", min(1.3 * r_c, 1.0)), ("rmax_1", 1.0)):
        out["oster"][name] = {"rmax": rmax, "delta_to_halve": oster_delta(b_u, r_u, b_c, r_c, b_c / 2, rmax),
                              "delta_to_zero": oster_delta(b_u, r_u, b_c, r_c, 0.0, rmax),
                              "beta_at_delta_1": b_c - (b_u - b_c) * (rmax - r_c) / (r_c - r_u)}
    # benchmark: how strong is a measured seller-level factor? worst vs best quarter of the seller's OTHER orders' bad rate
    g = R.groupby("seller"); loo = (g.y.transform("sum") - R.y) / (g.y.transform("count") - 1)
    ok = loo.notna(); q = pd.qcut(loo[ok].rank(method="first"), 4, labels=False)
    rate = R[ok].y.groupby(q).mean(); late_rate = R[ok].late.groupby(q).mean()
    out["benchmark_seller_quarter"] = {"bad_rate_best_q": float(rate.iloc[0]), "bad_rate_worst_q": float(rate.iloc[-1]),
                                       "rr_bad_worst_vs_best": float(rate.iloc[-1] / rate.iloc[0]),
                                       "late_rate_best_q": float(late_rate.iloc[0]), "late_rate_worst_q": float(late_rate.iloc[-1]),
                                       "rr_late_worst_vs_best": float(late_rate.iloc[-1] / late_rate.iloc[0])}
    ev = out["e_value_point"]["e_value_halve"]; d = out["oster"]["rmax_1.3x"]["delta_to_halve"]
    out["pass_rules"] = [
        {"id": "B-1 E-value to halve >= 2.0", "pass": bool(ev >= 2.0), "observed": ev},
        {"id": "B-2 Oster delta to halve (Rmax = 1.3 R_c) >= 1", "pass": bool(d >= 1 and out["oster"]["controls_moved_estimate"] == "down"),
         "observed": {"delta": d, "controls_moved_estimate": out["oster"]["controls_moved_estimate"]}}]
    json.dump(out, open(os.path.join(ROOT, "evidence", "sensitivity_report.json"), "w"), indent=1, default=float)
    print(json.dumps(out, indent=1, default=float))
