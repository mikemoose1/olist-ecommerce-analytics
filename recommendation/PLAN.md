# Analysis plan: what late delivery costs Olist (written before any outcome was measured)

This plan was committed before `analyze.py` existed. The predictions below are the ones the results get compared against. Population sizes were counted for power planning. No outcome (stars, repeats, money) was looked at before this commit.

## Question

How much does a late delivery cost Olist in review stars, in repeat purchases and in money (R$)? Where do late orders cluster? Which one or two changes should Olist test first?

## Definitions (from `ontology/ontology.yml` only)

- **Late**: delivered on a later calendar day than the promised date. Population is the `late_rate` population: delivered, at least one item, purchased 2017-01..2018-08, multi-seller orders left out (C1). 94,931 orders, 6,518 late.
- **Review stars**: the chosen review per order (C4). The survey date is the date Olist sent the survey, not when the customer wrote.
- **Customer**: one person, `customer_unique_id`.
- **Repeat**: `repeat_rate_90d` (C6). Another qualifying order 24 hours to 90 days after the person's first qualifying order. Only people with a full 90 days of data count.
- Secondary repeat outcome: `repeat_rate_ever` (2+ qualifying orders at any time), compared within the same first-order month so follow-up time is equal.
- **Money**: `amount_paid` on an order (what the customer paid, items plus freight). This is gross merchandise value. Olist's commission rate is not in the data, so the memo reports GMV and says so.

## Units of analysis

- Stars: one row per order in the late-rate population with a review (94,302 orders).
- Repeats: one row per person whose FIRST qualifying order is in the late-rate population and who is eligible for the 90-day rate (74,882 people, 5,677 with a late first order). Late is judged on that first order.

## Methods (two ways for each effect)

1. **Matched groups.** Exact matching on ship-to state, product category (top 30 by orders, else "other"; category of the highest-priced item), order freight in fifths, and purchase month. Each late order is compared only with on-time orders in the same cell. Effect = weighted average of within-cell differences, weighted by late orders per cell (effect on the late orders). 95% interval from 1,000 bootstrap resamples of cells' orders, seed fixed.
2. **Regression.** Ordinary least squares of the outcome on late plus fixed effects for state, category, freight fifth and purchase month. Standard errors clustered by seller. For repeats this is a linear probability model so the coefficient reads directly in percentage points.
3. Raw difference, uncontrolled, as a reference point.

If the two methods disagree by more than their intervals allow, the memo says so and does not pick the convenient one.

## Money (low / mid / high)

Lost repeat GMV per year = late first orders per year x drop in 90-day repeat rate x average GMV of a repeat order.
- low / mid / high = the 95% interval's ends and the point estimate of the repeat drop from the matched method.
- If the interval includes zero, the low value is R$0 and the memo says the repeat effect is not distinguishable from zero.
- Per year = count over the 20-month window x 12 / 20.
Also reported, as a fact and not a cost: GMV of late orders, and the number of 1-2 star reviews attributable to lateness (late orders x matched excess share of 1-2 star reviews).

## Where late orders cluster

- Ship-to state, seller state to ship-to state route, and seller. For each: orders, late orders, late rate, share of all late orders.
- Seller concentration: share of late orders from the worst 10% of sellers by late-order count (sellers with 20+ orders).
- Who caused the delay. Seller side = the seller handed the parcel to the carrier after its ship-by date. Carrier side = handed over on time, delivered late. Single-seller orders only, so one seller owns the order (C1 makes this clean).
- Promise vs actual: whether long or short promises are missed more.

## Hold-out re-check

Discovery months: 2017-01..2018-04. Held-out months: 2018-05..2018-08 (24,928 orders, 1,114 late). Every effect and every cluster ranking is computed on discovery months, then recomputed on held-out months. A finding survives if its sign holds and its held-out interval overlaps the discovery interval. Repeat outcomes have few eligible held-out people (first order before 2018-06-05), so a held-out repeat check is expected to be inconclusive and is reported as such.

## Predictions (before measuring)

| Number | Prediction | Would change the memo if |
|---|---|---|
| Matched star penalty | -1.9 to -2.1 stars (OLS from the experiments gave -2.012) | under -1.5: lateness matters less than the raw gap says |
| Stars by days late | worse with each extra day late | flat: "late at all" is what hurts, padding helps more than speed |
| Repeat 90d, on time | about 1.3% | |
| Repeat 90d, late | about 0.9-1.1% | |
| Repeat drop | 0.2-0.4 points; interval likely includes zero (standard error about 0.15 points with 5,677 late first orders, so a drop under about 0.3 points cannot be told from zero) | a clear drop over 0.5 points makes repeat money the headline |
| Lost repeat GMV | small, under R$50,000 a year, because few people come back at all | over R$500,000: repeat loss becomes the main cost |
| Seller-side share of late orders | about 30-40% | over 50%: seller enforcement is action 1; under 20%: carrier and promise dates are |
| Top states by late rate | northeast states (AL, MA, SE, CE, PI, BA) and RJ | SP in the top: problem is volume, not distance |
| Seller concentration | worst 10% of sellers carry 30-50% of late orders | under 15%: no seller program worth testing |

## Noise floor and what else a number could be measuring

- Bootstrap and clustered standard errors give the interval. An effect smaller than its interval is reported as not distinguishable.
- Month is a confounder: late rate swings from 1.19% (2018-06) to 19.15% (2018-03), and stars may drift by month. Month is in every adjusted model.
- Survey timing: for late orders the survey can go out before delivery (C2). Those reviews are kept. The penalty includes customers rating while still waiting, which is a real experience, not a data error.
- Repeat clock: the 90 days start at purchase, so a late order leaves slightly fewer post-delivery days. The memo notes this. It biases the repeat drop upward, against the finding "no clear effect".
- Reverse direction: a review cannot cause lateness, and the repeat outcome comes after the first order, so the direction is fixed. Hidden confounders (product quality, seller quality) can remain. The seller-cluster numbers are descriptive.

## Deliverables

- `recommendation/analyze.py`: computes every number, writes `evidence/recommendation_report.json` and `.md`, and checks that every number in `MEMO.md` matches the report. Runs in `make verify`.
- `recommendation/MEMO.md`: one page for an e-commerce operations or marketplace manager. What it is, why it matters, what to do.
