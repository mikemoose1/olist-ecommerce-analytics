# Locked pass bar: per-order delivery-date model

Written after tuning and before the holdout (purchases March to August 2018) was scored. Do not edit these thresholds after the holdout results are known.

## Tuning outcome, recorded before the holdout

The tuning rule (in `tune.py`) needed a setting whose promised date was on average at most 1 day longer than Olist's, and whose two tune-block spike months (November 2017 and February 2018) had no more extra late-delivery bad reviews than Olist's promise. None of the 56 settings met both. Every setting short enough to meet the length cap had more extra bad reviews than Olist in November 2017, the first peak season the model met, with no earlier November in its training data. Under the rule written before tuning, **the model fails at tuning** and is not adopted in this round.

The holdout is still scored once, for information, with the setting that cut the most extra bad reviews on the tune block among those that met the length cap: quantile 0.97, a 45-day label lag, learning rate 0.05, 300 trees of up to 15 leaves, at least 200 orders per leaf. Its tune-block coverage was 90.73%, so the coverage target below is 90%.

## The bar (judged on reviewed holdout orders, V2 effects from `seeds/review_cost_effects.csv`)

The model passes the holdout only if all of the following hold:

1. **Fewer bad reviews.** Net reduction in extra late-delivery bad reviews versus Olist's printed promise is above 0, and the 2.5th percentile of a 5,000-resample order bootstrap (effects held fixed) is above 0.
2. **Length cap.** The mean per-order promise is at most 1.0 day longer than Olist's, and the median promise at most 1 day longer than Olist's median.
3. **Spike month.** In March 2018, the holdout's spike month, extra bad reviews are not higher than under Olist's promise.
4. **Coverage.** At least 90% of scored holdout orders (reviewed or not) arrive on or before the printed date.
5. **Beats the simple date.** The model has fewer extra bad reviews than the route p95 date from `recommendation/promise_backtest/score.py` on the same orders, and the 2.5th percentile of a 5,000-resample paired order bootstrap of that difference is above 0.

The route p95 date is scored against items 1 to 4 on the same orders for comparison.

## Decision rule, locked

- The model is adopted only if it passed tuning and passes the holdout. It failed tuning, so the model is not adopted in this round, whatever the holdout shows. A holdout pass would be reported as evidence for the next round, not as a pass.
- If the route p95 date meets items 1 to 3 on the holdout, it is the recommended date now. If it does not, nothing passes, Olist's promise stays, and the recommendation is the data the model needs.
- A near miss does not pass. Do not change the bar to rescue one.

Late means delivered on a later calendar day than the printed date. Same day is on time. Scored orders are the judged orders (`metrics.metric_late_rate_orders`) bought in the holdout months; review totals use only orders with a review score.
