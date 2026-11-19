"""Prove story/check_story.py fails on planted wrong captions. Each case edits a copy of story.qmd (or the facts) once
and requires a problem. The untouched story must pass first."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_story as C

TEXT = (C.ROOT / "story" / "story.qmd").read_text()
FACTS = C.facts()
SF = C.story_facts()
QUESTIONS = (C.ROOT / "story" / "QUESTIONS.md").read_text()


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
    ("number in the title", edit("about a quarter of", "27% of")),
    ("seller lever loses its driver", edit("Hold sellers to their ship-by date, because late handoffs end late 21.2<!--f:late_if_handoff_late-->% of the time against 5.4<!--f:late_if_handoff_ok-->% and make up 27.8<!--f:seller_side_pct-->% of late orders.**",
                                            "Hold sellers to their ship-by date.**")),
    ("buffer lever's bold lead loses its borderline hedge", edit("% late, a borderline pass, and three highest-lateness", "% late and three highest-lateness")),
    ("buffer lever names only one driver", edit(" and three highest-lateness months held 48.3<!--f:top3_months_late-->% of late orders.**", ".**")),
    ("chart's key number left only in the image", edit(", 12.0<!--f:c_segment_thr-->% (the dashed line in the region panel),", "")),
    ("handoff denominator dropped from the text", edit(" sellers handed 8,530<!--f:c_handoff_orders--> orders over after ship-by, and", "")),
    ("late-handoff share loses its all-late-orders denominator", edit(" of all 6,518<!--f:late_orders--> late orders.", " of late orders.")),
    ("11,635 bad reviews lose their delivered single-seller scope",
     edit("11,635<!--f:c_low_star_all--> bad reviews on delivered single-seller orders (", "11,635<!--f:c_low_star_all--> bad reviews (")),
    ("caption fact changed underneath the text", lambda: (TEXT, {**FACTS, "c_comment_pct": "64.1"})),
    ("number words in a takeaway changed: two in three -> nine in ten", edit("**Two in three comments", "**Nine in ten comments")),
    ("number word in a takeaway changed: four times -> ten times", edit("about four times as often.**", "about ten times as often.**")),
    ("count of months in a takeaway changed", edit("North and northeast addresses and three highest", "North and northeast addresses and five highest")),
    ("unchecked number word added to a takeaway", edit("hold far more than their share of late orders.**", "hold twice their share of late orders.**")),
    ("numeral planted in a chart's alt text", edit('fig-alt="Bar chart of the late rate', 'fig-alt="Bar chart of the late rate, 91.5%,')),
    ("bar moved in kpi_tree.yml but not in the text", lambda: (TEXT, FACTS, {**C.design(), "thr_segment_ratio": "2"})),
    # wrong values in the accepted variants, and the cheap bypasses
    ("variant with a wrong value: nearly ten times", edit("about four times as often.**", "nearly ten times as often.**")),
    ("variant with a wrong value: about a third", edit("about a quarter of", "about a third of")),
    ("variant the range does not support: more than a quarter (the low end, 2,880, is under a quarter)", edit("about a quarter of", "more than a quarter of")),
    ("variant with a wrong value: nine tenths of comments", edit("**Two in three comments on late orders", "**Nine tenths of comments on late orders")),
    ("variant with a wrong value: the five months with the highest late rate",
     edit("addresses and three highest-lateness months hold", "addresses and the five months with the highest late rate hold")),
    ("numeral in single-quoted alt text", edit('fig-alt="Bar chart of the late rate for orders handed to the carrier after the ship-by date and on time, with ranges."',
                                                "fig-alt='Bar chart of the late rate, 91.5%, for orders handed over late and on time.'")),
    ("numeral after an escaped quote in alt text", edit('fig-alt="Bar chart of the late rate', 'fig-alt="Bar chart of \\"the\\" late rate, 91.5%,')),
    ("numeral in another header key", edit("    fig-align: left\n---", '    fig-align: left\nabstract: "Lateness is behind 91.5% of bad reviews"\n---')),
    ("number word missing from the old list: sixty", edit("**Two in three comments on late orders", "**Sixty percent of comments on late orders")),
    # story update (step 2): the causal review cost, the ramp, the alarm, goal and stretch lines, the repeat sentence
    ("causal review cost misprinted 3,110 -> 3,335", edit("about 3,110<!--f:c_cost_causal--> of the", "about 3,335<!--f:c_cost_causal--> of the")),
    ("old association figure back under its own memo tag", edit("about 3,110<!--f:c_cost_causal--> of the", "about 3,300<!--f:low_star_excess_mid--> of the")),
    ("range low end misprinted 2,880 -> 2,980", edit("between 2,880<!--f:c_cost_range_lo-->", "between 2,980<!--f:c_cost_range_lo-->")),
    ("cost range dropped from the chart's section", edit(" Six reasonable ways of making that comparison give between 2,880<!--f:c_cost_range_lo--> and 3,350<!--f:c_cost_range_hi--> reviews, the line on the bar.", "")),
    ("ramp slope misprinted 11 -> 15 points a day", edit("about 11<!--f:c_ramp_slope--> points", "about 15<!--f:c_ramp_slope--> points")),
    ("ramp plateau tagged as the on-time share", edit("near 78<!--f:c_ramp_plateau-->%", "near 78<!--f:c_ramp_on_time-->%")),
    ("alarm line misprinted 8.38 -> 8.83", edit("8.38<!--f:c_alarm_line-->", "8.83<!--f:c_alarm_line-->")),
    ("flagged month swapped 2018-02 -> 2018-01", edit("2018-02<!--f:c_flagged_2-->", "2018-01<!--f:c_flagged_2-->")),
    ("goal line misprinted 4.4 -> 3.0 (the safe goal, not drawn)", edit("the goal, 4.4<!--f:c_goal_line-->%", "the goal, 3.0<!--f:c_goal_line-->%")),
    ("stretch line left only in the image", edit("faint dashed line at 3.4<!--f:c_stretch_line-->% (3.43<!--f:c_stretch_exact-->%)", "faint dashed line")),
    ("what-if rate misprinted 5.49 -> 4.49", edit("5.49<!--f:c_whatif_rate-->", "4.49<!--f:c_whatif_rate-->")),
    ("repeat sentence reworded (somewhat -> much less likely)", edit("were somewhat less likely to order again", "were much less likely to order again")),
    ("repeat rate misprinted 1.0 -> 0.5", edit("about 1.0<!--f:c_rep_late_1dp-->%", "about 0.5<!--f:c_rep_late_1dp-->%")),
    ("repeat evidence no longer ties to the recommendation report (late returners 58 -> 63)",
     lambda: (TEXT, FACTS, None, {**SF, "repeat": {**SF["repeat"], "evidence_rep90": {**SF["repeat"]["evidence_rep90"], "late_k": 63}}})),
    ("'a few thousand reais' no longer holds (top of the range R$25,000)",
     lambda: (TEXT, FACTS, None, {**SF, "repeat": {**SF["repeat"], "revenue_high": 25000.0}})),
    ("QUESTIONS.md keeps the old 3,335", lambda: (TEXT, FACTS, None, None, QUESTIONS.replace("About 3,110 extra", "About 3,335 extra", 1))),
    ("QUESTIONS.md Q2 loses the goal line", lambda: (TEXT, FACTS, None, None, QUESTIONS.replace("The goal line is 4.4%, ", "The goal line is ", 1))),
    # stretch line, 3.4%: the retired 2.3% / 2.25% cannot come back, and its label cannot be softened or dropped
    ("retired stretch back: facts rebuilt to 2.3 / 2.25 and the story reprinted with them",
     lambda: (TEXT.replace("3.4<!--f:c_stretch_line-->", "2.3<!--f:c_stretch_line-->").replace("3.43<!--f:c_stretch_exact-->", "2.25<!--f:c_stretch_exact-->"),
              {**FACTS, "c_stretch_line": "2.3", "c_stretch_exact": "2.25"}), "retired stretch value"),
    ("retired stretch back in the facts only (the story still prints 3.4)",
     lambda: (TEXT, {**FACTS, "c_stretch_line": "2.3", "c_stretch_exact": "2.25"}), "retired stretch value"),
    ("stretch line misprinted 3.4 -> 2.9", edit("at 3.4<!--f:c_stretch_line-->%", "at 2.9<!--f:c_stretch_line-->%"), "c_stretch_line"),
    ("stretch gap misprinted about 1.0 -> 2.0 point", edit("about 1.0<!--f:c_whatif_gap--> point (single", "about 2.0<!--f:c_whatif_gap--> point (single"), "c_whatif_gap"),
    ("stretch line called a tested cause", edit("a what-if, not a tested cause. It redoes", "a result. It redoes"), "word for word"),
    ("stretch line loses 'middle month'", edit("shows the middle month if late seller handoffs", "shows a good month if late seller handoffs"), "word for word"),
    ("'not a randomized test' dropped from the cost paragraph", edit("This is an estimate from past orders, not a randomized test.", "This is an estimate from past orders."), "word for word"),
    ("flagged-month count says four months", edit("Three months crossed it:", "Four months crossed it:"), "flagged-month count"),
    ("flagged-month sentence removed", edit("Three months crossed it:", "Some months crossed it:"), "flagged-month count"),
    ("QUESTIONS.md keeps the retired stretch 2.3%",
     lambda: (TEXT, FACTS, None, None, QUESTIONS.replace("A faint stretch line at 3.4% (3.43%)", "A faint stretch line at 2.3% (3.43%)", 1)), "retired stretch value"),
    ("QUESTIONS.md Q2 loses the stretch value",
     lambda: (TEXT, FACTS, None, None, QUESTIONS.replace("A faint stretch line at 3.4% (3.43%)", "A faint stretch line", 1)), "c_stretch_line"),
    # bare or proven cause wording, and the stretch gap clause, are required word for word
    ("bold headline drops 'estimated': 'Late deliveries cause about 3,110'", edit("**Late deliveries are the estimated cause of about 3,110<!--f:c_cost_causal-->", "**Late deliveries cause about 3,110<!--f:c_cost_causal-->"), "drops 'estimated'"),
    ("recommendation drops 'estimated': 'Late deliveries cause about 3,110'", edit("Late deliveries are the estimated cause of about 3,110<!--f:c_cost_causal--> extra reviews", "Late deliveries cause about 3,110<!--f:c_cost_causal--> extra reviews"), "drops 'estimated'"),
    ("recommendation says 'are proven to cause'", edit("Late deliveries are the estimated cause of about 3,110<!--f:c_cost_causal--> extra reviews", "Late deliveries are proven to cause 3,110<!--f:c_cost_causal--> extra reviews"), "claims a proof"),
    ("'each extra day late proves the delay itself causes the damage'", edit("though part of that climb is survey timing.", "and each extra day late proves the delay itself causes the damage."), "claims a proof"),
    ("headline sentence reworded without 'estimated' (still no bare cause)", edit("Late deliveries are the estimated cause of about 3,110<!--f:c_cost_causal--> of the", "Late deliveries account for about 3,110<!--f:c_cost_causal--> of the"), "word for word"),
    ("gap clause reworded: 'best quartile of the same stable months'", edit("takes the median of the same stable months as the goal", "takes the best quartile of the same stable months as the goal"), "word for word"),
    ("gap read reworded: 'what that what-if alone is worth'", edit("is a median-scale read of the what-if, about 1.0", "is what that what-if alone is worth, about 1.0"), "word for word"),
    ("gap range high end misprinted 2.9 -> 3.9", edit("to 2.9<!--f:c_whatif_gap_hi-->", "to 3.9<!--f:c_whatif_gap_hi-->"), "c_whatif_gap_hi"),
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
    ("variant: nearly a quarter", edit("about a quarter of", "nearly a quarter of")),
    ("variant: two thirds of comments", edit("**Two in three comments on late orders", "**Two thirds of comments on late orders")),
    ("variant: the three months with the highest late rate",
     edit("addresses and three highest-lateness months hold", "addresses and the three months with the highest late rate hold")),
]


def main():
    n, base = C.check(TEXT, FACTS)
    print(f"{'PASS' if not base else 'FAIL'}  untouched story passes ({n} numbers)" + (f": {base}" if base else ""))
    fails = bool(base)
    for name, make, *expect in CASES:
        text, fx, *design = make()
        _, problems = C.check(text, fx, *design)
        hit = [p for p in problems if not expect or expect[0] in p]   # a case with an expected phrase must be caught for that reason
        fails |= not hit
        print(f"{'PASS' if hit else 'FAIL'}  {name}: " + (f"caught ({hit[0]})" if hit else f"NOT caught{' for the right reason' if problems else ''}"))
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
