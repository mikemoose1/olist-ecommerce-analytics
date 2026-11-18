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
    ("highest-lateness month mislabelled", edit("2018-03 (19.2<!--f:month_2018-03-->", "2018-02 (19.2<!--f:month_2018-03-->")),
    ("takeaway split into two sentences", edit("arrives late about four times as often.**", "arrives late. It happens about four times as often.**")),
    ("second chart in a question section", edit("![](fig_repeat.png)", "![](fig_repeat.png)\n\n![](fig_cost.png)")),
    ("number in the title", edit("more than a quarter of", "28.7% of")),
    ("seller lever loses its driver", edit("Hold sellers to their ship-by date, because late handoffs end late 21.2<!--f:late_if_handoff_late-->% of the time against 5.4<!--f:late_if_handoff_ok-->% and make up 27.8<!--f:seller_side_pct-->% of late orders.**",
                                            "Hold sellers to their ship-by date.**")),
    ("buffer lever's bold lead loses its borderline hedge", edit("% late, a borderline pass, and three highest-lateness", "% late and three highest-lateness")),
    ("buffer lever names only one driver", edit(" and three highest-lateness months held 48.3<!--f:top3_months_late-->% of late orders.**", ".**")),
    ("chart's key number left only in the image", edit(", 12.0<!--f:c_segment_thr-->% (the dashed line),", "")),
    ("handoff denominator dropped from the text", edit(" out of 8,530<!--f:c_handoff_orders--> handed over after ship-by", "")),
    ("caption fact changed underneath the text", lambda: (TEXT, {**FACTS, "c_comment_pct": "64.1"})),
    ("number words in a takeaway changed: two in three -> nine in ten", edit("**Two in three comments", "**Nine in ten comments")),
    ("number word in a takeaway changed: four times -> ten times", edit("about four times as often.**", "about ten times as often.**")),
    ("count of months in a takeaway changed", edit("North and northeast addresses and three highest", "North and northeast addresses and five highest")),
    ("unchecked number word added to a takeaway", edit("hold far more than their share of late orders.**", "hold twice their share of late orders.**")),
    ("numeral planted in a chart's alt text", edit('fig-alt="Bar chart of the late rate', 'fig-alt="Bar chart of the late rate, 91.5%,')),
    ("bar moved in kpi_tree.yml but not in the text", lambda: (TEXT, FACTS, {**C.design(), "thr_segment_ratio": "2"})),
    # wrong values in the accepted variants, and the cheap bypasses
    ("variant with a wrong value: nearly ten times", edit("about four times as often.**", "nearly ten times as often.**")),
    ("variant with a wrong value: over a third", edit("more than a quarter of", "over a third of")),
    ("variant with a wrong value: nine tenths of comments", edit("**Two in three comments on late orders", "**Nine tenths of comments on late orders")),
    ("variant with a wrong value: the five months with the highest late rate",
     edit("addresses and three highest-lateness months hold", "addresses and the five months with the highest late rate hold")),
    ("numeral in single-quoted alt text", edit('fig-alt="Bar chart of the late rate for orders handed to the carrier after the ship-by date and on time, with ranges."',
                                                "fig-alt='Bar chart of the late rate, 91.5%, for orders handed over late and on time.'")),
    ("numeral after an escaped quote in alt text", edit('fig-alt="Bar chart of the late rate', 'fig-alt="Bar chart of \\"the\\" late rate, 91.5%,')),
    ("numeral in another header key", edit("    fig-align: left\n---", '    fig-align: left\nabstract: "Lateness is behind 91.5% of bad reviews"\n---')),
    ("number word missing from the old list: sixty", edit("**Two in three comments on late orders", "**Sixty percent of comments on late orders")),
    ("number word missing from the old list: none", edit("hold far more than their share of late orders.**", "hold far more than their share of late orders, and none of the rest do.**")),
]

# Honest edits with no wrong number. Each must leave the story with no problems.
MUST_PASS = [
    ("number-free subtitle: the tests", edit("and two tests that would show", "and the tests that would show")),
    ("number-free heading: run these tests", edit("## What to do: two tests", "## What to do: run these tests")),
    ("number-free takeaway: the highest-lateness months", edit("addresses and three highest-lateness months hold", "addresses and the highest-lateness months hold")),
    ("number-free takeaway: these peak months", edit("addresses and three highest-lateness months hold", "addresses and these peak months hold")),
    ("number-free takeaway: Delays in late comments", edit("**Two in three comments on late orders are about", "**Delays in late comments are mostly about")),
    ("variant: nearly four times as often", edit("about four times as often.**", "nearly four times as often.**")),
    ("variant: over a quarter", edit("more than a quarter of", "over a quarter of")),
    ("variant: two thirds of comments", edit("**Two in three comments on late orders", "**Two thirds of comments on late orders")),
    ("variant: the three months with the highest late rate",
     edit("addresses and three highest-lateness months hold", "addresses and the three months with the highest late rate hold")),
]


def main():
    n, base = C.check(TEXT, FACTS)
    print(f"{'PASS' if not base else 'FAIL'}  untouched story passes ({n} numbers)" + (f": {base}" if base else ""))
    fails = bool(base)
    for name, make in CASES:
        text, fx, *design = make()
        _, problems = C.check(text, fx, *design)
        fails |= not problems
        print(f"{'PASS' if problems else 'FAIL'}  {name}: " + (f"caught ({problems[0]})" if problems else "NOT caught"))
    for name, make in MUST_PASS:
        text, fx, *design = make()
        _, problems = C.check(text, fx, *design)
        fails |= bool(problems)
        print(f"{'PASS' if not problems else 'FAIL'}  honest edit accepted: {name}" + (f": REJECTED ({problems[0]})" if problems else ""))
    total = len(CASES) + len(MUST_PASS) + 1
    print("SELFTEST FAILED" if fails else f"{total}/{total} story caption selftest cases PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
