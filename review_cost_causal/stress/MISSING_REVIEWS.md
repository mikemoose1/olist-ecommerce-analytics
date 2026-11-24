# Do missing reviews bias the 3,110?

**Short answer: no, if whether someone reviews depends only on things the data records.** Late orders are reviewed a
little less often than on-time ones, but so few judged orders have no review that reweighting for it moves the estimate
by under one review. The bounds below drop that assumption, and the estimate still stays inside the published range.

The pass rules were written before this ran, in [docs/preregistration_v2.md](../../docs/preregistration_v2.md) (part a).
Numbers below come from `evidence/missing_reviews_report.json`. Rerun with
`python review_cost_causal/stress/missing_reviews.py` after `make build` (about 6 minutes).

## Who is missing

| | Orders |
|---|---|
| Orders in the raw CSVs | 99,441 |
| Not judged (never delivered, or no promised date) | 4,510 |
| Judged orders | 94,931 |
| Judged, with a review | 94,302 |
| Judged, no review | 629 |
| Late judged orders with no review | 152 of 6,518 |

The 4,510 orders that were never delivered have no "days late", so they cannot enter a late-vs-on-time comparison. They
stay out, as before.

## Are late orders reviewed less often?

Yes, slightly: 97.7% of late orders have a review against 99.5% of on-time ones, a gap of 1.8 points (95% interval 1.4 to
2.2). Comparing within the same seller, category and month gives the same gap, 1.7 points (1.4 to 2.1).

## Reweighting for it

A logistic model gives each judged order its chance of being reviewed, from days late, days early, price, freight,
promised days, category, month and customer state. Each reviewed order then counts 1 / that chance, so reviewed orders
that look like the unreviewed ones count a little more. The preferred estimate (V2) is rerun with those weights.

| | Extra bad reviews | 95% interval |
|---|---|---|
| Published V2, no weights | 3,110 | 3,025 to 3,195 |
| V2 with inverse-probability weights | 3,109 | 3,024 to 3,195 |

The weights run from 1.000 to 1.137 (mean 1.007), so they barely change anything. Effective sample size is 94,298 of
94,302.

## Is the shift real or caused by the weighting?

Three checks, set before the run:

- **Code check.** The weighted code with every weight set to 1 gives 3,110 exactly (difference 0.0). Pass.
- **Shuffle check.** The real weights shuffled at random 50 times (so they say nothing about who reviews) move the
  estimate by up to 0.46 reviews at the 95th percentile. The real weights move it by 0.46. The shift is the size of the
  noise the weighting adds by itself, so it is not evidence of bias.
- **Trimming.** Capping the weights at their 1st and 99th percentiles changes the weighted estimate by 0.01%. Pass.

## All-bad and none-bad scenarios

If every one of the 629 unreviewed orders had been a bad review, V2 gives 3,113 on the same 6,366 reviewed late orders.
If none had, it gives 3,016. Counting the 152 unreviewed late orders in as well gives 3,198 and 3,099. All four are
inside the published 2,880 to 3,350 range. These are the scenarios rule A-2 names.

## Differential bounds

The scenarios above move late and on-time orders the same way, so they are not the widest case. The widest case counts
every unreviewed late order as bad and every unreviewed on-time order as not bad, then the reverse. On the same 6,366
reviewed late orders this gives 2,970 to 3,160. Counting the 152 unreviewed late orders in as well gives 3,051 to 3,246.
Both are inside 2,880 to 3,350. These bounds were added after the review and have no pass rule.

## Pass rules

| Rule | Result |
|---|---|
| A-1. Weighted estimate within 5% of 3,110 and inside 2,880 to 3,350 | **Pass** (3,109, -0.01%) |
| A-2. Both all-bad and none-bad estimates inside 2,880 to 3,350 | **Pass** (3,016 to 3,198) |

## Limits

- The review model only uses what is recorded about the order. If people skip reviews for a reason that is not in the
  data and also relates to how they felt about the delivery, the weights cannot fix that. The differential bounds cover
  that case for these 629 orders, and they stay inside the range.
- The 4,510 undelivered orders are a different question (a parcel that never arrives), not covered here.
