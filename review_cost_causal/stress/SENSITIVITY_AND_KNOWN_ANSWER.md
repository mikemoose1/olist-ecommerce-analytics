# Two stress tests for the 3,110: a planted answer and a hidden confounder

The pass rules were written before either test ran, in [docs/preregistration_v2.md](../../docs/preregistration_v2.md)
(parts b and c). One rule failed; it is reported as a fail.

## (c) Known-answer test on a copy of the real orders

**Question.** If we plant a known number of extra bad reviews into the real orders, do the existing estimators find it?

The existing harness (`review_cost_causal/harness.py`) does this on fully invented orders. This test keeps the real
94,302 reviewed orders: their real lateness, sellers, categories, months, prices, freight and promised days. Only the
outcome is replaced:

- Each order's baseline chance of a bad review comes from a model fitted on the real on-time orders (seller, category
  and month effects plus price, freight and promised days), clipped to 1% to 95%. The 1% floor clipped 8,713 of the
  94,302 baseline chances (9.2%). Because seller effects are in it, late
  orders start with a higher baseline (10.5%) than on-time ones (8.9%), as in the real data. A method that ignores
  sellers should come out too high.
- Late orders then get a planted effect by days-late bin. Four scenarios: none; half the published V2 effects; the full
  V2 effects; and the full effects applied on the log-odds scale, so the effect differs from order to order.
- 20 random draws per scenario. The six existing specifications run unchanged.

Run: `python review_cost_causal/stress/known_answer_real.py` (about 16 minutes on 4 cores). Results:
`evidence/known_answer_real_report.json`.

**Preferred estimate (V2), mean over 20 draws**

| Scenario | Planted | Found (mean) | Bias | 95% interval covers the planted number |
|---|---|---|---|---|
| No effect | 0 | -11 | -11 reviews | 20 of 20 |
| Half effect | 1,554 | 1,553 | -0.02% | **16 of 20** |
| Full effect | 3,101 | 3,108 | +0.2% | 17 of 20 |
| Full effect, log-odds scale | 3,110 | 3,112 | +0.1% | 20 of 20 |

**All six specifications, bias as a share of the planted number (full effect)**: V2 +0.2%, V1 +0.4%, V3 +0.3%,
V4 +0.2%, V5 +0.2%, and V0 (no seller matching) +1.9%. With no planted effect, V0 finds +45 and the plain late vs
on-time gap finds +96; the seller-matched specifications find between -5 and -13. On the log-odds scenario V4 (same
actual delivery time) is 2.3% low, the other seller-matched specifications are within 0.7%, and V0 is 1.3% high.

**Pass rules**

| Rule | Result |
|---|---|
| C-1. V2, no effect: interval covers 0 in at least 17 of 20 draws, mean within 50 reviews | **Pass** (20 of 20, -11) |
| C-1. V2, half effect: covers in at least 17 of 20, mean within 5% | **Fail** (16 of 20; mean -0.02%) |
| C-1. V2, full effect: covers in at least 17 of 20, mean within 5% | **Pass** (17 of 20, +0.2%) |
| C-2. V2, log-odds scenario: mean within 10% | **Pass** (+0.1%) |
| C-3. An estimator that always returns 0 fails where the planted number is not 0 | **Pass** |

### Finding: rule C-1 failed

- **The average estimate is accurate.** In every scenario the preferred estimate lands on average within 0.2% of the
  planted number. Single draws were off by up to 8%, in the half-effect scenario.
- **The 95% interval is too narrow.** Across the three scenarios with a coverage rule it covered the planted number in
  53 of 60 draws, or 88%, not the 95% it claims. The half-effect scenario covered 16 of 20 draws. The rule needed 17.
- **What to quote.** Do not quote the 3,025 to 3,195 interval on the preferred specification as a 95% range. The README
  quotes the range across specifications, 2,880 to 3,350. That range is a sensitivity band, not a confidence interval,
  and this test did not check its coverage. In these draws the spread of the six estimates contained the planted
  number in only 10 to 16 of 20 draws per scenario, so it is not shown to do better than the interval.
- The rule was set before the run and has not been changed. This is recorded as a fail.

**What this does not test.** The planted confounding is only as strong as the real seller differences among on-time
orders. A hidden cause that sits only inside late orders is part (b).

## (b) How strong would a hidden confounder have to be?

Run: `python review_cost_causal/stress/sensitivity.py` (about 10 seconds). Results: `evidence/sensitivity_report.json`.

**E-value.** Among the 6,366 reviewed late orders, 62.4% left a bad review. The V2 estimate says that without the delay
13.5% would have, a risk ratio of 4.6. To pull the estimate down to half (1,555), a hidden factor would need a risk ratio
of at least **5.1** with both lateness and bad reviews, beyond everything already matched on. To explain the effect away
completely it would need 8.7. Using the low end of the 95% interval instead: 4.6 to halve, 7.9 to remove.

For scale: orders from sellers in the worst quarter for bad reviews on their other orders get bad reviews 2.0 times as
often as orders from the best quarter, and are late 1.7 times as often. That is a strong, measured seller trait, and it
is still well short of 5.1 on both sides. (The seller trait is already removed by the seller matching; it is only a
yardstick.)

**Oster bound.** With a single late flag in place of the day bins: late orders have 53.7 points more bad reviews with no
controls (R-squared 0.168), and 48.3 points with the V2 controls and matching (R-squared 0.220). The controls moved the
estimate down a little and explained a lot more of the variation. If hidden factors mattered as much as the measured
ones (delta = 1) and a full model could reach 1.3 times the current R-squared (0.286), the effect would be 41.4 points.
Halving it would need hidden factors **3.5 times** as important as all the measured ones; removing it, 7.1 times.

The bound depends on that ceiling. If a full model could explain every bad review (R-squared 1), delta 0.30 would halve
it. A 1-2 star review is a single person's choice with a lot of noise no order data can explain, so a ceiling of 1 is not
realistic; 1.3 times is the usual choice (Oster 2019). Both are reported.

**Pass rules**

| Rule | Result |
|---|---|
| B-1. E-value to halve the estimate at least 2.0 | **Pass** (5.1) |
| B-2. Oster delta to halve, ceiling 1.3 x R-squared, at least 1, with the controls moving the estimate down | **Pass** (3.5) |

**Limits.** Both bounds assume the hidden factor works like the measured ones (the E-value on the risk-ratio scale, Oster
in a linear model). The Oster calculation uses the common approximation, not the exact cubic solution. Neither rules out
a confounder; they say how strong it would have to be.
