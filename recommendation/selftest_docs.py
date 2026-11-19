"""Prove recommendation/check_docs.py can fail: the real docs pass, and each planted retired figure is caught."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_docs as D

REAL = {d: (D.ROOT / d).read_text() for d in D.DOCS}
README, RCC, PLAN = (REAL[d] for d in D.DOCS)


def planted(doc, old, new):
    assert old in REAL[doc], f"selftest out of date: {old!r} is not in {doc}"
    return {**REAL, doc: REAL[doc].replace(old, new, 1)}


CASES = [   # (name, texts, must be caught)
    ("the real docs", REAL, False),
    ("README: the old 3,335 as the current estimate", planted("README.md", "about 3,110 of the 11,635", "about 3,335 of the 11,635"), True),
    ("README: the old 28.7% share", planted("README.md", "about 27%", "about 28.7%"), True),
    ("README: the old stretch value", planted("README.md", "The cost shows up in ratings.", "The stretch line is 2.3% of orders. The cost shows up in ratings."), True),
    ("review_cost_causal README: 3,335 outside a History line", planted("review_cost_causal/README.md", "about 3,110 extra 1-2 star", "about 3,335 extra 1-2 star"), True),
    ("PLAN: the old range end 29.4%", planted("recommendation/PLAN.md", "## Where late orders cluster", "The matched share was 29.4% at most.\n\n## Where late orders cluster"), True),
    ("PLAN: the old stretch value 2.25%", planted("recommendation/PLAN.md", "## Where late orders cluster", "The 2.25% stretch goal stays.\n\n## Where late orders cluster"), True),
    ("a History line may name 3,335", planted("recommendation/PLAN.md", "## Where late orders cluster", "History: the old figure was 3,335.\n\n## Where late orders cluster"), False),
    ("an unrelated 2.3 (not a stretch figure) is fine", planted("README.md", "The cost shows up in ratings.", "Without the same-day rule it is 2.31% of pairs. The cost shows up in ratings."), False),
]
bad = 0
for name, texts, want in CASES:
    found = D.problems(texts)
    ok = bool(found) == want
    bad += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {found[0] if found else 'no problem'}")
print(f"{len(CASES) - bad}/{len(CASES)} docs selftest cases PASS")
sys.exit(1 if bad else 0)
