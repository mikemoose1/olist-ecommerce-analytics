"""Known-answer harness. Every check is run on the proper method (must PASS) and on a deliberately broken
method (must FAIL), so we know each check can fail. Writes evidence/review_cost_harness.json. Takes about 20 minutes."""
import json, os, sys, time, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synth import make
import estimators as E

def covers(r, t, lo="lo", hi="hi"): return r[lo] <= t <= r[hi]
def zero_in(r): return r["lo"] <= 0 <= r["hi"]
always_zero = {"jump": 0.0, "lo": 0.0, "hi": 0.0, "extra": 0.0}

rows = []
def rec(check, method, passed, expect, detail):
    ok = passed == expect
    rows.append({"check": check, "method": method, "passed": bool(passed), "expected": "PASS" if expect else "FAIL", "as_expected": bool(ok), "detail": detail})
    print(("OK " if ok else "XX ") + f"{check:42s} {method:34s} {'PASS' if passed else 'FAIL'}  {detail}")

P, tP = make(1, effect=True); N0, tN = make(2, effect=False)
print("truth planted:", tP, " naive planted:", E.naive_gap(P), " naive null:", E.naive_gap(N0))

# C1 RD recovers the planted jump
for h in (1, 2, 3):
    r = E.rd_local_linear(P.x, P.y, P.seller, h); rec(f"C1 RD recovers planted jump h={h}", "local linear", covers(r, tP["jump"]), True, f"jump={r['jump']:.3f} [{r['lo']:.3f},{r['hi']:.3f}] truth={tP['jump']:.3f}")
rec("C1 RD recovers planted jump h=2", "BROKEN always-zero", covers(always_zero, tP["jump"]), False, "returns 0")
r = E.rd_local_linear(P.x, P.y, P.seller, 8, slopes=False); rec("C1 RD recovers planted jump h=8", "BROKEN no-slope mean diff", covers(r, tP["jump"]), False, f"jump={r['jump']:.3f}")

# C1b coverage of the planted jump over 20 seeds (h=2)
cov = 0
for s in range(200, 220):
    d, t = make(s, effect=True); cov += covers(E.rd_local_linear(d.x, d.y, d.seller, 2), t["jump"])
rec("C1b RD 95% CI covers planted jump >= 80% of 20 seeds", "local linear", cov / 20 >= .8, True, f"covered {cov}/20")

# C2 RD finds nothing when lateness does nothing (confounded null), false-positive rate over seeds
fp = {"local linear": 0, "BROKEN no-slope mean diff": 0}; S = 40
for s in range(100, 100 + S):
    d, _ = make(s, effect=False)
    fp["local linear"] += not zero_in(E.rd_local_linear(d.x, d.y, d.seller, 2))
    fp["BROKEN no-slope mean diff"] += not zero_in(E.rd_local_linear(d.x, d.y, d.seller, 8, slopes=False))
for m, v in fp.items():
    rec("C2 RD null: false alarms <= 10% of 40 seeds", m, v / S <= 0.10, m == "local linear", f"false alarms {v}/{S}")

# C3 placebo cutoffs at -5 and +10 days, on planted data (one side only)
for c in (-5, 10):
    r = E.rd_placebo(P.x, P.y, P.seller, c, 2); rec(f"C3 placebo cutoff {c:+d} shows no jump", "local linear", zero_in(r), True, f"jump={r['jump']:.3f} [{r['lo']:.3f},{r['hi']:.3f}]")
xs = P.x.to_numpy(); side = xs < 0
r = E.rd_local_linear(xs[side], P.y[side], P.seller[side], 8, cutoff=-5, slopes=False)
rec("C3 placebo cutoff -5 shows no jump", "BROKEN no-slope mean diff h=8", zero_in(r), False, f"jump={r['jump']:.3f} [{r['lo']:.3f},{r['hi']:.3f}]")
side = xs >= 0
r = E.rd_local_linear(xs[side], P.y[side], P.seller[side], 10, cutoff=10, slopes=False, kernel="uniform")
rec("C3 placebo cutoff +10 shows no jump", "BROKEN no-slope mean diff h=10", zero_in(r), False, f"jump={r['jump']:.3f} [{r['lo']:.3f},{r['hi']:.3f}]")

