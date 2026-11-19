"""Honest titles pass story/check_titles.py (scripts/prove_tests_fail.py proves the wrong ones fail on the real files)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_titles as T

STORY = (T.ROOT / "story" / "story.qmd").read_text()
MEMO = (T.ROOT / "recommendation" / "MEMO.md").read_text()
TITLE = "Late deliveries are linked to about a quarter of the bad reviews on delivered single-seller Olist orders"
CASES = [   # (name, story text, memo text, title that must pass or fail, should pass)
    ("the real titles", STORY, MEMO, None, True),
    ("'because' in a title is not cause wording", STORY.replace(TITLE, TITLE + ", because parcels arrive late", 1), MEMO, "story title", True),
    ("'linked to' in capitals", STORY.replace("linked to", "Linked To", 1), MEMO, "story title", True),
    ("'Caused' at the start of the memo title", STORY, MEMO.replace("# Late deliveries:", "# Caused by late deliveries:", 1), "memo title", False),
]
bad = 0
for name, story, memo, which, want in CASES:
    assert which is None or story != STORY or memo != MEMO, f"selftest out of date: {name} edits nothing"
    got = T.problems(story, memo)
    ok = (not any(got.values())) if which is None else (not got[which]) == want
    bad += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}: {got if not ok else ('passes' if want else 'caught')}")
print(f"{len(CASES) - bad}/{len(CASES)} title selftest cases PASS")
sys.exit(1 if bad else 0)
