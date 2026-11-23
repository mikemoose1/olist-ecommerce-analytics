# Late deliveries and bad reviews at Olist

This project builds a tested data pipeline from about 99,000 real orders of Olist, a Brazilian online marketplace, and uses it to estimate what late delivery costs. The analysis found an estimated effect of late delivery on about 3,110 of the 11,635 one- and two-star reviews on 94,931 delivered orders, about 27%, with a range of 2,880 to 3,350. It is an estimate from past orders, not a randomized test, so it is not proven cause. There is too little repeat buying in the data to tell whether late delivery lowers it. The star penalty for a late order was smaller in the last four months of the window: 1.56 stars, against 2.05 earlier. The lead recommendation is a per-order delivery-date model. Scored once on held-out orders from March to August 2018, it would have cut extra late-delivery bad reviews by about 64% (about 811 of 1,275), but only by printing dates 4.5 days longer than Olist's on average, so it failed its pass bar and is not adopted now. Olist's printed promise stays. The model is worth rebuilding, with the length cap built in, once Olist's checkout data, which this dataset does not have, shows whether a longer date is worth it.

[![Dashboard of late deliveries, reviews, sellers, regions and months](docs/img/dashboard.png)](docs/img/dashboard.png)

*The dashboard in one view. Click the image for the full-size picture, or see it in [the full case study](docs/CASE_STUDY.md#dashboard). The interactive version is coming. It was built before the current recommendations. Its "Two fixes to test next" panel (seller ship-by reminders and buffer days) was replaced by the recommendation below, its "fixable cause" title rests on a handoff link that was never tested, and its repeat-late shippers panel is not a target list: a later as-of check found that sellers flagged for repeated late handoffs did not have more late orders afterward. The image has not been rebuilt since.*

**Role and tools.** An end-to-end analytics project on a public dataset: data modeling and automated data checks in dbt and DuckDB, the review-cost analysis in Python (pandas and statsmodels), a delivery-date model (scikit-learn), a recommendation memo, a Quarto data story and a Tableau dashboard. GitHub Actions rebuilds and checks all of it.

**Code.** This repository. The main folders are [models/](models/) (the dbt layers), [tests/](tests/) (data checks), [review_cost_causal/](review_cost_causal/README.md) (the estimate), [recommendation/](recommendation/MEMO.md) (the memo), [dashboard/](dashboard/tableau/README.md) (the Tableau workbook and its data) and [case_study/](case_study/) (the checks behind these pages).

**Read more.** [The full case study](docs/CASE_STUDY.md) has the charts, the data model and the verification record. [docs/REPRODUCE.md](docs/REPRODUCE.md) has setup and the one command that reproduces everything.

## The short version

A customer ID is a new receipt number on every order, so the analysis counts people, not IDs. An order is late when it arrives on a later calendar day than the promised date.

**Question.** What does late delivery cost Olist, and where should an operations manager act first?

**Finding.** 6.87% of delivered orders bought from January 2017 to August 2018 (6,518 of 94,931) arrived late. Late orders average 2.27 stars and on-time orders 4.31. The estimated effect is about 3,110 of 11,635 (27%). The 2,880 to 3,350 range is the spread of six comparison methods, not a confidence interval. The preferred method's own 95% interval is 3,025 to 3,195. On 9.0% of orders the seller handed the parcel to the carrier after the ship-by date. Those orders were late 21.2% of the time, against 5.4% when the handoff was on time.

**Recommendation.** Keep building a per-order delivery-date model as Olist's promise engine, but do not adopt this version: Olist's printed promise stays for now. Scored once on 38,307 reviewed orders from March to August 2018, it cut extra late-delivery bad reviews from about 1,275 under Olist's promise to about 464 and held up in the March 2018 spike, but its dates were 4.5 days longer than Olist's on average, against a cap of 1 day, so it failed its pass bar. The next round rebuilds it with the length cap inside the model, and it launches only once checkout conversion by promised days and a second peak season are available and show the longer date is worth it. A list of sellers who were late in past months does not point to later lateness: flagged sellers' orders ran late 6.9% of the time, against 7.2% for the rest. The full case study has the method and the decision rules.

**Dashboard numbers.** The goal, 4.4%, is the median late rate of the 15 stable months, and the warning line, 8.4%, is a limit set from how much the monthly late rate normally swings. Three months crossed the line. The what-if rate of 3.4% on the dashboard moves a typical stable month down from the goal by about 1.0 percentage point. The 5.49% on the full page is the same what-if on all 94,931 orders pooled, from 6.87%, which is higher because the pooled rate includes the spike months.

**Limits.** The effect estimate comes from comparing past orders, not from a randomized test, so it is not proven cause. Late handoff and late arrival are only linked, because the carrier may have been late anyway. Customers whose first order was late came back 0.10 percentage points less often, with a range of -0.52 to 0.22 percentage points that includes zero, so there is too little data to tell whether late delivery lowers repeat buying.

**Checked.** Every number on this page is checked against the warehouse by [case_study/check_case_study.py](case_study/check_case_study.py). The full case study has the charts, the data model and the verification record.
