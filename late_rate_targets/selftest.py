#!/usr/bin/env python3
"""Prove the proofs can fail. Each check in proofs.py is fed deliberately broken input and must report FAILURE;
the break-point search must find a planted break and must not invent one in a straight line.
  python late_rate_targets/selftest.py          (needs a built warehouse for the real monthly counts)
Exit 1 if any broken input is accepted."""
import os, sys
import duckdb, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import spc, proofs, breakpoint as bp

ROOT = os.path.dirname(HERE)
con = duckdb.connect(os.environ.get("OLIST_DB_PATH", os.path.join(ROOT, "olist.duckdb")), read_only=True)
m = con.execute("select * from metrics.metric_late_rate_control_chart order by year_month").df()
months, k, n = list(m.year_month), m.late_orders.values.astype(float), m.orders.values.astype(float)
base = spc.fit_laney(k, n)["centre"]
results = []


def expect(name, condition, detail=""):
    results.append(condition)
    print(("PASS " if condition else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


S = 400
# 1. sound inputs pass, so a failure below means the check, not the setup
ok, r = proofs.check_planted_month_is_flagged(n, base, "laney", seeds=S)
expect("control: planted month check passes with the real detector", ok, f"{r['planted_flagged']:.0%}")
ok, r = proofs.check_pure_noise_is_quiet(n, base, "laney", seeds=S)
expect("control: pure-noise check passes with the real detector", ok, f"{r['series_any_flag']:.1%}")

# 2. broken detectors must be rejected
blind = lambda kk, nn: spc.apply_limits(spc.fit_plain(kk, nn)["centre"], 10.0, kk, nn)["signal"]       # limits 10x too wide
ok, r = proofs.check_planted_month_is_flagged(n, base, "laney", detector=blind, seeds=S)
expect("planted-month check REJECTS a detector with limits 10x too wide", not ok, f"flagged only {r['planted_flagged']:.0%}")
jumpy = lambda kk, nn: spc.apply_limits(spc.fit_plain(kk, nn)["centre"], 0.33, kk, nn)["signal"]        # limits 1 sigma instead of 3
ok, r = proofs.check_pure_noise_is_quiet(n, base, "laney", detector=jumpy, seeds=S)
expect("pure-noise check REJECTS a detector with 1-sigma limits", not ok, f"{r['series_any_flag']:.0%} of noise series flagged")

# 3. holdout: if March 2018 were an ordinary month, it must NOT be flagged
k_calm = k.copy(); i = months.index("2018-03"); k_calm[i] = round(n[i] * base)
ok, r = proofs.check_holdout_flags_month(months, k_calm, n, [x for x in months if x < "2018"], "2018-03")
expect("holdout check REJECTS a March 2018 that is an ordinary month", not ok, f"rate {k_calm[i] / n[i]:.2%} vs limit {r['months']['2018-03']['ucl']:.2%}")
ok, _ = proofs.check_holdout_flags_month(months, k, n, [x for x in months if x < "2018"], "2018-03")
expect("control: holdout check passes on the real data", ok)

# 4. dispersion test: chance-only 'real' counts must not pass as loud
rng = np.random.default_rng(9)
chance_k = rng.binomial(n.astype(int), base)
ok, r = proofs.check_dispersion_test_discriminates(n, base, chance_k, seeds=500)
expect("dispersion check REJECTS counts that are pure chance", not ok, f"p = {r['real']['p_value']:.2f}")

# 5. break-point search: finds a planted break, invents none in a straight line
x = np.arange(-30, 31, dtype=float); nn = np.full(len(x), 1500.0); grid = list(range(-20, 26))
truth = bp.logit_predict(x, (-1, 6), np.array([-2.3, 0.0, 0.5, -0.5]))
found, p_planted = [], []
rng = np.random.default_rng(21)
for _ in range(15):
    y = rng.binomial(nn.astype(int), truth).astype(float)
    kn, _, _ = bp.logit_search(x, y, nn, grid, 2); found.append(kn)
exact = np.mean([abs(a - (-1)) <= 1 and abs(b - 6) <= 1 for a, b in found])
expect("break search recovers a planted break pair (-1, +6) within 1 day in 15 of 15 simulated datasets", exact == 1.0, f"{exact:.0%}")
straight = bp.logit_predict(x, (), np.array([-2.3, 0.01]))
fp = 0
for s in range(30):
    y = np.random.default_rng(100 + s).binomial(nn.astype(int), straight).astype(float)
    fp += bp.davies_logit(x, y, nn, grid, 60, s)["p_value"] < 0.05
expect("break test invents no break in a straight line (false positives at 5% in 30 datasets: 4 or fewer)", fp <= 4, f"{fp} of 30")
y = np.random.default_rng(5).binomial(nn.astype(int), truth).astype(float)
expect("break test accepts the planted break", bp.davies_logit(x, y, nn, grid, 60, 1)["p_value"] < 0.05)
expect("control: planted-break claim is REJECTED on straight-line data", bp.davies_logit(x, np.random.default_rng(7).binomial(nn.astype(int), straight).astype(float), nn, grid, 60, 1)["p_value"] >= 0.05)

print(f"\n{sum(results)}/{len(results)} selftest checks passed")
sys.exit(0 if all(results) else 1)
