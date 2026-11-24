# Delivery date as a predicted range plus a separate rule

The earlier per-order model ([../delivery_date_model](../delivery_date_model/README.md)) did two jobs at once: it
predicted how long delivery takes and chose which date to print. This folder splits those jobs:

1. **Prediction layer** (`predict.py`): for each order, a range of likely delivery times, as quantiles from 5% to 99%.
   It knows nothing about promises or reviews.
2. **Decision layer** (`decide.py`): turns that range into a printed date. It reads only the predicted quantiles and
   the published late-to-bad-review effects.

This makes the trade-off visible: each setting of the rule gives a point with "days added to the promise" on one axis
and "extra bad reviews" on the other. **No point is picked here.** Which one to ship, and whether 1 day is the right
limit, are business calls.

The pass rules were written before the run, in [docs/preregistration_v2.md](../../docs/preregistration_v2.md) (part d).
Results: `evidence/delivery_range_report.json`. Rerun (about 16 minutes on 8 cores, needs `make build`):

```bash
pip install -r recommendation/delivery_range/requirements.txt   # LightGBM and NGBoost, on top of requirements.txt
python recommendation/delivery_range/run.py
```

## Set-up

- **Same split as the earlier model.** Walk-forward from January 2017 (each month retrained on orders delivered before
  it, with a 45-day label lag), tune on November 2017 to February 2018, holdout March to August 2018 (38,511 judged
  orders). `run.py` checks the order IDs of both blocks against the hashes in the pre-registration.
- **The holdout is locked, not fresh.** Earlier models in this repo already scored these months, so the design was
  shaped after earlier looks at them. Nothing newer exists in the data.
- **Same checkout-time features** as `../delivery_date_model/features.py`.
- **Candidates.** scikit-learn gradient boosting (one quantile model per level), LightGBM (same), and NGBoost with a
  log-normal distribution. The two boosting models reuse the earlier model's setting (learning rate 0.05, 300 trees,
  15 leaves, 200 orders per leaf). NGBoost used 400 rounds at 0.03 and was not tuned. Baseline with no model: the
  route's own past delivery times at each level.
- **Scores.** CRPS, the average distance between the predicted range and what happened (in days, lower is better),
  approximated from 19 evenly spaced quantiles. Calibration: for each level, the share of orders that arrived within
  it; the error is the largest gap between 50% and 95%.

## Prediction layer

| | CRPS, tune | CRPS, holdout | Calibration error, holdout | Arrived within the 90% quantile, holdout |
|---|---|---|---|---|
| scikit-learn boosting | 4.810 | 3.611 | 14.7 points | 91.8% |
| **LightGBM (picked on tune)** | **4.798** | **3.601** | **14.8 points** | **91.9%** |
| NGBoost log-normal | 4.810 | 3.535 | 16.0 points | 93.2% |
| Route history (no model) | 5.188 | 3.784 | 17.1 points | 92.9% |

LightGBM was picked on the tune block, by a margin of 0.012 days, before the holdout was scored. On the holdout,
NGBoost scored better; the pick was not changed.

**The ranges are not well calibrated.** On the tune block, which holds two peak months, orders arrived slower than
predicted: only 78.7% arrived within the 90% quantile. On the holdout, after the March peak, they arrived faster: 64.8%
arrived within the 50% quantile. A model retrained each month on older orders lags behind shifts in delivery speed in
both directions. So "the 90% date" is not a 90% promise. The decision layer below is judged on what actually happened,
not on the stated levels.

## Decision layer

- **Rule T:** print the predicted quantile at level tau, rounded up.
- **Rule C:** for each order, pick the whole-day date that minimizes expected extra bad reviews plus lambda times the
  days promised. Lambda is the price of a promise day in bad reviews. At lambda = 0.004, one bad review avoided is worth
  250 extra promise days spread over all orders. A long range gets a later date and a tight one an earlier date.

Holdout, 38,511 orders, extra late-delivery bad reviews counted on reviewed orders with the V2 effects. Olist's printed
date gives 1,275 extra bad reviews, with a mean promise of 22.5 days and a median of 22. Selected points (the full
sweep is in the report):

| Rule | Mean days vs Olist | Median promise | On time | Extra bad reviews | Fewer than Olist (95% bootstrap) | March 2018 (Olist 658) |
|---|---|---|---|---|---|---|
| T, tau 0.90 | -2.1 | 20 | 93.3% | 1,144 | 131 (99 to 167) | 662 |
| C, lambda 0.006 | -1.4 | 21 | 94.0% | 1,036 | 239 (206 to 274) | 602 |
| C, lambda 0.005 | -0.4 | 22 | 94.8% | 891 | 384 (351 to 419) | 522 |
| C, lambda 0.004 | +0.6 | 23 | 95.5% | 773 | 502 (468 to 539) | 463 |
| T, tau 0.95 | +1.5 | 23 | 96.0% | 682 | 593 (558 to 630) | 412 |
| Route p95 date | +4.3 | 24 | 96.3% | 670 | 605 (567 to 646) | 418 |

![trade-off](tradeoff.png)

Within the 1-day guardrail (mean at most 1.0 day longer than Olist's promise, median at most 1 day longer), the best
point is rule C at lambda 0.004: 502 fewer extra bad reviews (39%) for 0.6 more days on average. At lambda 0.005 the
promise is shorter than Olist's on average and still cuts 384. Rules T and C give nearly the same curve, with C a
little lower near the guardrail. The route p95 date cuts about as many as tau 0.95 but needs 4.3 days.

## Pass rules

| Rule | Result |
|---|---|
| D-1. Picked model beats the route-history baseline on holdout CRPS, paired bootstrap 2.5th percentile above 0 | **Pass** (0.18 days better, 0.16 to 0.20) |
| D-2. Picked model's holdout calibration error at most 3 points | **Fail** (14.8 points) |
| D-3. (Finding, not a launch decision) some point inside the guardrail cuts extra bad reviews, bootstrap 2.5th percentile above 0 | **Yes**: tau 0.90 and lambda 0.004, 0.005, 0.006 |

## Left to decide (not by this analysis)

- Which point to ship, if any: a tau, a lambda, or none.
- Whether a 1-day limit on the average promise is the right business limit.

## Limits

- Calibration failed (D-2). Any launch would need recalibration on recent deliveries, and that would have to be tested
  on months it was not built on.
- The holdout months were seen by earlier models in this repo.
- The bad-review effects come from the whole window, holdout included, and are treated as fixed. The bootstrap only
  reflects which orders happened to fall in the holdout, not uncertainty in the effects.
- A shorter or longer date may change who buys. There is no checkout data here, so that cost is not counted.
- No settings were tuned for this comparison. LightGBM and scikit-learn reuse the earlier model's setting, and NGBoost
  used one untuned setting.
