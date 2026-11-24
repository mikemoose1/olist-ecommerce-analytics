"""(a) Do missing reviews bias the ~3,110 estimate? (pre-registered in docs/preregistration_v2.md)

Uses every judged order (delivered, with a promised date), reviewed or not. Compares review rates for late and on-time
orders, re-estimates the preferred (V2) specification with inverse-probability weights, and checks that any shift is
not caused by the weighting itself. Writes evidence/missing_reviews_report.json. About 6 minutes.
Usage: python review_cost_causal/stress/missing_reviews.py
"""
import json, os, sys
import numpy as np, pandas as pd, duckdb
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import make_pipeline
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import E, ROOT, load, published  # noqa: E402
from data import DB  # noqa: E402

V2 = dict(fe_cols=("seller", "category", "ym"), extra=("lprice", "lfreight", "promised_days"), early_slope=True)
N_SHUFFLE = 50
SEED = 20261123


def weighted_demean(arr, fes, w, tol=1e-10, iters=500):
    """Like estimators.demean, but removes WEIGHTED group means. With w = 1 it is the same calculation."""
    out = np.array(arr, float, copy=True)
    sw = [np.bincount(f, w) for f in fes]
    for _ in range(iters):
        prev = out.copy()
        for f, s in zip(fes, sw):
            sums = np.zeros((s.size, out.shape[1])); np.add.at(sums, f, out * w[:, None])
            out -= (sums / np.maximum(s, 1e-300)[:, None])[f]
        if np.max(np.abs(out - prev)) < tol: break
    return out


def weighted_v2(d, w, count_rows=None):
    """V2 with weights: weighted fixed-effects regression on days-late bins, seller-clustered errors. The count is the
    per-bin effects times the late orders in `count_rows` (default: the late rows of d)."""
    D = E.late_bins(d.x)
    C = np.column_stack([d[list(V2["extra"])].to_numpy(float), np.clip(np.minimum(d.x.to_numpy(float), 0), -30, 0)])
    X = np.column_stack([D, C]); y = d.y.to_numpy(float)
    M = weighted_demean(np.column_stack([y, X]), [pd.factorize(d[c])[0] for c in V2["fe_cols"]], w)
    yd, Xd = M[:, 0], M[:, 1:]
    sw = np.sqrt(w)
    beta = np.linalg.lstsq(Xd * sw[:, None], yd * sw, rcond=None)[0]
    V = E._cluster_vcov(Xd, yd - Xd @ beta, d.seller.to_numpy(), w)
    nb = D.shape[1]; b = beta[:nb]; Vb = V[:nb, :nb]
    rows = d if count_rows is None else count_rows
    counts = E.late_bins(rows.x)[rows.late.to_numpy() == 1].sum(0)
    extra = float(counts @ b); se = float(np.sqrt(counts @ Vb @ counts))
    return {"extra": extra, "lo": extra - E.Z * se, "hi": extra + E.Z * se, "bins": dict(zip([n for *_, n in E.BINS], map(float, b))),
            "late_rows_counted": int(counts.sum())}


def review_propensity(A):
    """Chance an order gets a review, from everything known about it (logistic, mild L2 penalty for rare categories)."""
    A = A.copy(); A["early"] = np.clip(np.minimum(A.x, 0), -30, 0)
    B = pd.DataFrame(E.late_bins(A.x), columns=[n for *_, n in E.BINS], index=A.index)
    X = pd.concat([B, A[["early", "lprice", "lfreight", "promised_days", "category", "ym", "ship_to_state"]]], axis=1)
    num = list(B.columns) + ["early", "lprice", "lfreight", "promised_days"]
    pre = ColumnTransformer([("num", StandardScaler(), num),
                             ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), ["category", "ym", "ship_to_state"])])
    m = make_pipeline(pre, LogisticRegression(C=1.0, max_iter=5000))
    m.fit(X, A.reviewed.to_numpy())
    return m.predict_proba(X)[:, 1]


