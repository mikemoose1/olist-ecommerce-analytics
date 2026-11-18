#!/usr/bin/env python3
"""Prove the memo check can fail. The real memo must pass; each way of breaking it must be caught.
The first five cases are the independent reviewer's counterexamples (each one passed the old, value-only check).
Usage: python recommendation/selftest_memo.py   (after recommendation/analyze.py has written evidence/recommendation_report.json)"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from memo_check import check_memo

ROOT = os.path.dirname(HERE)
memo = open(os.path.join(HERE, "MEMO.md")).read()
facts = json.load(open(os.path.join(ROOT, "evidence", "recommendation_report.json")))["memo_facts"]

CASES = [  # (name, old text, new text, text the problem list must contain)
    ("a nearby fact's value swapped in (1.96 -> 1.97)", "1.96<!--f:abs:stars_matched-->", "1.97<!--f:abs:stars_matched-->", "stars_matched"),
    ("another metric's value swapped in (28.7% -> 62.4%)", "28.7<!--f:low_star_share_mid-->", "62.4<!--f:low_star_share_mid-->", "low_star_share_mid"),
    ("another metric's value swapped in (87.2% -> 74.5%)", "87.2<!--f:matched_pct-->", "74.5<!--f:matched_pct-->", "matched_pct"),
    ("a number no fact produced (6.87 -> 6.79)", "6.87<!--f:late_rate-->", "6.79<!--f:late_rate-->", "late_rate"),
    ("a money figure edited (R$163 -> R$27)", "R$163<!--f:repeat_spend-->", "R$27<!--f:repeat_spend-->", "repeat_spend"),
    ("a number with its tag removed", "6,518<!--f:late_orders-->", "6,518", "6,518: no tag"),
    ("a tag that names no fact", "6.87<!--f:late_rate-->", "6.87<!--f:no_such_fact-->", "names nothing"),
    ("a design constant with a different value (20 -> 25 orders)", "20<!--d:min_seller_orders-->", "25<!--d:min_seller_orders-->", "min_seller_orders"),
    ("a sign dropped where the prose says -0.10", "-0.10<!--f:rep_matched-->", "0.10<!--f:rep_matched-->", "rep_matched"),
    ("a tag that follows no number", "twice as often as average", "twice as often<!--f:late_rate--> as average", "follows no number"),
    ("a new bare number slipped into a sentence", "so a few days would", "so about 14 days would", "14: no tag"),
    # review L2: a label or a direction swapped while every value and tag stays put
    ("a state label swapped (AL -> SP)", "AL (21.6<!--f:state_AL-->%)", "SP (21.6<!--f:state_AL-->%)", "state_AL"),
    ("two state labels swapped (AL <-> MA)", "AL (21.6<!--f:state_AL-->%), MA (17.7", "MA (21.6<!--f:state_AL-->%), AL (17.7", "state_AL"),
    ("a month label swapped (2018-03 -> 2017-11)", "2018-03 (19.2<!--f:month_2018-03-->", "2017-11 (19.2<!--f:month_2018-03-->", "month_2018-03"),
    ("a direction flipped (stars lower -> stars higher)", "1.96<!--f:abs:stars_matched--> stars lower", "1.96<!--f:abs:stars_matched--> stars higher", "stars_matched"),
    ("survey timing swapped (surveyed after -> before)", "Late orders surveyed after delivery average", "Late orders surveyed before delivery average", "stars_sent_after"),
    ("survey timing swapped in the 1-3 day split (before <-> after)", "before delivery, 3.53<!--f:survey_near_after--> after)", "after delivery, 3.53<!--f:survey_near_after--> before)", "survey_near"),
    # more direction words, the survey-gap sentence's before/after, and months with no tag
    ("a direction flipped to 'better' (stars lower -> stars better)", "1.96<!--f:abs:stars_matched--> stars lower", "1.96<!--f:abs:stars_matched--> stars better", "stars_matched"),
    ("a direction flipped to 'up' (stars lower -> stars up)", "1.96<!--f:abs:stars_matched--> stars lower", "1.96<!--f:abs:stars_matched--> stars up", "stars_matched"),
    ("a direction flipped to 'above' (stars lower -> stars above)", "1.96<!--f:abs:stars_matched--> stars lower", "1.96<!--f:abs:stars_matched--> stars above", "stars_matched"),
    ("the survey-gap sentence's timing swapped (before -> after)", "surveys sent before delivery still score", "surveys sent after delivery still score", "survey_gap_same_days"),
    ("the analysis window's first month edited (2017-01 -> 2016-12)", "bought 2017-01", "bought 2016-12", "2016-12"),
    ("the held-out window's first month edited (2018-05 -> 2018-04)", "held in 2018-05", "held in 2018-04", "2018-04"),
    ("the spike window's first month edited (2017-11 -> 2017-10)", "late from 2017-11", "late from 2017-10", "2017-10"),
]


def main():
    n, problems = check_memo(memo, facts)
    bad = []
    ok = not problems and n > 0
    print(f"{'PASS' if ok else 'FAIL'}  the real memo: {n} numbers, problems: {problems or 'none'}")
    if not ok:
        bad.append("real memo")
    for name, old, new, expect in CASES:
        assert old in memo, f"selftest out of date: {old!r} is not in MEMO.md"
        _, found = check_memo(memo.replace(old, new, 1), facts)
        good = any(expect in p for p in found)
        print(f"{'PASS' if good else 'FAIL'}  {name}: {'caught' if found else 'NOT caught'}")
        if not good:
            bad.append(name)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
