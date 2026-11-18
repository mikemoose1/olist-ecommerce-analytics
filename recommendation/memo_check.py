"""Tie every number in MEMO.md to the fact it states.

Each number is followed by an invisible tag:
  <!--f:late_rate-->        names a fact from the analysis run; its value must equal the number
  <!--f:abs:stars_matched--> the same, when the prose states the magnitude of a negative fact ("1.96 stars lower")
  <!--d:ci_level-->         names a design constant (a definition or test design, not a measurement), see DESIGN
Fails when a number has no tag, the tag names nothing, the value differs, or a tag follows no number.
So a number edited or swapped without changing the fact behind it fails. Moving a number AND its tag together is a visible
edit a reviewer can read; the check cannot know what the sentence means.
"""
import re

DESIGN = {
    "ci_level": "95",                 # the intervals are 95% ranges
    "star_low_min": "1", "star_low_max": "2",   # "1 or 2 stars" defines a bad review
    "bucket_1_day": "1", "bucket_2_3_days": "2-3", "bucket_4_7_days": "4-7", "bucket_8_14_days": "8-14", "bucket_15_plus_days": "15",   # days-late buckets (labels above)
    "repeat_window_days": "90",       # repeat_rate_90d window (C6)
    "min_seller_orders": "20",        # sellers with fewer orders are left out of the seller concentration
    "test_weeks": "8",                # proposed test length
    "near_miss_days": "1-3", "week_days": "7",   # sizes of the "1-3 days late" and "within 7 days" shares
    "promise_short_days": "0-14", "promise_long_days": "36",   # promise-length groups
}
NUM = re.compile(r"R\$\d{1,3}(?:,\d{3})+(?:\.\d+)?(?: million)?|R\$\d+(?:\.\d+)?(?: million)?|\d+-\d+|(?<![\w])-\d+(?:\.\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
TAG = re.compile(r"<!--(f|d):(abs:)?([^>]+?)-->")


def check_memo(raw_text, facts):
    """Returns (numbers checked, problems)."""
    blank = lambda m: " " * len(m.group(0))
    masked = re.sub(r"<!--.*?-->|\b\d{4}-\d{2}\b|^\s*\d+\.(?=\s)", blank, raw_text, flags=re.S | re.M)   # tags, dates (YYYY-MM), list numbering
    problems, claimed, n = [], set(), 0
    for m in NUM.finditer(masked):
        n += 1
        tok, tag = m.group(0), TAG.match(raw_text, m.end())
        if not tag:
            problems.append(f"{tok}: no tag")
            continue
        claimed.add(tag.start())
        kind, absolute, name = tag.group(1), bool(tag.group(2)), tag.group(3)
        want = facts.get(name) if kind == "f" else DESIGN.get(name)
        if want is None:
            problems.append(f"{tok}: tag {kind}:{name} names nothing")
        elif (want.lstrip("-") != tok.lstrip("-")) if absolute else (want != tok):
            problems.append(f"{tok}: tag {kind}:{'abs:' if absolute else ''}{name} is {want}")
    problems += [f"tag {t.group(0)} follows no number" for t in TAG.finditer(raw_text) if t.start() not in claimed]
    return n, problems
