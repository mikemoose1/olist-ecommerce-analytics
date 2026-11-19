"""Does late delivery cause bad (1-2 star) reviews, and how many extra did it cause on the 6,366 reviewed late orders?

1. Cutoff design at the promised date (regression discontinuity), diagnostics FIRST: a count test for bunching on
   either side of the cutoff, and covariate continuity. 2. Within-seller comparison (seller, category and month fixed
   effects; days-late bins; an on-time trend so the baseline is 'arrived just on time'), seller-clustered errors.
3. Variants, a falsification test and the before/after-delivery split.
Writes evidence/review_cost_causal_report.json and seeds/review_cost_effects.csv (the per-bin effects the dbt model
metric_review_cost_causal multiplies by its own counts).
Usage: python review_cost_causal/analyze.py [--slow]   (--slow adds the logit models: ~30 minutes)"""
import json, os, sys, warnings, numpy as np, pandas as pd, statsmodels.api as sm
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); warnings.filterwarnings("ignore")
import estimators as E
from data import load
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = load(reviewed_only=False); R = load()
out = {"population": {"judged_orders": len(A), "reviewed": len(R), "reviewed_late": int(R.late.sum()), "bad_reviews": int(R.y.sum()),
                      "bad_late": int(R[R.late == 1].y.sum())}}

# ---- 1. cutoff design: diagnostics before any estimate
def density_jump(series, lo, hi, cut=0.5):
    c = series.value_counts().sort_index(); c = c[(c.index >= lo) & (c.index <= hi)]
    dd = c.index.to_numpy(float) - cut; s = (dd > 0).astype(float)
    m = sm.GLM(c.to_numpy(float), np.column_stack([np.ones_like(dd), s, dd, s * dd]), family=sm.families.Poisson()).fit(scale="X2")
    return {"pct_change": float(100 * (np.exp(m.params[1]) - 1)), "p": float(m.pvalues[1]), "window": [lo, hi]}
bd = np.where(A.days_past_promise > 0,
    np.busday_count(pd.to_datetime(A.estimated_delivery_date).values.astype("datetime64[D]"), A.delivered_to_customer_at.values.astype("datetime64[D]")),
    -np.busday_count(A.delivered_to_customer_at.values.astype("datetime64[D]"), pd.to_datetime(A.estimated_delivery_date).values.astype("datetime64[D]")))
out["rd_density"] = {f"{n}_{lo}_{hi}": density_jump(s, lo, hi) for n, s in (("calendar", A.days_past_promise), ("business", pd.Series(bd)))
                     for lo, hi in ((-5, 6), (-3, 4), (-8, 9))}
out["rd_density_passed"] = all(v["p"] > 0.05 for v in out["rd_density"].values())
R["xd"] = R.days_past_promise - 0.5
g = R.groupby("seller")
R["seller_loo_bad"] = (g.y.transform("sum") - R.y) / (g.y.transform("count") - 1)
R["cat_base_bad"] = R.groupby("category").y.transform("mean"); R["state_base_bad"] = R.groupby("ship_to_state").y.transform("mean")
R["promise_friday"] = (pd.to_datetime(R.estimated_delivery_date).dt.day_of_week == 4).astype(float)
cov = {}
for c in ["lprice", "lfreight", "promised_days", "seller_loo_bad", "cat_base_bad", "state_base_bad", "n_items", "promise_friday"]:
    d = R[R[c].notna()]; r = E.rd_local_linear(d.xd, d[c].astype(float), d.seller, 3)
    cov[c] = {"jump": r["jump"], "lo": r["lo"], "hi": r["hi"], "smooth": bool(r["lo"] <= 0 <= r["hi"])}
fit = R[R.days_past_promise <= -4]; cols = ["lprice", "lfreight", "promised_days", "seller_loo_bad", "cat_base_bad", "state_base_bad", "n_items"]
lm = sm.Logit(fit.y.astype(float), sm.add_constant(fit[cols].fillna(0).astype(float))).fit(disp=0)
R["pred_bad"] = lm.predict(sm.add_constant(R[cols].fillna(0).astype(float)))
r = E.rd_local_linear(R.xd, R.pred_bad, R.seller, 3); cov["INDEX predicted bad-review risk"] = {"jump": r["jump"], "lo": r["lo"], "hi": r["hi"], "smooth": bool(r["lo"] <= 0 <= r["hi"])}
out["rd_covariates"] = cov
out["rd_review_rate_jump"] = E.rd_local_linear(A.days_past_promise - .5, A.reviewed.astype(float), A.seller, 3)
# estimates (diagnostic of SHAPE only: the density check failed, so not used for the count)
out["rd_estimates"] = {f"days_pm{h}": E.rd_local_linear(R.xd, R.y, R.seller, h, slopes=(h > 1)) for h in (1, 2, 3)}
out["rd_estimates"]["donut_drop_d0_d1"] = E.rd_local_linear(R.xd, R.y, R.seller, 4.01, donut=1.0, kernel="uniform")
for c in (-5, 10):
    d = R[R.days_past_promise <= 0] if c < 0 else R[R.days_past_promise >= 1]
    out["rd_estimates"][f"placebo_{c:+d}"] = E.rd_local_linear(d.days_past_promise - 0.5, d.y, d.seller, 3, cutoff=c)