if __name__ == "__main__":
    pub = published()["fe"]["V2_preferred"]
    A = load(reviewed_only=False)
    A["y"] = (A.review_score <= 2).astype(float)            # only used for reviewed rows
    rv = A.reviewed == 1; R = A[rv].reset_index(drop=True)
    con = duckdb.connect(DB, read_only=True)
    n_all = con.sql("select count(*) from marts.fct_orders").fetchall()[0][0]
    out = {"population": {"orders_in_raw_csv": int(n_all), "judged_orders": len(A), "not_judged_no_delivery_or_promise": int(n_all - len(A)),
                          "judged_reviewed": int(rv.sum()), "judged_unreviewed": int((~rv).sum()),
                          "late_judged": int(A.late.sum()), "late_unreviewed": int(((A.late == 1) & ~rv).sum())}}
    # 1. review rate gap
    rl, ro = A[A.late == 1].reviewed.mean(), A[A.late == 0].reviewed.mean()
    se = np.sqrt(rl * (1 - rl) / (A.late == 1).sum() + ro * (1 - ro) / (A.late == 0).sum())
    fe = E.fe_lpm_att(A.assign(y=A.reviewed), use_bins=False, early_slope=False)
    out["review_rate"] = {"late_pct": 100 * rl, "on_time_pct": 100 * ro, "gap_pp": 100 * (rl - ro),
                          "gap_ci95_pp": [100 * (rl - ro - E.Z * se), 100 * (rl - ro + E.Z * se)],
                          "within_seller_category_month_gap_pp": fe["att_pp"],
                          "within_ci95_pp": [fe["att_pp"] - 100 * E.Z * fe["bin_se"]["late"], fe["att_pp"] + 100 * E.Z * fe["bin_se"]["late"]]}
    # 2-3. inverse-probability weights and the weighted V2
    p = review_propensity(A); w = 1 / p[rv.to_numpy()]
    ess = w.sum() ** 2 / (w ** 2).sum()
    unweighted = E.fe_lpm_att(R, **V2)
    ipw = weighted_v2(R, w)
    out["weights"] = {"min": float(w.min()), "max": float(w.max()), "mean": float(w.mean()), "effective_sample_size": float(ess),
                      "propensity_min": float(p.min()), "propensity_mean": float(p.mean())}
    out["v2_unweighted"] = {"extra": unweighted["extra"], "lo": unweighted["lo"], "hi": unweighted["hi"]}
    out["v2_ipw"] = ipw
    # W-1 code check, W-2 shuffle check, W-3 trimming
    unit = weighted_v2(R, np.ones(len(R)))
    rng = np.random.default_rng(SEED)
    shifts = [abs(weighted_v2(R, rng.permutation(w))["extra"] - unweighted["extra"]) for _ in range(N_SHUFFLE)]
    lo_q, hi_q = np.quantile(w, [0.01, 0.99]); trimmed = weighted_v2(R, np.clip(w, lo_q, hi_q))
    shift = ipw["extra"] - unweighted["extra"]
    out["artifact_checks"] = {
        "W-1 unit weights reproduce V2": {"extra": unit["extra"], "diff": unit["extra"] - unweighted["extra"], "pass": bool(abs(unit["extra"] - unweighted["extra"]) <= 1)},
        "W-2 shuffled weights": {"n": N_SHUFFLE, "abs_shift_p95": float(np.quantile(shifts, 0.95)), "abs_shift_max": float(max(shifts)),
                                  "real_abs_shift": abs(shift), "real_shift_beyond_p95": bool(abs(shift) > np.quantile(shifts, 0.95))},
        "W-3 trimmed weights": {"extra": trimmed["extra"], "pct_diff": 100 * (trimmed["extra"] / ipw["extra"] - 1),
                                "pass": bool(abs(trimmed["extra"] / ipw["extra"] - 1) <= 0.01)}}
    # 4. worst-case bounds: every unreviewed order counted as bad, then as not bad
    U = A.copy(); bounds = {}
    for name, val in (("all_unreviewed_bad", 1.0), ("all_unreviewed_not_bad", 0.0)):
        U["y"] = np.where(rv, A.y, val)
        r_all = E.fe_lpm_att(U, **V2)                                     # counts every judged late order
        bins = np.array([r_all["bins"][n] for *_, n in E.BINS])
        comparable = float(E.late_bins(R.x)[R.late.to_numpy() == 1].sum(0) @ bins)   # same 6,366 reviewed late orders
        bounds[name] = {"extra_on_all_judged_late": r_all["extra"], "extra_on_6366_reviewed_late": comparable}
    out["worst_case_bounds"] = bounds
    lo_r, hi_r = pub_range = published()["headline"]["range_across_specifications"]
    within5 = abs(ipw["extra"] / pub["extra"] - 1) <= 0.05
    out["pass_rules"] = [
        {"id": "A-1 IPW estimate within 5% of 3,110 and inside the six-specification range", "pass": bool(within5 and lo_r <= ipw["extra"] <= hi_r),
         "observed": {"ipw": ipw["extra"], "pct_shift": 100 * shift / pub["extra"], "range": pub_range}},
        {"id": "A-2 both worst-case bounds inside the six-specification range", "pass": bool(all(lo_r <= b[k] <= hi_r for b in bounds.values() for k in b)),
         "observed": bounds}]
    if not out["pass_rules"][0]["pass"]:
        real = out["artifact_checks"]["W-2 shuffled weights"]["real_shift_beyond_p95"] and out["artifact_checks"]["W-1 unit weights reproduce V2"]["pass"] and out["artifact_checks"]["W-3 trimmed weights"]["pass"]
        out["interpretation"] = "real missing-review bias" if real else "weighting noise"
    else:
        out["interpretation"] = "no material missing-review bias"
    json.dump(out, open(os.path.join(ROOT, "evidence", "missing_reviews_report.json"), "w"), indent=1, default=float)
    print(json.dumps({k: out[k] for k in ("population", "review_rate", "weights", "v2_ipw", "artifact_checks", "worst_case_bounds", "pass_rules", "interpretation")}, indent=1, default=float))
