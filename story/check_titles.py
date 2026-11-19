"""The story's and the memo's titles describe the review cost as a link, not a cause.

Design note: the title says late deliveries are "linked to" the bad reviews, while the body keeps its
"estimated cause" wording with the method and range beside it. A title is read alone, so it carries no caveat.
  - the story title and subtitle, and the memo title (its first "# " line), must not use cause wording: cause, causes, caused,
    causing, causal, drive, drives, driven, driving, drove, "result in", "results in", "resulted in", "lead to", "leads to",
    "led to", "leading to", trigger, triggers, triggered, "responsible for"
  - the story title and the memo title must both say "linked to"
STORY_QMD and MEMO_MD point the check at edited copies (scripts/prove_tests_fail.py uses them); defaults are the real files.
Prints one PASS or FAIL line per title and exits 1 on any FAIL.
"""
import os, re, sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CAUSE = re.compile(r"\bcaus(?:e|es|ed|ing|al)\b|\bdriv(?:e|es|en|ing)\b|\bdrove\b|\bresult(?:s|ed|ing)? in\b|\b(?:lead|leads|led|leading) to\b|\btrigger(?:s|ed|ing)?\b|\bresponsible for\b", re.I)
# "because" does not match: no word boundary before "caus"; "driver" and "results" alone do not match


def story_titles(text):
    header = yaml.safe_load(text.split("---", 2)[1])
    return {"story title": str(header.get("title", "")), "story subtitle": str(header.get("subtitle", ""))}


def memo_title(text):
    first = next((l for l in text.splitlines() if l.startswith("# ")), "")
    return {"memo title": first[2:]}


def problems(story_text, memo_text):
    """{title name: [problems]} for the story title, story subtitle and memo title."""
    out = {}
    for name, title in {**story_titles(story_text), **memo_title(memo_text)}.items():
        p = [f"says {m.group(0)!r}; a title says 'linked to', not cause or drive or lead to" for m in CAUSE.finditer(title)]
        if name in ("story title", "memo title") and "linked to" not in title.lower():
            p.append("does not say 'linked to'")
        if name != "story subtitle" and not title.strip():
            p.append("is missing")
        out[name] = p
    return out


def main():
    story = Path(os.environ.get("STORY_QMD", ROOT / "story" / "story.qmd")).read_text()
    memo = Path(os.environ.get("MEMO_MD", ROOT / "recommendation" / "MEMO.md")).read_text()
    bad = 0
    for name, p in problems(story, memo).items():
        bad += bool(p)
        print(f"{'FAIL' if p else 'PASS'}  title {name}: {'; '.join(p) if p else 'no cause wording'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
