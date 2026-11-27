# How I check AI-written analytics

AI coding agents wrote most of the code and analysis in this project. I set the questions and the rules, and I decided what merged. A number is not trusted because an agent produced it. It is trusted when a check that can fail has run against it. Every rule in [evidence/mutation_report.md](https://github.com/mikemoose1/olist-ecommerce-analytics/blob/main/evidence/mutation_report.md) has had a bad change planted and caught by at least one of its tests, and the number check has a self-test that plants wrong numbers.

## The checks that can fail

**Rules before results.** The pass rules for the four statistical stress tests, on missing reviews, a hidden confounder, a planted answer and the delivery-date range, are in [docs/preregistration_v2.md](preregistration_v2.md). That file was committed before any test results were committed, and it has not changed since. A result that misses its rule is published as a miss.

**Rules proven able to fail.** A data test that has never failed proves nothing. [scripts/prove_tests_fail.py](https://github.com/mikemoose1/olist-ecommerce-analytics/blob/main/scripts/prove_tests_fail.py) copies the warehouse, plants bad rows or a broken formula in the copy, and requires at least one of the rule's tests to fail there while all of them still pass on the real data. All 248 rules in the mutation report pass this test. The CI workflow runs it with the other checks.

**Every number in the write-up is traced.** [case_study/check_case_study.py](https://github.com/mikemoose1/olist-ecommerce-analytics/blob/main/case_study/check_case_study.py) rebuilds each number in the README, the case study, the Model card section of the delivery-range README and this page from the warehouse or the saved evidence files. It fails on any number it cannot trace. Its self-test plants wrong numbers in those pages and requires the check to catch each one.

**An independent recount.** [verification/verify_headlines.py](https://github.com/mikemoose1/olist-ecommerce-analytics/blob/main/verification/verify_headlines.py) recomputes the repeat-purchase rates, the late rate, the average review score and the raw review gap between late and on-time orders straight from the raw CSV files, without the dbt models, and the results must agree ([evidence/verification_report.md](https://github.com/mikemoose1/olist-ecommerce-analytics/blob/main/evidence/verification_report.md)). It does not recount the 3,110 estimate.

**Stress tests on the main estimate.** The [Stress tests](CASE_STUDY.md#stress-tests) section of the case study reports all four tests. Two met every pre-registered rule. Two missed one: the planted-answer test at half effect and the delivery-range calibration.

## Review by a different AI family

I ask a model from a different family than the one that wrote a change to review it, and I fix its findings before the change merges. The reviews and the model names are not stored here, so this is my practice, not evidence in the repo. It is not one of the checks above, because a review has not been shown to catch a planted mistake.

## One check that caught something

The planted-answer test copies the real orders, plants a late-delivery effect of known size, and asks the method to find it. The rule, written before the test ran, was that the method's 95% interval must cover the planted number in at least 17 of 20 draws. With the effect at half size, the interval covered it in 16 of 20 draws. That is a fail, and it is published as one.

Without a rule fixed in advance, 16 of 20 is easy to call close enough. The average estimate stayed close to the planted number, so the problem is the interval, which is too narrow. Across the draws with no, half and full effect it covered the planted number in 53 of 60. Because of this result, the case study tells readers not to quote 3,025 to 3,195 as a 95% range.

## What the checks do not show

The checks show that each number matches the data and that each rule was applied as written. They do not make the main estimate a proven cause. It comes from past orders, not a controlled test. They also cannot show that these were the right questions to ask. That part is my judgement.
