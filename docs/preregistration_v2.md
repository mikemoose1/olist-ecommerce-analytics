# Pre-registration v2: stress tests for the late-delivery study

Written 23 November 2026 (US Eastern), before any of the analyses below were run. Base commit: `5e37adb` (main).
The pass rules here are fixed. If a result misses a rule, it is reported as a miss; the rule is not edited afterwards.
"Nothing passes" is an allowed outcome.

What these tests check: whether the headline (late delivery caused about 3,110 extra 1-2 star reviews, the V2
within-seller estimate in `evidence/review_cost_causal_report.json`) holds up against three threats it has not faced,
whether the delivery date works better as a predicted range plus a separate rule, and whether the dashboard's tables are
checked at build time. No new topics.

Already known before writing this (from the published report, not new runs): 94,931 judged orders, 94,302 of them
reviewed, 6,366 reviewed late orders, V2 estimate 3,110 (95% interval 3,025 to 3,195), six-specification range about
2,880 to 3,350.

Choices left to Mike, not made by any test here: which promise percentile (or cost weight) to ship, and whether a
1-day guardrail is the right business limit.

## Order of work

(c) known-answer test first, so the estimators are trusted before they are reused; then (a) and (b); then (e); then (d).
Each lands as its own pull request.

## (c) Known-answer test on a copy of the real orders

**Set-up.** Take the 94,302 reviewed judged orders with their real lateness (days past promise), sellers, categories,
months, prices, freight and promised days. Replace the outcome with a simulated one whose cause is known:

- Baseline chance of a bad review for each order, `p0`: the fitted value of a linear model on the real on-time orders
  only (seller, category and month effects plus price, freight and promised days), clipped to [0.01, 0.95]. Because
  seller effects are in `p0`, sellers who are late more often can also have more bad reviews, as in the real data.
- Planted effect for late orders, by days-late bin. Scenarios:
  - S0 null: no effect.
  - S1 half: half the published V2 bin effects, added to `p0`.
  - S2 full: the published V2 bin effects, added to `p0`.
  - S3 logit: the same bin effects applied on the log-odds scale (so the effect differs by order), sized so the
    average added chance is close to S2. The planted truth is computed order by order.
- Planted truth = the sum over late orders of (chance with the effect minus chance without), after clipping.
- 20 seeds per scenario. The outcome is drawn from those chances.

**Estimators run.** All six existing fixed-effects specifications (`fe_lpm_att` with the arguments used in
`review_cost_causal/analyze.py`), unchanged, plus the naive late vs on-time gap as a reference.

**Pass rules.**
- C-1. V2 (preferred) in S0, S1, S2: its 95% interval covers the planted truth in at least 17 of 20 seeds, and the mean
  estimate over seeds is within 5% of the planted truth (S0: within 50 reviews of zero).
- C-2. V2 in S3: mean estimate within 10% of the planted truth. (The linear model is not the true model here.)
- C-3. The check can fail: an estimator that always returns 0 must fail C-1 in S1 and S2.
- Reported, no pass rule: coverage and bias for the other five specifications and the naive gap.

## (a) Missing reviews

**Population.** The 94,931 judged orders (delivered, with a promised date), reviewed or not. Undelivered orders have no
days-late value and stay out; their count is reported.

**Steps.**
1. Review rate for late vs on-time orders, with a 95% interval for the gap, plain and within seller, category and month
   (linear model, seller-clustered errors).
2. Chance of being reviewed, from a logistic model on everything known about the order: days-late bins, days early
   (capped at 30), price, freight, promised days, category, month and customer state. Inverse-probability weights for
   reviewed orders = 1 / that chance.
3. Re-estimate V2 with those weights (weighted fixed-effects regression, same specification, seller-clustered errors).
   The count is the weighted per-bin effects times the same 6,366 reviewed late orders, so it is comparable with 3,110.
4. Worst-case bounds: re-run V2 with every unreviewed order counted as a bad review, then as not bad.

**Artifact checks (so a shift is not caused by the weighting itself).**
- W-1. Code check: the weighted code with every weight set to 1 reproduces 3,110 to within 1 review.
- W-2. Shuffle check: 50 runs with the real weights shuffled at random across reviewed orders. Shuffled weights carry no
  information about who gets reviewed, so they show how far weighting alone moves the estimate.
- W-3. Trimmed weights (capped at the 1st and 99th percentile) give an estimate within 1% of the untrimmed one.
- Effective sample size of the weights is reported.

**Pass rules.**
- A-1 (no material missing-review bias): the weighted estimate is within 5% of 3,110 (2,955 to 3,266) and inside the
  six-specification range.
- A-2 (worst-case bounds stay inside the published range): both worst-case estimates inside 2,880 to 3,350.
- Interpretation if A-1 fails: if the shift is also larger than the 95th percentile of the shuffle-check shifts and W-1
  and W-3 hold, it is called real missing-review bias and the weighted figure is reported next to 3,110. Otherwise it is
  called weighting noise.

## (b) Sensitivity to an unmeasured confounder

