# Per-route delivery-date backtest

A short-term printed-date test: replay history with a walk-forward per-route delivery date in place of Olist's promise, and estimate the change in extra 1-2 star reviews attributed to late delivery. Actual delivery times stay as they were. This is not a logistics fix.

## How to run

Needs a built warehouse (`make build`). The warehouse path is `OLIST_DB_PATH`, or `olist.duckdb` in the repo root.

```
python recommendation/promise_backtest/check_headlines.py
```

`make verify` runs that check. It rebuilds the walk-forward dates from the warehouse, applies the published V2 effects (V4 as a sensitivity), and fails if any locked headline in `expected.json` has drifted. The pass bar was written before the totals; both land in the same commit. The figures in the section below are also checked against `expected.json`.

## What the analysis found

On 89,412 reviewed orders purchased from April 2017 onward, the pre-declared route p95 date (arrive by 19 times out of 20) cuts expected extra bad reviews by 286 versus Olist's 3,017, about 9%. An order bootstrap (5,000 resamples, effects held fixed) gives a range of 225 to 345 reviews, or about 7% to 11%. That cut is a net: 2,337 newly on-time orders avoid about 894 extra bad reviews, 1,839 newly late orders add about 650, and about 42 fewer come from orders late either way. March 2018 also improves. The pass bar is met. The looser route p90 date (arrive by 9 times out of 10) fails the bar and adds about 1,739 extra bad reviews, because it marks too many orders late.

The data cannot measure checkout conversion or whether honest dates would raise repeat buying.

## Earlier delivery-date tests, in brief

A more detailed walk-forward model (route, month, seller, load, and parcel weight) did not beat a simple walk-forward route median on accuracy. Its 9-out-of-10 date was too tight, especially in March 2018, so it failed a pre-registered accuracy and coverage bar. The simple route p90 date was close to real arrivals and well calibrated overall but missed March 2018. The pre-declared route p95 date held in March and stayed one day shorter than Olist's median promise, but it covered slightly more orders than a cap set for that earlier test. Those coverage results are not re-tested here. This folder asks a different question: what the two simple dates would have done to late-delivery bad reviews.