for h in (3, 5):
    d = R[np.abs(R.xd) < h]; xv = d.xd.to_numpy(float); t = (xv > 0).astype(float); y = d.y.to_numpy(float)
    X = np.column_stack([np.ones(len(d)), t, xv, t * xv]); b = np.linalg.lstsq(X, y, rcond=None)[0]
    V = E._cluster_vcov(X, y - X @ b, d.seller.to_numpy())
    out["rd_estimates"][f"kink_pm{h}"] = {"left_slope_pp_per_day": 100 * b[2], "slope_change_pp_per_day": 100 * b[3], "se": 100 * float(np.sqrt(V[3, 3]))}

# ---- 2. within-seller comparison
R["product"] = R.product_id; R["state"] = R.ship_to_state
R["deliv_days_cap"] = (R.delivered_to_customer_at.dt.normalize() - R.purchased_at.dt.normalize()).dt.days.clip(upper=60)
V = {"V2_preferred": dict(fe_cols=("seller", "category", "ym"), early_slope=True),
     "V1_baseline_all_on_time": dict(fe_cols=("seller", "category", "ym")),
     "V3_product_fe": dict(fe_cols=("seller", "product", "ym"), early_slope=True),
     "V4_same_actual_delivery_time": dict(fe_cols=("seller", "category", "ym", "deliv_days_cap")),
     "V5_plus_state_fe": dict(fe_cols=("seller", "category", "ym", "state"), early_slope=True),
     "V0_no_seller_fe": dict(fe_cols=("category", "ym"))}
out["naive"] = E.naive_gap(R)
out["fe"] = {k: E.fe_lpm_att(R, **kw) for k, kw in V.items()}

# ---- 3. falsification and mechanism
O = R[(R.late == 0) & R.delivered_to_carrier_at.notna() & R.ship_limit_at.notna()].copy()
O["handoff_late"] = (O.delivered_to_carrier_at > O.ship_limit_at).astype(float); O["early"] = np.clip(np.minimum(O.x, 0), -30, 0)
c2 = ["handoff_late", "early", "lprice", "lfreight", "promised_days"]
M = E.demean(np.column_stack([O.y.to_numpy(float), O[c2].to_numpy(float)]), [pd.factorize(O[c])[0] for c in ("seller", "category", "ym")])
b = np.linalg.lstsq(M[:, 1:], M[:, 0], rcond=None)[0]; se = float(np.sqrt(E._cluster_vcov(M[:, 1:], M[:, 0] - M[:, 1:] @ b, O.seller.to_numpy())[0, 0]))
out["falsification_late_handoff_on_time_pp"] = {"pp": 100 * b[0], "lo": 100 * (b[0] - 1.96 * se), "hi": 100 * (b[0] + 1.96 * se), "n_late_handoffs": int(O.handoff_late.sum())}
before = R.review_before_delivery.fillna(False).astype(bool)
out["mechanism"] = {n: E.fe_lpm_att(R.assign(y=((R.y == 1) & m).astype(int)), early_slope=True)["extra"]
                    for n, m in (("bad_written_before_delivery", before), ("bad_written_after_delivery", ~before))}
if "--slow" in sys.argv:
    out["mundlak_logit_V2"] = E.mundlak_logit_att(R, early_slope=True, boot=100, seed=11)
    out["conditional_logit"] = E.conditional_logit(R)

p = out["fe"]["V2_preferred"]
# The honest range is the spread of the point estimates across the six specifications (V4 lowest, V0 highest); the 95%
# interval on the preferred spec alone only reflects sampling noise within that one specification.
spec_extras = [v["extra"] for v in out["fe"].values()]
f_ = out["falsification_late_handoff_on_time_pp"]; n_late_rev = out["population"]["reviewed_late"]
out["headline"] = {"extra_bad_reviews": p["extra"], "ci95": [p["lo"], p["hi"]], "share_of_bad_reviews_pct": 100 * p["extra"] / out["population"]["bad_reviews"],
                   "range_across_specifications": [min(spec_extras), max(spec_extras)],
                   "hidden_seller_bias_if_in_every_late_order": {
                       "points": [f_["pp"], f_["hi"]], "reviews": [f_["pp"] / 100 * n_late_rev, f_["hi"] / 100 * n_late_rev],
                       "share_of_extra_pct": [100 * f_["pp"] / 100 * n_late_rev / p["extra"], 100 * f_["hi"] / 100 * n_late_rev / p["extra"]]},
                   # history: the association figure the story printed before this estimate replaced it (PR #7)
                   "earlier_story_value_association": 3335, "within_10pct_of_earlier_story_value": bool(abs(p["extra"] / 3335 - 1) <= 0.10)}
json.dump(out, open(os.path.join(ROOT, "evidence", "review_cost_causal_report.json"), "w"), indent=1, default=float)
edges = {"late_d1": (1, 1), "late_d2": (2, 2), "late_d3": (3, 3), "late_d4_6": (4, 6), "late_d7_13": (7, 13), "late_d14p": (14, 9999)}
pd.DataFrame([{"days_late_bin": k, "min_days_late": edges[k][0], "max_days_late": edges[k][1], "effect_on_bad_share": round(v, 6),
               "effect_se": round(p["bin_se"][k], 6), "reviewed_late_orders_at_estimation": p["bin_counts"][k]} for k, v in p["bins"].items()]
             ).to_csv(os.path.join(ROOT, "seeds", "review_cost_effects.csv"), index=False)
print(json.dumps(out["headline"]), "| density passed:", out["rd_density_passed"])
