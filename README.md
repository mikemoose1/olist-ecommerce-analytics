# Late deliveries and bad reviews at Olist

This project builds a tested data pipeline from about 99,000 real orders of Olist, a Brazilian online marketplace, and uses it to estimate what late delivery costs. The analysis found an estimated effect of late delivery on about 3,110 of the 11,635 one- and two-star reviews on 94,931 delivered orders, about 27%, with a range of 2,880 to 3,350. It is an estimate from past orders, not a randomized test, so it is not proven cause. Late delivery shows no clear effect on repeat buying. The recommendation is two randomized tests, starting with reminders to sellers about their ship-by date, because 27.8% of late orders were handed to the carrier late. A ship-by date is the deadline Olist gives a seller to hand the parcel to the carrier.

[![Dashboard of late deliveries, reviews, sellers, regions and months](docs/img/dashboard.png)](docs/img/dashboard.png)

*The dashboard in one view. Click the image for the full-size picture, or [open the live, clickable dashboard](https://mikemoose1.github.io/olist-ecommerce-analytics/#live-dashboard).*

**Role and tools.** An end-to-end analytics project on a public dataset: data modeling and automated data checks in dbt and DuckDB, the review-cost analysis in Python (pandas and statsmodels), a recommendation memo, a Quarto data story and a Tableau dashboard. GitHub Actions rebuilds and checks all of it.

**Code.** This repository. The main folders are [models/](models/) (the dbt layers), [tests/](tests/) (data checks), [review_cost_causal/](review_cost_causal/README.md) (the estimate), [recommendation/](recommendation/MEMO.md) (the memo), [dashboard/](dashboard/tableau/README.md) (the Tableau workbook and its data) and [case_study/](case_study/) (the checks behind these pages).

**Read more.** [The full case study](https://mikemoose1.github.io/olist-ecommerce-analytics/) has the charts, the data model and the verification record ([same text in the repo](docs/CASE_STUDY.md)). [docs/REPRODUCE.md](docs/REPRODUCE.md) has setup and the one command that reproduces everything.

## The short version

**Question.** What does late delivery cost Olist, and where should an operations manager act first?

**Finding.** 6.87% of delivered orders (6,518 of 94,931) arrived late. Late orders average 2.27 stars and on-time orders 4.31. The estimated effect is about 3,110 of 11,635 (27%) bad reviews, and six reasonable ways of comparing give 2,880 to 3,350. On 9.0% of orders the seller handed the parcel to the carrier after the ship-by date. Those orders were late 21.2% of the time, against 5.4% when the handoff was on time.

**Recommendation.** Run two randomized tests before any rollout. First, ship-by reminders. Half of the sellers, picked at random, get a reminder the day before each ship-by date and a visible on-time score. The other half see no change. Second, buffer days in the promise for north and northeast addresses and in high-lateness months, on a random half of orders.

**Dashboard numbers.** The goal, 4.4%, is the median late rate of the 15 stable months, and the warning line, 8.4%, is a limit set from how much the monthly late rate normally swings. Three months crossed the line. The what-if rate of 3.4% on the dashboard moves a typical stable month down from the goal by about 1.0 percentage point. The 5.49% on the full page is the same what-if on all 94,931 orders pooled, from 6.87%, which is higher because the pooled rate includes the spike months.

**Limits.** The effect estimate comes from comparing past orders, not from a randomized test, so it is not proven cause. Late handoff and late arrival are only linked, because the carrier may have been late anyway. Customers whose first order was late came back 0.10 percentage points less often, with a range of -0.52 to 0.22 percentage points that includes zero, so repeat buying shows no clear effect.

**Checked.** Every number on this page is checked against the warehouse by [case_study/check_case_study.py](case_study/check_case_study.py). The full case study has the charts, the data model and the verification record.
