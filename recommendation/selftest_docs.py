"""Prove recommendation/check_docs.py can fail: the real docs pass, and each planted retired figure is caught."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_docs as D

REAL = {str(p.relative_to(D.ROOT)): p.read_text(errors="replace") for p in D.doc_paths()}


def planted(doc, old, new):
    assert old in REAL[doc], f"selftest out of date: {old!r} is not in {doc}"
    return {**REAL, doc: REAL[doc].replace(old, new, 1)}


def added(doc, text):
    """The real docs plus one extra file (or extra text at the end of an existing one)."""
    return {**REAL, doc: REAL.get(doc, "") + "\n\n" + text}


CASES = [   # (name, texts, must be caught)
    ("the real docs", REAL, False),
    ("REPRODUCE: the old 3,335 as the current estimate", planted("docs/REPRODUCE.md", "about 3,110 of the 11,635", "about 3,335 of the 11,635"), True),
    ("REPRODUCE: the old 28.7% share", planted("docs/REPRODUCE.md", "about 27%", "about 28.7%"), True),
    ("REPRODUCE: the old share as '28.7 percent'", planted("docs/REPRODUCE.md", "about 27%", "about 28.7 percent"), True),
    ("REPRODUCE: the old share as '28.7 per cent'", planted("docs/REPRODUCE.md", "about 27%", "about 28.7 per cent"), True),
    ("REPRODUCE: the old stretch value", planted("docs/REPRODUCE.md", "The cost shows up in ratings.", "The stretch line is 2.3% of orders. The cost shows up in ratings."), True),
    ("REPRODUCE: the old stretch value as '2.25 percent'", planted("docs/REPRODUCE.md", "The cost shows up in ratings.", "The stretch line sits at 2.25 percent. The cost shows up in ratings."), True),
    ("review_cost_causal README: 3,335 outside a History paragraph", planted("review_cost_causal/README.md", "about 3,110 extra 1-2 star", "about 3,335 extra 1-2 star"), True),
    ("PLAN: the old range end 29.4%", planted("recommendation/PLAN.md", "## Where late orders cluster", "The matched share was 29.4% at most.\n\n## Where late orders cluster"), True),
    ("PLAN: the old stretch value 2.25%", planted("recommendation/PLAN.md", "## Where late orders cluster", "The 2.25% stretch goal stays.\n\n## Where late orders cluster"), True),
    ("MODELING.md is scanned: the old 3,335", added("MODELING.md", "The late-review excess is 3,335 reviews."), True),
    ("docs/ is scanned: the old stretch value", {**REAL, "docs/NEW.md": "The stretch goal is 2.3 per cent.\n"}, True),
    ("verification/ is scanned: the old share", {**REAL, "verification/NEW.md": "Matched share 27.7%.\n"}, True),
    ("a History paragraph may name 3,335", added("recommendation/PLAN.md", "History: the old figure was 3,335."), False),
    ("a History note does not cover the NEXT paragraph", added("recommendation/PLAN.md", "History: the old figure was 3,335.\n\nIt is still 3,335 today."), True),
    ("a History note covers its own multi-line paragraph", added("recommendation/PLAN.md", "History: the old matched figure\nwas 3,335 and 28.7 percent."), False),
    ("an unrelated 2.3 (not a stretch figure) is fine", planted("docs/REPRODUCE.md", "The cost shows up in ratings.", "Without the same-day rule it is 2.31% of pairs. The cost shows up in ratings."), False),
    ("an unrelated bare 28.7 (no percent sign) is fine", added("MODELING.md", "Row 28.7 of the grid."), False),
]
bad = 0
for name, texts, want in CASES:
    found = D.problems(texts)
    ok = bool(found) == want
    bad += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {found[0] if found else 'no problem'}")
print(f"{len(CASES) - bad}/{len(CASES)} docs selftest cases PASS")
sys.exit(1 if bad else 0)
