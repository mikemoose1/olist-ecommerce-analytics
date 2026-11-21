# Per-order delivery-date model

A model that sets an expected delivery date for each order at checkout, retrained every month on orders already delivered, built and judged the way a production model would be: train, tune and holdout on separate stretches of time, with the pass bar written before the holdout was scored.

**Result: FAIL.** The model cut late-delivery bad reviews by far more than either baseline, but only by printing longer dates than the locked cap allows, and it failed tuning in the first peak season it met. The full bar and the decision rule are in [PASS_BAR.md](PASS_BAR.md).

## Set-up

- **Split by purchase month.** Train on January to October 2017, tune on November 2017 to February 2018, hold out March to August 2018. Both the tune block and the holdout contain a spike month (November 2017 and February 2018 in tuning, March 2018 in the holdout).
- **Walk-forward.** Each month gets its own model, trained only on orders delivered before the 1st of that month and bought at least 30 or 45 days before it (the label lag, tuned). Without the lag the newest training orders are only the fast ones, because the slow ones have not arrived yet.
- **Checkout-time features only** (`features.py`): route history (the route's past median, 90th and 95th percentile delivery times), distance from seller to customer, the seller's past delivery time, past lateness and past handoff speed, the seller's orders in the last 30 days and orders still open, parcel weight and size, freight and price, purchase month and weekday, Olist's own printed lead time, platform orders in the last 7 days and orders still in transit, and both states. Every history feature counts only events strictly before the purchase.
- **Model.** scikit-learn gradient boosting with a quantile loss (`model.py`). The printed date is the purchase date plus the predicted quantile, rounded up to whole days.
- **Scoring.** The same late-delivery bad-review effects (V2, with V4 as a sensitivity) and the same order bootstrap as [the promise backtest](../promise_backtest/README.md), on judged orders. Baselines are Olist's printed promise and the route p95 date from `../promise_backtest/score.py`, on the same orders.

## Tuning

`tune.py` tried 56 settings (quantile 0.90 to 0.99, label lag 30 or 45 days, two learning rates, two tree sizes) on the tune block only. A setting had to print dates on average no more than 1 day longer than Olist's and do no worse than Olist in November 2017 and February 2018. None of the 56 settings passed tuning. Every setting short enough for the length cap was worse than Olist in November 2017, the first peak season the model met, with no earlier November in its training data. The best of them, quantile 0.97, cut 150 bad reviews over the tune block at 0.4 days longer, but had 467 extra bad reviews in November 2017 against Olist's 440. The route p95 date did worse over the same block, with 248 more extra bad reviews than Olist. The settings and results are in `tune_results.json`. An earlier grid, with no label lag and quantiles from 0.80, gave tune-block coverage near 50% at quantile 0.80; the lag was added and the grid moved to 0.90 to 0.99 before the holdout was touched.

## Holdout, scored once

The holdout was scored once with that quantile-0.97 setting, for information. On 38,307 reviewed orders bought March to August 2018:

- extra late-delivery bad reviews fall from about 1,275 under Olist's printed promise to about 464, a cut of about 811 (64%; bootstrap range 773 to 852). That is about 711 avoided on 1,741 orders that turn on time, minus about 20 added on 70 orders that turn late, plus about 120 fewer on orders late either way.
- That is about 206 fewer than the route p95 date (paired range 183 to 230), which cut about 605 (range 568 to 646).
- March 2018: 658 under Olist, 283 under the model, 418 under route p95.
- 97.3% of orders arrive by the model's date, against 92.9% for Olist's. The coverage target set on the tune block was 90%.
- The cost: the model's dates are on average 4.5 days longer than Olist's (median 26 days against 22), against a cap of 1 day. The route p95 date was 4.3 days longer. The model's date is later than Olist's on 72% of orders.

Bar: fewer bad reviews, pass; spike month, pass; coverage, pass; beats route p95, pass; length cap, **FAIL**. With tuning already failed, the model is not adopted. The route p95 date also fails the length cap on this holdout, so under the locked rule nothing passes and Olist's promise stays.

Olist shortened its own promise in 2018: an average of 22.5 days in the holdout against 25.7 in the tune block. Most of the model's cut comes from printing a later date where a parcel is likely to run late, and checkout conversion, which decides whether a later date is worth it, is not in the data.

In the March 2018 model, the features that mattered most (permutation importance on the pinball loss) were the customer's state, the distance, Olist's printed lead, the route's 90th-percentile time and the seller's past handoff speed.

## Repeat-late sellers, as of each month

`seller_flags.py` tests whether sellers who were late in at least 3 earlier months are worth targeting. At the 1st of each holdout month it flags sellers with orders that were both handed over after the ship-by date and delivered late in at least 3 different earlier months, using only orders delivered by then: 46 sellers in March 2018, 106 by August. In the following months those sellers handed parcels over late more often (11.4% against 6.9%), but their orders did not arrive late more often (6.9% against 7.2%). They carried 18.1% of late orders on 18.6% of orders. A list of repeat-late sellers does not point to where future late deliveries will come from.

## How to run

Needs a built warehouse (`make build`).

```
python recommendation/delivery_date_model/check_headlines.py
```

`make verify` runs it. It rebuilds the features, the six monthly holdout models, both baselines and the seller flags from the warehouse, and fails if any result in `expected.json` drifts, if the rounded figures no longer add up, or if this README no longer states them. `tune.py` reruns the tuning grid (several minutes; not part of `make verify`).
