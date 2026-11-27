# Late deliveries and bad reviews at Olist

- **What late delivery costs.** Late delivery is the estimated cause of about 3,110 of the 11,635 one- and two-star reviews on delivered orders (27%). Reweighting for missing reviews gives 3,109, and a hidden confounder would need an E-value of 5.1 to halve it. A planted-effect test missed its coverage rule, and that is reported as a fail.
- **What to do about it.** A delivery-range model beat the no-model baseline but failed its own calibration rule: a calibration error of 14.8 points, against a limit of 3. It is not ready to ship, and Olist's printed promise stays.
- **How the numbers are checked.** Every number on this page is recomputed from the warehouse or the saved evidence files by [case_study/check_case_study.py](case_study/check_case_study.py), the pass rules were written before the stress tests ran, and all 248 rules in the check suite are proven able to fail on planted bad data ([evidence/mutation_report.md](evidence/mutation_report.md)).

**[Dashboard](docs/CASE_STUDY.md#dashboard)** · **[Case study](docs/CASE_STUDY.md)** · **[Code](models/)** · **[Reproduce](docs/REPRODUCE.md)**

| Result | Number | Status |
|---|---|---|
| Bad reviews caused by late delivery | about 3,110 of 11,635 (27%); range across six specifications 2,880 to 3,350, not a confidence interval | Estimate from past orders, not a randomized test |
| Same estimate, reweighted for missing reviews (inverse probability weighting) | 3,109 | Pass |
| How strong a hidden confounder must be to halve it (E-value) | 5.1 (rule: at least 2.0) | Pass |
| Planted-effect test on the real orders | the 95% interval covered the planted number in 16 of 20 draws at half effect (rule: at least 17) | Fail, reported |
| Delivery-range model, calibration error | 14.8 points (rule: at most 3) | Fail, not ready to ship |

## Summary

This project builds a tested data pipeline from about 99,000 real orders of Olist, a Brazilian online marketplace, and uses it to estimate what late delivery costs. The analysis found an estimated effect of late delivery on about 3,110 of the 11,635 one- and two-star reviews on 94,931 delivered orders, about 27%, with a range of 2,880 to 3,350. It is an estimate from past orders, not a randomized test, so it is not proven cause. There is too little repeat buying in the data to tell whether late delivery lowers it. The star penalty for a late order was smaller in the last four months of the window: 1.56 stars, against 2.05 earlier. The lead recommendation is a per-order delivery-date model. Scored once on held-out orders from March to August 2018, it would have cut extra late-delivery bad reviews by about 64% (about 811 of 1,275), but only by printing dates 4.5 days longer than Olist's on average, so it failed its pass bar and is not adopted now. Olist's printed promise stays. The model is worth rebuilding, with the length cap built in, once Olist's checkout data, which this dataset does not have, shows whether a longer date is worth it.

[![Dashboard of late deliveries, reviews, sellers, regions and months](docs/img/dashboard.png)](docs/img/dashboard.png)

*The dashboard in one view. Click the image for the full-size picture, or see it in [the full case study](docs/CASE_STUDY.md#dashboard). The interactive version is coming.*

**Role and tools.** An end-to-end analytics project on a public dataset: data modeling and automated data checks in dbt and DuckDB, the review-cost analysis in Python (pandas and statsmodels), a delivery-date model (scikit-learn), a recommendation memo, a Quarto data story and a Tableau dashboard. GitHub Actions rebuilds and checks all of it.

**Code.** This repository. The main folders are [models/](models/) (the dbt layers), [tests/](tests/) (data checks), [review_cost_causal/](review_cost_causal/README.md) (the estimate), [recommendation/](recommendation/MEMO.md) (the memo), [dashboard/](dashboard/tableau/README.md) (the Tableau workbook and its data) and [case_study/](case_study/) (the checks behind these pages).

## How this was built

AI coding agents wrote most of the code and analysis. [How I check AI-written analytics](docs/HOW_I_CHECK_AI_WORK.md) explains how each piece was checked before it merged, with an example of a check that caught a problem.

The pass rules for the stress tests were committed in [docs/preregistration_v2.md](docs/preregistration_v2.md) before any of them ran. Each change then went in as a small pull request with its own evidence: the scripts that produce its numbers were rerun to reproduce them, and the full check suite ran in CI before merge.

- [Contracts and the dashboard exposure](https://github.com/mikemoose1/olist-ecommerce-analytics/pull/8): enforced dbt contracts on every table the dashboard reads, and [dashboard/SEMANTIC_LAYER.md](dashboard/SEMANTIC_LAYER.md).
- [Missing reviews](https://github.com/mikemoose1/olist-ecommerce-analytics/pull/10): inverse probability weighting and worst-case bounds ([review_cost_causal/stress/MISSING_REVIEWS.md](review_cost_causal/stress/MISSING_REVIEWS.md)).
- [Planted answer and hidden confounder](https://github.com/mikemoose1/olist-ecommerce-analytics/pull/9): the known-answer test, the E-value and the Oster bound ([review_cost_causal/stress/SENSITIVITY_AND_KNOWN_ANSWER.md](review_cost_causal/stress/SENSITIVITY_AND_KNOWN_ANSWER.md)).
- [Delivery range and decision rule](https://github.com/mikemoose1/olist-ecommerce-analytics/pull/11): a predicted range kept apart from the rule that picks the printed date, with a model card ([recommendation/delivery_range/README.md](recommendation/delivery_range/README.md)).

## The short version

A customer ID is a new receipt number on every order, so the analysis counts people, not IDs. An order is late when it arrives on a later calendar day than the promised date.

**Question.** What does late delivery cost Olist, and where should an operations manager act first?

**Finding.** 6.87% of delivered orders bought from January 2017 to August 2018 (6,518 of 94,931) arrived late. Late orders average 2.27 stars and on-time orders 4.31. The estimated effect is about 3,110 of 11,635 (27%). The 2,880 to 3,350 range is the spread of six comparison methods, not a confidence interval. The preferred method's own 95% interval is 3,025 to 3,195. On 9.0% of orders the seller handed the parcel to the carrier after the ship-by date. Those orders were late 21.2% of the time, against 5.4% when the handoff was on time.

**Recommendation.** Keep building a per-order delivery-date model as Olist's promise engine, but do not adopt this version: Olist's printed promise stays for now. Scored once on 38,307 reviewed orders from March to August 2018, it cut extra late-delivery bad reviews from about 1,275 under Olist's promise to about 464 and held up in the March 2018 spike, but its dates were 4.5 days longer than Olist's on average, against a cap of 1 day, so it failed its pass bar. The next round rebuilds it with the length cap inside the model, and it launches only once checkout conversion by promised days and a second peak season are available and show the longer date is worth it. A list of sellers who were late in past months does not point to later lateness: flagged sellers' orders ran late 6.9% of the time, against 7.2% for the rest. The full case study has the method and the decision rules.

**Dashboard numbers.** The goal, 4.4%, is the median late rate of the 15 stable months, and the warning line, 8.4%, is a limit set from how much the monthly late rate normally swings. Three months crossed the line. The what-if rate of 3.4% on the dashboard moves a typical stable month down from the goal by about 1.0 percentage point. The 5.49% on the full page is the same what-if on all 94,931 orders pooled, from 6.87%, which is higher because the pooled rate includes the spike months.

**Limits.** The effect estimate comes from comparing past orders, not from a randomized test, so it is not proven cause. Late handoff and late arrival are only linked, because the carrier may have been late anyway. Customers whose first order was late came back 0.10 percentage points less often, with a range of -0.52 to 0.22 percentage points that includes zero, so there is too little data to tell whether late delivery lowers repeat buying.

**Checked.** Every number on this page is checked against the warehouse by [case_study/check_case_study.py](case_study/check_case_study.py). The full case study has the charts, the data model and the verification record.
