# Locked pass bar: honest-date bad-review backtest

Do not edit these thresholds after the totals are known.

A date (route p90 or route p95, each judged on its own) passes only if all of the following hold on the scored reviewed window, using V2 effects from `seeds/review_cost_effects.csv`:

1. Net reduction versus Olist is at least 250 extra bad reviews.
2. The same net reduction is at least 8% of Olist's extra computed on this same scored window (not 8% of the full-population 3,110, because the scored window drops early-2017 orders).
3. A 95% interval on the reduction, using the seed effect standard errors and treating the order counts as fixed, lies entirely above 0 (lower bound > 0).
4. March 2018 extra under the date is not higher than Olist's March extra on the scored reviewed March orders.
5. The V4 sensitivity also shows a net reduction whose 95% interval lies entirely above 0. It is not required to clear the 250 / 8% floors, but if that interval does not lie entirely above 0, the date does not pass.

It does not help if no date clears all five. Do not change the bar to rescue a near miss.

On 20 November 2026, items 3 and 5 were reworded after the totals to require the interval to sit on the reduction side (lower bound > 0). This only tightens the wording; which dates pass did not change (p90 FAIL, p95 PASS).


Interval method, locked with the bar:

- extra(policy) = sum over bins of n_policy[b] * effect[b], and 0 for on-time orders.
- net_change = extra(policy) - extra(Olist). A reduction is a negative net_change.
- reduction = extra(Olist) - extra(policy).
- With counts treated as fixed, Var(net_change) = sum_b (n_policy[b] - n_Olist[b])^2 * effect_se[b]^2.
- 95% interval uses z = 1.96: net_change ± 1.96 * sqrt(Var).
- V4 uses the same formulas with the V4 effects in `evidence/review_cost_causal_report.json`.

Population, locked:

- Late means delivered on a later calendar day than the date being judged. Same-day is on time.
- Score judged orders purchased on or after 2017-04-01 (90,003 orders in the reference run). Review totals use only those orders that have a review score.

A separate order-bootstrap interval (orders resampled, effects held fixed) is reported as a realistic range. It is not part of the pass bar.
