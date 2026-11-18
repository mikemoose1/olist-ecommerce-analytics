"""Prove story/check_story.py fails on planted wrong captions. Each case edits a copy of story.qmd (or the facts) once
and requires a problem. The untouched story must pass first."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_story as C

TEXT = (C.ROOT / "story" / "story.qmd").read_text()
FACTS = C.facts()


def edit(old, new):
    def f():
        assert old in TEXT, f"selftest anchor gone: {old[:60]!r}"
        return TEXT.replace(old, new, 1), FACTS
    return f


CASES = [
    ("comment share misprinted 66.7 -> 76.7", edit("66.7<!--f:c_comment_pct-->", "76.7<!--f:c_comment_pct-->")),
    ("north-and-northeast rate tagged as the rest-of-Brazil rate", edit("12.2<!--f:nne_rate-->", "12.2<!--f:c_rest_rate-->")),
    ("untagged number added to a takeaway", edit("hold far more than their share of late orders.**", "hold far more than their share of late orders, about 1,302 of them.**")),
    ("star penalty direction flipped", edit("score 1.96<!--f:abs:stars_matched--> stars lower", "score 1.96<!--f:abs:stars_matched--> stars higher")),
    ("peak month mislabelled", edit("2018-03 (19.2<!--f:month_2018-03-->", "2018-02 (19.2<!--f:month_2018-03-->")),
    ("takeaway split into two sentences", edit("arrives late about four times as often.**", "arrives late. It happens about four times as often.**")),
    ("second chart in a question section", edit("![](fig_repeat.png)", "![](fig_repeat.png)\n\n![](fig_cost.png)")),
    ("number in the title", edit("more than a quarter of", "28.7% of")),
    ("seller lever loses its driver", edit("Hold sellers to their ship-by date, because late handoffs end late 21.2<!--f:late_if_handoff_late-->% of the time against 5.4<!--f:late_if_handoff_ok-->% and make up 27.8<!--f:seller_side_pct-->% of late orders.**",
                                            "Hold sellers to their ship-by date.**")),
    ("buffer lever names only one driver", edit(" and three peak months held 48.3<!--f:top3_months_late-->% of late orders.**", ".**")),
    ("chart's key number left only in the image", edit(", 12.0<!--f:c_segment_thr-->% (the dashed line),", "")),
    ("handoff denominator dropped from the text", edit(" out of 8,530<!--f:c_handoff_orders--> handed over after ship-by", "")),
    ("caption fact changed underneath the text", lambda: (TEXT, {**FACTS, "c_comment_pct": "64.1"})),
]


def main():
    n, base = C.check(TEXT, FACTS)
    print(f"{'PASS' if not base else 'FAIL'}  untouched story passes ({n} numbers)" + (f": {base}" if base else ""))
    fails = bool(base)
    for name, make in CASES:
        text, fx = make()
        _, problems = C.check(text, fx)
        fails |= not problems
        print(f"{'PASS' if problems else 'FAIL'}  {name}: " + (f"caught ({problems[0]})" if problems else "NOT caught"))
    print("SELFTEST FAILED" if fails else f"{len(CASES) + 1}/{len(CASES) + 1} story caption selftest cases PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