# C4 FE recovers the planted extra-bad-review count; C5 FE finds ~0 on confounded null
r = E.fe_lpm_att(P); rec("C4 FE-LPM recovers planted extra count", "seller+cat+month FE, bins", covers(r, tP["extra"]), True, f"{r['extra']:.0f} [{r['lo']:.0f},{r['hi']:.0f}] truth={tP['extra']:.0f}")
rb = E.fe_lpm_att(P, fe_cols=("category", "ym")); rec("C4 FE-LPM recovers planted extra count", "BROKEN no seller FE", covers(rb, tP["extra"]), False, f"{rb['extra']:.0f} [{rb['lo']:.0f},{rb['hi']:.0f}]")
r = E.fe_lpm_att(P, early_slope=True); rec("C4b FE-LPM + on-time slope recovers planted", "V2 spec (used for the real number)", covers(r, tP["extra"]), True, f"{r['extra']:.0f} [{r['lo']:.0f},{r['hi']:.0f}] truth={tP['extra']:.0f}")
# C5b: a single 95% CI misses zero 5% of the time by design (seed 2 does), so the gate is the false-alarm RATE over 20 seeds
fa = {"V2 spec (used for the real number)": [], "V1 spec": [], "BROKEN no seller FE": []}
for s_ in range(400, 420):
    d_, _ = make(s_, effect=False)
    fa["V2 spec (used for the real number)"].append(not zero_in(E.fe_lpm_att(d_, early_slope=True)))
    fa["V1 spec"].append(not zero_in(E.fe_lpm_att(d_)))
    fa["BROKEN no seller FE"].append(not zero_in(E.fe_lpm_att(d_, fe_cols=("category", "ym"))))
for m_, v_ in fa.items():
    rec("C5b FE-LPM null: false alarms <= 10% of 20 seeds", m_, np.mean(v_) <= .10, not m_.startswith("BROKEN"), f"false alarms {sum(v_)}/20")
r = E.fe_lpm_att(N0); rec("C5 FE-LPM null: CI includes 0", "seller+cat+month FE, bins", zero_in(r), True, f"{r['extra']:.0f} [{r['lo']:.0f},{r['hi']:.0f}] naive={E.naive_gap(N0)['extra']:.0f}")
rb = E.fe_lpm_att(N0, fe_cols=("category", "ym")); rec("C5 FE-LPM null: CI includes 0", "BROKEN no seller FE", zero_in(rb), False, f"{rb['extra']:.0f} [{rb['lo']:.0f},{rb['hi']:.0f}]")

# C6 Mundlak logit (point check, +-10% of truth / |null| < 10% of naive)
m = E.mundlak_logit_att(P); rec("C6 Mundlak logit within 10% of planted", "Mundlak logit", abs(m["extra"] / tP["extra"] - 1) < .10, True, f"{m['extra']:.0f} truth={tP['extra']:.0f}")
nulls = [make(s, effect=False)[0] for s in range(300, 308)]
mu0 = np.mean([E.mundlak_logit_att(d)["extra"] for d in nulls]); nv = np.mean([E.naive_gap(d)["extra"] for d in nulls])
rec("C6 Mundlak logit null: mean of 8 seeds < 10% of naive", "Mundlak logit", abs(mu0) < .10 * nv, True, f"mean {mu0:.0f} vs naive {nv:.0f}")
mb = np.mean([E.naive_gap(d)["extra"] for d in nulls])
rec("C6 Mundlak logit null: mean of 8 seeds < 10% of naive", "BROKEN naive gap (no controls)", abs(mb) < .10 * nv, False, f"mean {mb:.0f}")
ma = 0.0
rec("C6 Mundlak logit within 10% of planted", "BROKEN always-zero", abs(ma / tP["extra"] - 1) < .10, False, "returns 0")

# C7 conditional logit: OR CI excludes 1 when planted, includes 1 under null
c1 = E.conditional_logit(P); rec("C7 cond. logit detects planted (OR>1)", "conditional logit by seller", c1["or_lo"] > 1, True, f"OR={c1['or']:.2f} [{c1['or_lo']:.2f},{c1['or_hi']:.2f}]")
cb = {"or_lo": 1.0, "or": 1.0}; rec("C7 cond. logit detects planted (OR>1)", "BROKEN always OR=1", cb["or_lo"] > 1, False, "returns 1")
c0 = E.conditional_logit(N0); rec("C7 cond. logit null: OR CI includes 1", "conditional logit by seller", c0["or_lo"] <= 1 <= c0["or_hi"], True, f"OR={c0['or']:.2f} [{c0['or_lo']:.2f},{c0['or_hi']:.2f}]")
import statsmodels.api as sm
lb = sm.Logit(N0.y.to_numpy(float), sm.add_constant(N0[["late"]].astype(float))).fit(disp=0); b, se = lb.params["late"], lb.bse["late"]
rec("C7 cond. logit null: OR CI includes 1", "BROKEN plain logit, no seller conditioning", np.exp(b - 1.96 * se) <= 1 <= np.exp(b + 1.96 * se), False, f"OR={np.exp(b):.2f}")

json.dump({"truth_planted": tP, "rows": rows, "all_as_expected": all(r["as_expected"] for r in rows)}, open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evidence", "review_cost_harness.json"), "w"), indent=1)
print("ALL AS EXPECTED:", all(r["as_expected"] for r in rows))