**E-value.** On reviewed late orders: observed bad-review rate `p1`, and the no-lateness rate `p0 = p1 - 3,110 / 6,366`.
Risk ratio `RR = p1 / p0`. The E-value to bring the estimate to half (1,555) uses `RR / RR_half`, where `RR_half` is the
risk ratio when the effect is halved; formula `E = RR' + sqrt(RR' * (RR' - 1))`. Also reported: the E-value to explain
the effect away fully, and the same for the lower end of the 95% interval.

**Oster-style bound.** Single late indicator in place of the bins (so there is one coefficient). Uncontrolled model:
bad review on late only. Controlled model: the V2 controls and fixed effects. R-squared includes the fixed effects.
`delta` needed to move the coefficient to half its controlled value, from the approximation
`beta* = beta_c - delta * (beta_u - beta_c) * (Rmax - R_c) / (R_c - R_u)`, with `Rmax = min(1.3 * R_c, 1)`, and also
with `Rmax = 1` reported. Also `delta` for a coefficient of 0.

**Benchmark (reported, no pass rule).** The risk ratio of a bad review for orders from sellers in the worst vs best
quarter of other-order bad-review rate, as a yardstick for how strong a seller-level confounder can be in this data.

**Pass rules.**
- B-1. E-value to halve the estimate is at least 2.0.
- B-2. Oster `delta` to halve the estimate, with `Rmax = 1.3 * R_c`, is at least 1 (or negative because the controls
  move the estimate up, which is reported as such, not as a pass).

## (e) Contracts and exposures

**Scope.** The seven `export_dash_*` models that `dashboard/export_csv.py` writes to the CSVs Tableau reads.

**Pass rules.**
- E-1. `contract: {enforced: true}` with a data type for every column on all seven; `dbt build` passes.
- E-2. The contract can fail: changing one column's declared type makes `dbt build` fail (checked by a script).
- E-3. One exposure for the Tableau dashboard depends on all seven models; a check fails if `export_csv.py` reads a
  model the exposure does not list.
- E-4. A list of every number the dashboard prints, marked "from the semantic layer" only if a metric in
  `models/semantic/_semantic.yml` defines it. No pass rule on the count; the list is the output.

## (d) Delivery date as a range plus a separate rule

**Split (locked).** Train from January 2017 (walk-forward, retrained each month, 45-day label lag, as in
`recommendation/delivery_date_model`), tune November 2017 to February 2018, holdout March to August 2018.
These months were already scored by earlier models in this repo, so the holdout is locked but not fresh; that is
disclosed with every result. Order IDs (judged orders, sorted, newline-joined, SHA-256):
- train (Jan-Oct 2017): 30,299 orders, `da36b83c634179d41fb1aa8cedf304fcf4510c42e050da8ece4169bd93fcee69`
- tune (Nov 2017-Feb 2018): 26,121 orders, `adc1fe4666756906ac51d45ac508bb3292001ee278f0f0193f0759b0b20d0648`
- holdout (Mar-Aug 2018): 38,511 orders, `0d98b704ef12780ace89020dd89a1bb5be931ba07e2b601d5f0765ff3cad2440`

**Prediction layer.** Each candidate predicts a range of delivery days (purchase to delivery) for each order, using the
existing checkout-time features only. Candidates: scikit-learn gradient boosting with one quantile model per level,
LightGBM quantile models, and NGBoost with a log-normal distribution. Baseline: the route's own past delivery-time
quantiles (no model). Quantile levels 0.05 to 0.95 in steps of 0.05, plus 0.97 and 0.99; crossing quantiles are sorted.

**Scores.** CRPS approximated as twice the mean pinball loss over the 19 levels 0.05 to 0.95 (lower is better).
Calibration: for each level, the share of orders delivered within the predicted quantile; calibration error = the
largest gap from the level over 0.5 to 0.95.

**Selection.** The candidate with the lowest tune-block CRPS is selected before the holdout is scored. The holdout is
scored once for every candidate; the selection does not change after.

**Pass rules (prediction layer).**
- D-1. The selected model's holdout CRPS is lower than the route-history baseline's, and the 2.5th percentile of a
  2,000-resample paired order bootstrap of the difference is above 0.
- D-2. The selected model's holdout calibration error is at most 3 percentage points.

**Decision layer (separate code; reads only the predicted quantiles).**
- Rule T: print purchase date + the predicted quantile at level tau, rounded up, for tau from 0.50 to 0.99.
- Rule C: per order, pick the whole-day lead that minimizes expected extra bad reviews + lambda x lead days, using the
  predicted distribution and the published V2 bin effects; sweep lambda.
- For every tau and lambda: extra late-delivery bad reviews on reviewed holdout orders (V2 effects, same counting as
  the existing backtest), mean and median days added vs Olist's printed promise, and on-time share. Plotted as extra bad
  reviews against mean days added, with Olist's promise, the route p95 date and the 1-day guardrail marked.
- D-3 (reported finding, not a launch decision): whether any point at or under the guardrail (mean at most 1.0 day
  longer than Olist's, median at most 1 day longer) cuts extra bad reviews vs Olist with the 2.5th percentile of a
  2,000-resample order bootstrap above 0.
- No point is picked to ship. That is Mike's call.
