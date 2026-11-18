"""Check the story's prose and captions (story/story.qmd).

Numbers: every number carries a tag, and recommendation/memo_check.py checks it, the same check MEMO.md passes.
  <!--f:name-->  a memo fact from analyze.py, or a story caption fact (c_*) that story/story_data.py builds from the warehouse
  <!--d:name-->  a design constant: memo_check.DESIGN, or a story threshold below
Shape: each question section (## Q...) opens with one bold one-sentence takeaway and holds exactly one chart; each chart's
key numbers are also in its section's text (CHART_KEYS, for text-only readers); each lever in "What to do" names its driver
in its bold lead (LEVER_DRIVERS); the page holds both KPI tree markers. Exit 1 on any problem. story/selftest_story.py proves it fails on planted wrong captions.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "recommendation"))
from memo_check import check_memo

STORY_DESIGN = {   # thresholds from story/QUESTIONS.md, fixed before the charts were drawn
    "thr_low_star_share": "10", "thr_segment_ratio": "1.75", "thr_segment_share": "10",
    "thr_handoff_share": "20", "thr_comment_share": "50",
}


def facts():
    rep = json.loads((ROOT / "evidence" / "recommendation_report.json").read_text())["memo_facts"]
    cap = json.loads((ROOT / "story" / "data" / "facts.json").read_text())["captions"]
    clash = set(rep) & set(cap)
    assert not clash, f"caption facts reuse memo fact names: {clash}"
    return {**rep, **cap}


def body(text):
    """The story without its YAML header, with question labels (Q1..Q9) and image targets masked."""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"^## Q\d ", "## Q  ", text, flags=re.M)
    return re.sub(r"\]\([^)]*\)\{[^}]*\}", "]()", text)


# A text-only reader must get each chart's key numbers from the words: these facts must be tagged in the chart's own section.
CHART_KEYS = {
    "fig_cost.png": ["c_low_star_excess_exact", "c_low_star_all", "low_star_share_mid", "c_late_sales_year_m"],
    "fig_where_when.png": ["nne_rate", "c_rest_rate", "month_2018-03", "month_2018-02", "month_2017-11", "c_segment_thr"],
    "fig_handoff.png": ["late_if_handoff_late", "late_if_handoff_ok", "c_handoff_late_n", "c_handoff_orders", "seller_side_pct"],
    "fig_comments.png": ["c_comment_pct", "survey_before_pct", "d:thr_comment_share"],
    "fig_repeat.png": ["rep_matched", "rep_matched_lo", "rep_matched_hi"],
}
# Each lever in the recommendation must name its driver in its own bold lead sentence.
LEVER_DRIVERS = [["late_if_handoff_late", "late_if_handoff_ok", "seller_side_pct"], ["nne_rate", "top3_months_late"]]


def tags_in(chunk):
    return {("d:" if k == "d" else "") + n.removeprefix("abs:") for k, n in re.findall(r"<!--(f|d):([^>]+?)-->", chunk)}


def check_shape(text):
    problems = []
    sections = {re.split(r"\n", s, maxsplit=1)[0]: s for s in re.split(r"^## ", text, flags=re.M)[1:]}
    for fig, keys in CHART_KEYS.items():
        sec = next((s for s in sections.values() if f"]({fig})" in s), None)
        if sec is None:
            problems.append(f"{fig}: not in the story")
            continue
        missing = [k for k in keys if k not in tags_in(sec)]
        if missing:
            problems.append(f"{fig}: key numbers only in the image, not the text: {missing}")
    todo = next((s for h, s in sections.items() if h.startswith("What to do")), "")
    items = re.findall(r"^\d+\. (\*\*.*?\*\*)", todo, re.M)
    if len(items) != len(LEVER_DRIVERS):
        problems.append(f"What to do: {len(items)} levers, want {len(LEVER_DRIVERS)}")
    for i, (lead, want) in enumerate(zip(items, LEVER_DRIVERS), 1):
        if not set(want) <= tags_in(lead):
            problems.append(f"lever {i}: its bold lead does not name its driver {sorted(set(want) - tags_in(lead))}")
    if re.search(r"\d", re.match(r"\A---\n(.*?)\n---\n", text, re.S).group(1).split("format:")[0]):
        problems.append("title or subtitle holds a number (the header cannot carry tags)")
    for m in ("<!-- KPI_TREE_TOP -->", "<!-- KPI_TREE_FULL -->"):
        if m not in text:
            problems.append(f"missing {m}")
    sections = re.split(r"^## ", text, flags=re.M)[1:]
    qs = [s for s in sections if re.match(r"Q\d ", s)]
    if not qs:
        problems.append("no question sections")
    for s in qs:
        head, *rest = s.split("\n")
        paras = [p.strip() for p in "\n".join(rest).split("\n\n") if p.strip()]
        take = paras[0] if paras else ""
        plain = re.sub(r"<!--.*?-->", "", take)
        if not (plain.startswith("**") and plain.endswith("**")) or len(re.findall(r"[.!?](?:\s|\*\*$)", plain)) != 1:
            problems.append(f"{head}: first paragraph is not one bold sentence")
        figs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", s)
        if len(figs) != 1:
            problems.append(f"{head}: {len(figs)} charts, want 1")
    return problems


def check(text, fx=None):
    n, problems = check_memo(body(text), fx or facts(), STORY_DESIGN)
    return n, problems + check_shape(text)


def main():
    text = (ROOT / "story" / "story.qmd").read_text()
    n, problems = check(text)
    for p in problems:
        print(f"FAIL  {p}")
    print(f"{'PASS' if not problems else 'FAIL'}  story.qmd: {n} numbers tied to facts, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
