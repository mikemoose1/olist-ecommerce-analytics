"""Keep retired figures out of the docs that have no number tags.

MEMO.md and the story are tied to facts by recommendation/memo_check.py. The docs below carry no tags, so they are scanned for the
figures that were replaced:
  - the matched association the causal estimate replaced: 3,335 extra reviews (or 3335), "about 3,300", and the shares 28.7, 27.7 and
    29.4 when written as a percentage ("28.7%", "28.7 percent", "28.7 per cent")
  - the old stretch line: a 2.3 or 2.25 percentage within one sentence of the word "stretch"
Scanned: README.md, MODELING.md, review_cost_causal/README.md, recommendation/PLAN.md, and every .md file under docs/ and verification/.
A retired figure may appear only in a paragraph (text between blank lines) that holds a History note ("History:"), which names it as retired.
recommendation/selftest_docs.py proves the scan can fail. Prints one line per problem; exit 1 on any.
"""
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["README.md", "MODELING.md", "review_cost_causal/README.md", "recommendation/PLAN.md"]
TREES = ["docs", "verification"]
PCT = r"\s*(?:%|per\s?cent)"
RETIRED_ASSOCIATION = re.compile(r"(?<![\d,.])(?:3,335|3335)(?![\d])|\babout 3,300\b|(?<![\d.])(?:28\.7|27\.7|29\.4)" + PCT, re.I)
RETIRED_STRETCH = re.compile(r"stretch[^.\n]{0,80}?(?<![\d.])2\.(?:3|25)\d*" + PCT + r"|(?<![\d.])2\.(?:3|25)\d*" + PCT + r"[^.\n]{0,80}?stretch", re.I)


def doc_paths():
    out = [ROOT / f for f in FILES]
    for t in TREES:
        out += sorted((ROOT / t).rglob("*.md"))
    return [p for p in out if p.is_file()]


def problems(texts):
    """texts: {doc name: text}. Returns a list of 'doc:line: problem' strings. Paragraphs are split on blank lines;
    a paragraph holding 'History:' may name the retired figures."""
    out = []
    for name, text in texts.items():
        line_no = 1
        for para in re.split(r"(\n\s*\n)", text):
            if "History:" not in para:
                for i, line in enumerate(para.splitlines(), line_no):
                    for rx, what in ((RETIRED_ASSOCIATION, "the retired association figure"), (RETIRED_STRETCH, "the retired stretch value")):
                        for m in rx.finditer(line):
                            out.append(f"{name}:{i}: {what} {m.group(0)!r} outside a History paragraph")
            line_no += para.count("\n")
    return out


def main():
    paths = doc_paths()
    found = problems({str(p.relative_to(ROOT)): p.read_text(errors="replace") for p in paths})
    for p in found:
        print(f"FAIL  {p}")
    print(f"{'FAIL' if found else 'PASS'}  docs: {len(paths)} files scanned for retired figures, {len(found)} problems")
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
