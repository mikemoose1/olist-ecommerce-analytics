"""Keep retired figures out of the docs that have no number tags (README.md, review_cost_causal/README.md, recommendation/PLAN.md).

MEMO.md and the story are tied to facts by recommendation/memo_check.py. These three files carry no tags, so they are scanned
for the figures that were replaced:
  - the matched association the causal estimate replaced: 3,335 extra reviews, 28.7%, 27.7%, 29.4%, "about 3,300"
  - the old stretch line: a 2.3% or 2.25% figure within one sentence of the word "stretch"
A retired figure may appear only on a line that holds a History note ("History:"), which names it as retired.
recommendation/selftest_docs.py proves the scan can fail. Prints one line per problem; exit 1 on any.
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ["README.md", "review_cost_causal/README.md", "recommendation/PLAN.md"]
RETIRED_ASSOCIATION = re.compile(r"(?<![\d,.])(?:3,335|3335|28\.7|27\.7|29\.4)(?![\d])|about 3,300")
RETIRED_STRETCH = re.compile(r"stretch[^.\n]{0,80}?(?<![\d.])2\.(?:3|25)\d*\s*%|(?<![\d.])2\.(?:3|25)\d*\s*%[^.\n]{0,80}?stretch", re.I)


def problems(texts):
    """texts: {doc name: text}. Returns a list of 'doc:line: problem' strings."""
    out = []
    for name, text in texts.items():
        for i, line in enumerate(text.splitlines(), 1):
            if "History:" in line:
                continue
            for rx, what in ((RETIRED_ASSOCIATION, "the retired association figure"), (RETIRED_STRETCH, "the retired stretch value")):
                for m in rx.finditer(line):
                    out.append(f"{name}:{i}: {what} {m.group(0)!r} outside a History note")
    return out


def main():
    found = problems({d: (ROOT / d).read_text() for d in DOCS})
    for p in found:
        print(f"FAIL  {p}")
    print(f"{'FAIL' if found else 'PASS'}  docs: {len(DOCS)} files scanned for retired figures, {len(found)} problems")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
