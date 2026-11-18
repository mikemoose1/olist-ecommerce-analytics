# Late deliveries: what they cost Olist and what to test

Written for an e-commerce operations or marketplace manager. Every number comes from `recommendation/analyze.py`, and `make verify` fails if any number here stops matching it. The orders are single-seller orders bought 2017-01 to 2018-08 and delivered, 94,931 in all, as defined in `ontology/ontology.yml`.

## What it is

6.87% of these orders (6,518) arrived after the date Olist promised. Late orders average 2.27 stars. On-time orders average 4.31.

## Why it matters

**Stars.** A late order costs about 2 stars, and about 1.6 in the most recent months. Compared with on-time orders in the same state, product category, freight band and month, late orders score 1.96 stars lower (95% range 1.91 to 2.01). A regression with the same controls gives 1.97 (1.92 to 2.02). Stars fall with each extra day for about two weeks: 3.74 at 1 day late, 2.94 at 2-3 days, 2.10 at 4-7 days and 1.67 at 8-14 days. After that they level off (1.72 at 15 days or more).

**Bad reviews.** 62.4% of late orders get 1 or 2 stars, against 8.7% of on-time orders. Lateness accounts for about 3,300 one- and two-star reviews on these orders, 28.7% of them (range 27.7% to 29.4%).

**Repeat buying shows no clear effect.** Of people whose first order was late, 1.02% came back within 90 days, against 1.30% for on-time first orders. After matching, the gap is -0.10 points, with a range of -0.52 to 0.22. That range includes zero, so the data cannot tell a real drop from chance. Ever coming back gives the same answer (-0.43 points, range -1.03 to 0.22).

**Money.** Lost repeat sales come to R$0 (low), R$600 (mid) and R$3,200 (high) a year. That is 3,800 late first orders a year, times the repeat drop, times R$163, which is what a returning customer spends in their 90 days. It is small because few customers come back at all. Late orders carried R$0.7 million of sales a year. That money went through a bad experience. It was not lost. Olist's commission and the sales value of a star are not in this data. So the case for fixing lateness rests on ratings, not on repeat revenue.

## Where late orders cluster

**When.** 48.3% of late orders came from three months that had 21.7% of orders: 2018-03 (19.2% late), 2018-02 (14.2%) and 2017-11 (12.5%). The spike hit the whole country. Outside Rio de Janeiro, orders ran 9.8% late from 2017-11 to 2018-03 and 4.1% in other months.

**Where.** North and northeast states receive 11.3% of orders and 20.0% of late orders, a 12.2% late rate. The worst are AL (21.6%), MA (17.7%) and SE (15.5%). Rio de Janeiro had 22.9% of late orders, almost all from the spike. It ran 26.6% late from 2017-11 to 2018-03 and 4.4% in other months.

**Who.** On 9.0% of orders the seller handed the parcel to the carrier after its ship-by date. Those orders were late 21.2% of the time, against 5.4% when the handoff was on time. 27.8% of late orders had a late handoff. The rest were handed over on time and still arrived late. A short list of bad sellers is not the answer. Among sellers with 20 or more orders, the 73 that run late at least twice as often as average carry 12.7% of late orders.

## What to do: two tests

1. **Hold sellers to their ship-by date.** Pick half of sellers at random. They get a reminder the day before each ship-by date and a visible on-time handoff score. The other half see no change. Assign by seller, not by order. Measure the share of handoffs after ship-by first, then the late rate and average stars, over 8 weeks. The ceiling is about 1,300 fewer late orders (20.6% of them), if late-handoff orders became as reliable as on-time ones. The real gain will be lower, since sellers who miss ship-by may differ in other ways.
2. **Add buffer days to the promise where and when lateness is likely.** For north and northeast addresses, and in peak periods such as November, add buffer days to the promised date on a random half of orders at checkout. 28.6% of late orders were 1-3 days late and 56.1% were within 7 days, so a few days would turn many of them into on-time orders. Measure the late rate, average stars and checkout conversion. Conversion is not in this data and is the main risk. Longer promises may also cost stars: on-time orders with 36+ day promises averaged 4.17 stars, against 4.42 for 0-14 days. That raw comparison also mixes in distance.

## How sure we are

- The star penalty held in 2018-05 to 2018-08, the months set aside before measuring, but it was smaller: 1.56 stars (range 1.44 to 1.68) against 2.05 earlier. Late orders in those months were less late (median 5 days against 7), which fits the day-by-day pattern.
- North and northeast stayed worse (13.8% against 6.9% elsewhere, then 6.8% against 4.2%). Late handoffs stayed risky (21.0% against 6.3%, then 22.0% against 3.0%).
- Much of the star cost comes from customers rating while still waiting. Olist sends the survey on the promised date if the parcel has not arrived. 74.5% of late orders' surveys went out before delivery and average 1.84 stars. Late orders surveyed after delivery average 3.53. Sending the survey later would raise the score without fixing a single delivery, so it is not on the list.
- Matching found on-time look-alikes for 87.2% of late orders. It rules out state, category, freight and month as the explanation. It cannot rule out product or seller quality. That is why both actions are tests, not rollouts.
