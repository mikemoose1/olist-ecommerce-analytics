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
  abs: (a negative fact stated as a magnitude)   the sentence must not say higher, more, greater, better, above, up, rise, gain...,
                                   and must say a known decrease word (lower, fewer, less ...) or hold no comparative at all
  a survey-gap fact                the sentence must say the surveys sent before delivery score lower (not after, not higher)
  a month (YYYY-MM)                is tagged and checked like a number, or labels the month fact right after it
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
    "thin_cell": "10",                # a survey-timing day with fewer orders than this in either group is called thin (analyze.py THIN_CELL)
    "near_miss_days": "1-3", "week_days": "7",   # sizes of the "1-3 days late" and "within 7 days" shares
    "promise_short_days": "0-14", "promise_long_days": "36",   # promise-length groups
}
NUM = re.compile(r"R\$\d{1,3}(?:,\d{3})+(?:\.\d+)?(?: million)?|R\$\d+(?:\.\d+)?(?: million)?|\d+-\d+|(?<![\w])-\d+(?:\.\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")
TAG = re.compile(r"<!--(f|d):(abs:)?([^>]+?)-->")
UP = re.compile(r"\b(higher|more|greater|rises?|rose|increase[sd]?|better|above|up|gain(?:s|ed)?|exceed(?:s|ed)?|raise[sd]?|improve[sd]?)\b", re.I)
DOWN = re.compile(r"\b(lower|fewer|less|smaller|below|down|worse|drops?|dropped|fell|falls?)\b", re.I)
# a comparative the lists above do not know ("steeper", "sharper") could hide a flipped direction, so an abs:
# sentence must say a known decrease word, or hold no comparative at all. Words ending in -er that are not comparatives:
COMPARATIVE = re.compile(r"\b(?:more|less|[a-z]{2,}(?:er|ier))\b", re.I)
NOT_COMPARATIVE = {"order", "orders", "after", "other", "others", "never", "number", "numbers", "under", "customer", "customers",
                   "seller", "sellers", "however", "together", "either", "neither", "whether", "rather", "over", "per", "earlier",
                   "later", "ever", "whatever", "matter", "answer", "answered", "regression", "consider", "register", "offer",
                   "deliver", "cover", "filter", "chapter", "letter", "member", "members", "paper", "quarter", "remainder", "border"}
MONTH = re.compile(r"\b\d{4}-\d{2}\b")
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
        if "survey" in name and "gap" in name and (UP.search(before + after) or DOWN.search(before + after)):
            # the survey gap has a direction: surveys sent BEFORE delivery score lower
            text = before + after
            ok = re.search(r"\bbefore\b.*?\b(lower|fewer|less|worse)\b|\bafter\b.*?\b(higher|more|better)\b", text, re.I)
            wrong = re.search(r"\bafter\b.*?\b(lower|fewer|less|worse)\b|\bbefore\b.*?\b(higher|more|better)\b", text, re.I)
            if not ok or wrong:
                problems.append(f"tag {name}: its sentence must say the surveys sent before delivery score lower")
        if absolute and UP.search(before + after):
            problems.append(f"tag abs:{name} is a decrease, but its sentence says {UP.search(before + after).group(0)}")
        elif absolute and not DOWN.search(before + after):
            unknown = [w for w in COMPARATIVE.findall(before + after) if w.lower() not in NOT_COMPARATIVE]
            if unknown:
                problems.append(f"tag abs:{name}: its sentence compares with {unknown[0]!r}, not a known decrease word (lower, fewer, less ...)")
    # every month (YYYY-MM) is tagged, or labels the tagged month fact right after it ("2018-03 (19.2<!--f:month_2018-03-->")
    for m in MONTH.finditer(raw_text):
        tag = TAG.match(raw_text, m.end())
        label = re.match(r"\s*\(\s*[\d.,]+<!--f:month_" + re.escape(m.group(0)) + "-->", raw_text[m.end():])
        if not tag and not label:
            problems.append(f"month {m.group(0)}: no tag (a month must be tagged, or label the month fact right after it)")
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
    for m in MONTH.finditer(raw_text):        # a tagged month is checked like a number
        tag = TAG.match(raw_text, m.end())
        if tag:
            n += 1
            claimed.add(tag.start())
            want = facts.get(tag.group(3)) if tag.group(1) == "f" else DESIGN.get(tag.group(3))
            if want != m.group(0):
                problems.append(f"{m.group(0)}: tag {tag.group(1)}:{tag.group(3)} is {want}")
    problems += [f"tag {t.group(0)} follows no number" for t in TAG.finditer(raw_text) if t.start() not in claimed]
    problems += check_meaning(raw_text)
    return n, problems
