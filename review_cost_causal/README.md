# Does late delivery cause Olist's bad reviews?

Short answer: yes, as an estimate from past orders. Late delivery is the estimated cause of about 3,110 extra 1-2 star
reviews, 26.7% of the 11,635 bad ones (the story and memo round it to about 27%). This is the figure the story and the memo
print. Their titles say late deliveries are "linked to" the bad reviews, because a title is read without the method beside it.

History: until PR #8 (the story until PR #7) the story and the memo printed 3,335 (28.7%), a matched association. That comparison used all on-time
orders, including ones that arrived days early, as the baseline, and came out a little high. The recommendation report still
carries it under `money.low_star_reviews`, and `recommendation/memo_check.py` fails if the memo or the story prints it again, and `recommendation/check_docs.py` fails if a README or the plan states it outside a History line.

Numbers below come from `evidence/review_cost_causal_report.json`; the dbt model
`metric_review_cost_causal` multiplies the per-bin effects in `seeds/review_cost_effects.csv` by its own counts, and the test
`assert_review_cost_causal_reconciles` reads that JSON and fails if the two disagree.

## How sure are we

- **Range: about 2,880 to 3,350.** That is the spread of the point estimates across six specifications (same seller,
  category and month, with the preferred "arrived just on time" baseline; the same with any on-time order as baseline; same product; plus state; same actual delivery time; no seller matching).
  The narrower 95% interval on the preferred specification alone (3,025 to 3,195) only reflects sampling noise inside
  that one choice, so it is not the range to quote. Nothing in the evidence supports a figure as high as 3,500.
- **Hidden seller sloppiness.** Orders handed to the carrier late but still delivered on time get about 1.4 points more bad
  reviews than the same seller's other on-time orders (95% interval 0.4 to 2.4 points). If a hidden effect of that size also
  sat inside every late order, it would account for about 90 reviews, and about 150 at the top of the interval (3-5% of the 3,110).
- **The cutoff comparison (regression discontinuity) is used for shape only.** Its density check failed: fewer parcels
  arrive one day late than the trend predicts, so the "just missed vs just made it" groups are not alike.
- **Review-text agreement.** Two independent AI labelers labeled the same 200 Portuguese reviews
  as delivery, product or other, each from the text alone. They agreed on 187 of 200 (93.5%), kappa 0.89 (0.91 for
  delivery vs not delivery). That is agreement between two AIs, not accuracy against hand-checked labels.
  Reproduce it: `python review_cost_causal/label_agreement.py` (labels and order IDs in
  `evidence/review_text_labels_sample200.csv`; the review text is public Kaggle data keyed by `order_id`, not copied here).

- **Missing reviews.** 629 judged orders have no review, and late orders are reviewed 1.8 points less often. Reweighting
  for that gives 3,109, which holds if reviewing depends only on what the data records. Without that assumption, counting
  unreviewed late orders as bad and unreviewed on-time orders as not bad, or the reverse, gives 2,970 to 3,160, still
  inside the range. Details: [stress/MISSING_REVIEWS.md](stress/MISSING_REVIEWS.md).

## Break-point wording

The two-break fit of review score on days late puts the breaks at day -1 and day 6. Those are point estimates on a
whole-day grid. A bootstrap "95% interval" for them collapsed to a single value, so no interval is claimed.
