"""Tie every number in MEMO.md to the fact it states.

Each number is followed by an invisible tag:
  <!--f:late_rate-->        names a fact from the analysis run; its value must equal the number
  <!--f:abs:stars_matched--> the same, when the prose states the magnitude of a negative fact ("1.96 stars lower")
  <!--d:ci_level-->         names a design constant (a definition or test design, not a measurement), see DESIGN
Fails when a number has no tag, the tag names nothing, the value differs, or a tag follows no number.
So a number edited or swapped without changing the fact behind it fails. Moving a number AND its tag together is a visible
edit a reviewer can read.
Labels and directions are bound too, in the sentence that holds the number:
  state_XX / month_YYYY-MM   the nearest state code / month before the number must be XX / YYYY-MM
  a fact named *before* / *after*   the nearest "before" or "after" word must be the same one
  abs: (a negative fact stated as a magnitude)   the sentence must not say higher, more, greater, rise or increase
Known limit: beyond those, the check cannot know what a sentence means (a reworded claim with the right numbers passes).
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
UP = re.compile(r"\b(higher|more|greater|rises?|rose|increase[sd]?)\b", re.I)
TIMING = re.compile(r"\b(before|after)\b", re.I)


def check_meaning(raw_text):
    """Problems where a tagged number sits next to the wrong label or direction (see the module docstring)."""
    clean, cut, spots = [], 0, []
    for t in TAG.finditer(raw_text):
        clean.append(raw_text[cut:t.start()]); cut = t.end()
        spots.append((sum(map(len, clean)), t.group(2), t.group(3)))
    clean = "".join(clean) + raw_text[cut:]
    problems = []
    for at, absolute, name in spots:
        start = max(clean.rfind(c, 0, at) for c in (". ", ".\n", "\n", ": ")) + 1
        ends = [e for e in (clean.find(c, at) for c in (". ", ".\n", "\n")) if e != -1]
        before, after = clean[start:at], clean[at:min(ends) if ends else len(clean)]
        label = re.match(r"(state|month)_(.+)$", name)
        if label:
            pat = r"\b[A-Z]{2}\b" if label.group(1) == "state" else r"\b\d{4}-\d{2}\b"
            near = re.findall(pat, before)
            if not near or near[-1] != label.group(2):
                problems.append(f"tag {name} sits after {near[-1] if near else 'no label'}, not {label.group(2)}")
        timing = {"before", "after"} & set(name.split("_"))
        if timing:
            words = [(len(before) - m.end(), m.group(1).lower()) for m in TIMING.finditer(before)]
            words += [(m.start(), m.group(1).lower()) for m in TIMING.finditer(after)]
            if not words or min(words)[1] not in timing:
                problems.append(f"tag {name} sits next to {min(words)[1] if words else 'no before/after'}")
        if absolute and UP.search(before + after):
            problems.append(f"tag abs:{name} is a decrease, but its sentence says {UP.search(before + after).group(0)}")
    return problems


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
    problems += check_meaning(raw_text)
    return n, problems
