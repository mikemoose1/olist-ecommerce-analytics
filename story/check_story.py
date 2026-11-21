"""Check the story's prose and captions (story/story.qmd).

Numbers: every number carries a tag, and recommendation/memo_check.py checks it, the same check MEMO.md passes.
  <!--f:name-->  a memo fact from analyze.py, or a story caption fact (c_*) that story/story_data.py builds from the warehouse
  <!--d:name-->  a design constant: memo_check.DESIGN, or a story threshold below
Shape: each question section (## Q...) opens with one bold one-sentence takeaway and holds exactly one chart; each chart's
key numbers are also in its section's text (CHART_KEYS, for text-only readers); each lever in "What to do" names its driver
in its bold lead (LEVER_DRIVERS); a scoped count carries its population right after it (SCOPED_FACTS); and a lever that failed its pass bar says so there (LEVER_HEDGES); the page holds both KPI tree markers.
Number words: the title, subtitle, headings, bold lines and chart alt text cannot carry tags, so every number word there
("two in three", "about four times", "three ... months") must sit in a phrase of NUMBER_PHRASES that checks it against the
facts, and alt text (either quote style) and every header string outside `format:` hold no numerals.
Out of scope: whether a phrase's subject is right ("more than a quarter of sellers" passes if the share is), and number
words in body prose, where every numeral already carries a tag. Exit 1 on any problem. story/selftest_story.py proves it fails on planted wrong captions.
"""
import json, re, sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "recommendation"))
sys.path.insert(0, str(ROOT / "story"))
from memo_check import DESIGN, RETIRED_TAGS, check_memo, story_sentences
from kpi_tree import NUMBER_WORD   # the number-word list kpi_tree.py also uses for threshold text

def design():
    """Story design numbers: the bars in kpi_tree.yml `thresholds:` (the one source), as d:thr_<name> tags."""
    bars = yaml.safe_load((ROOT / "story" / "kpi_tree.yml").read_text())["thresholds"]
    return {f"thr_{k}": f"{v:g}" for k, v in bars.items()}


def facts():
    rep = json.loads((ROOT / "evidence" / "recommendation_report.json").read_text())["memo_facts"]
    cap = json.loads((ROOT / "story" / "data" / "facts.json").read_text())["captions"]
    # the memo prints some caption facts too (recommendation/analyze.py adds story_data.causal_captions); a shared name
    # must hold the same value in both files, so neither can silently override the other
    clash = {k: (rep[k], cap[k]) for k in set(rep) & set(cap) if rep[k] != cap[k]}
    assert not clash, f"memo facts and caption facts disagree: {clash}"
    return {**rep, **cap}


def body(text):
    """The story without its YAML header, with question labels (Q1..Q9) and image targets masked."""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"^## Q\d ", "## Q  ", text, flags=re.M)
    return re.sub(r"\]\([^)]*\)\{[^}]*\}", "]()", text)


# A text-only reader must get each chart's key numbers from the words: these facts must be tagged in the chart's own section.
CHART_KEYS = {
    "fig_cost.png": ["c_cost_causal", "c_low_star_all", "c_cost_causal_share", "c_cost_range_lo", "c_cost_range_hi",
                     "c_ramp_on_time", "c_ramp_slope", "c_ramp_plateau", "c_ramp_end_day", "c_late_sales_last12_m", "c_late_sales_last12_share"],
    "fig_where_when.png": ["nne_rate", "c_rest_rate", "month_2018-03", "month_2018-02", "month_2017-11", "c_segment_thr",
                           "c_alarm_line", "c_flagged_1", "c_flagged_2", "c_flagged_3", "c_goal_line", "c_stretch_line"],
    "fig_handoff.png": ["late_if_handoff_late", "late_if_handoff_ok", "c_handoff_late_n", "c_handoff_orders", "seller_side_pct",
                        "late_orders"],
    "fig_comments.png": ["c_comment_pct", "survey_before_pct", "d:thr_comment_share"],
    "fig_repeat.png": ["rep_matched", "rep_matched_lo", "rep_matched_hi"],
}
# Each lever in the recommendation must name its driver in its own bold lead sentence.
# A lever that rests on a borderline pass must say so in its bold lead (wave-4 readers missed the hedge in the body).
LEVER_HEDGES = ["not ready", None]
LEVER_DRIVERS = [["ddm_olist_extra", "ddm_model_extra", "ddm_model_extra_days"], ["ddm_sellers_late_flagged", "ddm_sellers_late_other"]]


WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12}
FRACTIONS = {"half": 2, "halves": 2, "third": 3, "thirds": 3, "quarter": 4, "quarters": 4, "fifth": 5, "fifths": 5,
             "tenth": 10, "tenths": 10}
N = r"(" + "|".join(WORDS) + r")"          # a counted number word, captured
F = r"(" + "|".join(FRACTIONS) + r")"      # a fraction word, captured
NEAR = r"(?:about|nearly|almost|roughly|around)"


def num(x):
    return float(str(x).replace(",", "").replace("R$", ""))


def _w(m, i=1):
    return WORDS[m.group(i).lower()]


def _share_ok(share, pct):
    return abs(100 * share - num(pct)) <= 5


# phrase regex -> (what it claims, test against facts f and design d). A number word outside these phrases is a problem.
# Each phrase starts with a number word, so number-free wording ("the tests", "these peak months") never matches.
NUMBER_PHRASES = [
    (rf"\b{N} in {N} comments", "comment share", lambda m, f, d: _share_ok(_w(m) / _w(m, 2), f["c_comment_pct"])),
    (rf"\b{N} {F} of comments", "comment share",
     lambda m, f, d: _share_ok(_w(m) / FRACTIONS[m.group(2).lower()], f["c_comment_pct"])),
    (rf"\b{NEAR} {N} times as often", "late-handoff ratio", lambda m, f, d: _w(m) == round(num(f["c_handoff_ratio"]))),
    (rf"\b(?:more than|over) {N} times as often", "late-handoff ratio", lambda m, f, d: num(f["c_handoff_ratio"]) > _w(m)),
    # the causal review cost: "more than a quarter" must hold at the low end of the range across specifications,
    # "about a quarter" within 3 points of the central estimate
    (rf"\b(?:more than|over) an? {F}\b", "caused low-star share (low end of the range)",
     lambda m, f, d: 100 * num(f["c_cost_range_lo"]) / num(f["c_low_star_all"]) > 100 / FRACTIONS[m.group(1).lower()]),
    (rf"\b{NEAR} an? {F}\b", "caused low-star share",
     lambda m, f, d: abs(num(f["c_cost_causal_share"]) - 100 / FRACTIONS[m.group(1).lower()]) <= 3),
    (rf"\b{N} (?:highest-lateness|peak) months", "number of top months",
     lambda m, f, d: _w(m) == sum(k.startswith("month_") for k in f)),
    (rf"\b{N} months with the highest late rate", "number of top months",
     lambda m, f, d: _w(m) == sum(k.startswith("month_") for k in f)),
    (rf"\b{N} (?:tests|levers)\b", "number of levers", lambda m, f, d: _w(m) == len(LEVER_DRIVERS)),
    (r"\bone- and two-star", "low-star definition", lambda m, f, d: (d["star_low_min"], d["star_low_max"]) == ("1", "2")),
    (r"\bat one half\b", "comment bar", lambda m, f, d: d["thr_comment_share"] == "50"),
]
ALT = re.compile(r"""\b(?:fig-alt|fig-cap|alt)=(["'])((?:\\.|(?!\1).)*)\1""", re.S)


def header_text(text):
    """Every string in the YAML header except the `format:` options: title, subtitle, abstract, description, ..."""
    hdr = yaml.safe_load(re.match(r"\A---\n(.*?)\n---\n", text, re.S).group(1)) or {}
    out = []
    def walk(x):
        if isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
        elif x is not None and not isinstance(x, bool):
            out.append(str(x))
    walk({k: v for k, v in hdr.items() if k != "format"})
    return "\n".join(out)


def untaggable(text):
    """Text that cannot carry tags: the header, headings, bold spans, and chart alt text (either quote style)."""
    rest = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    bold = re.findall(r"\*\*(.+?)\*\*", rest, re.S)
    heads = re.findall(r"^#+ (.*)$", rest, re.M)
    alts = [m.group(2) for m in ALT.finditer(rest)]
    clean = lambda t: re.sub(r"<!--.*?-->", "", t)
    return [("header", header_text(text))] + [("bold", clean(b)) for b in bold] + [("heading", h) for h in heads] + [("alt", a) for a in alts]


def check_number_words(text, f, d):
    problems = []
    for where, chunk in untaggable(text):
        if where in ("alt", "header") and re.search(r"\d", chunk):
            problems.append(f"{where} holds a numeral (it cannot carry a tag): {chunk[:70]!r}")
        covered = set()
        for pat, what, ok in NUMBER_PHRASES:
            for m in re.finditer(pat, chunk, re.I):
                covered |= set(range(*m.span()))
                if not ok(m, f, d):
                    problems.append(f"{where}: {m.group(0)!r} does not match the facts ({what})")
        for m in re.finditer(NUMBER_WORD, chunk, re.I):
            if m.start() not in covered:
                problems.append(f"{where}: number word {m.group(0)!r} is not checked against a fact: {chunk[:70]!r}")
    return problems


# A count that readers repeat without its population: wherever it is printed, its scope must follow within SCOPE_WINDOW
# characters of plain text (wave-4 and wave-5 readers dropped "delivered single-seller" from the 11,635).
SCOPED_FACTS = {"c_low_star_all": "delivered single-seller orders"}
SCOPE_WINDOW = 60


def check_scope(text):
    problems = []
    for name, scope in SCOPED_FACTS.items():
        for m in re.finditer(rf"<!--f:{re.escape(name)}-->", text):
            after = re.sub(r"<!--.*?-->", "", text[m.end():m.end() + 400])[:SCOPE_WINDOW]
            if scope not in after:
                problems.append(f"f:{name} is printed without its scope '{scope}' right after it: {after!r}")
    return problems


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
    for i, (lead, hedge) in enumerate(zip(items, LEVER_HEDGES), 1):
        if hedge and hedge not in lead.lower():
            problems.append(f"lever {i}: its bold lead does not carry its hedge {hedge!r}")
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


def story_facts():
    return json.loads((ROOT / "story" / "data" / "facts.json").read_text())


def plain(text):
    """What a reader sees: tags dropped, whitespace collapsed."""
    return re.sub(r"\s+", " ", re.sub(r"<!--.*?-->", "", text))


FEW_THOUSAND = (1_000, 10_000)   # "at most a few thousand reais": the top of every repeat-sales range sits in [1,000, 10,000)


def check_repeat(text, sf):
    """The repeat sentence is printed word for word, its counts tie to the recommendation report, and its money words hold."""
    rp, problems = sf["repeat"], []
    if rp["sentence"] not in plain(text):
        problems.append("repeat sentence is not printed word for word (evidence/repeat_first_order_report.json story_sentence)")
    ev = rp["evidence_rep90"]
    for what, n_ev, k_ev, n_rep, rate_rep in (("late", ev["late_n"], ev["late_k"], rp["n_late"], rp["late"]),
                                              ("on-time", ev["ontime_n"], ev["ontime_k"], rp["n_on_time"], rp["on_time"])):
        if n_ev != n_rep or abs(k_ev / n_ev - rate_rep) >= 5e-7:
            problems.append(f"repeat evidence ({what} first orders {k_ev}/{n_ev}) does not tie to the recommendation report ({rate_rep} of {n_rep})")
    if not FEW_THOUSAND[0] <= rp["revenue_high"] < FEW_THOUSAND[1]:
        problems.append(f"'at most a few thousand reais' does not hold: the top of the repeat-sales range is R${rp['revenue_high']:,.0f}")
    return problems


# QUESTIONS.md answers repeat the story's new numbers in words a reader can check: each listed caption fact must be printed
# in its question's section, and the replaced figures must be gone.
QUESTION_FACTS = {"Q1": ["c_cost_causal", "c_cost_causal_share", "c_cost_range_lo", "c_cost_range_hi", "c_ramp_on_time", "c_ramp_slope", "c_ramp_plateau"],
                  "Q2": ["c_alarm_line", "c_goal_line", "c_goal_exact", "c_stretch_line", "c_stretch_exact", "c_whatif_rate", "c_whatif_gap", "c_whatif_gap_lo", "c_whatif_gap_hi"],
                  "Q5": ["c_rep_late_1dp", "c_rep_on_time_1dp"]}
RETIRED = ["3,335", "28.7%", "linked to about 3,300"]
# a stretch value stated in QUESTIONS.md prose, which carries no tags: the retired 25th-percentile stretch, 2.3% or 2.25%
RETIRED_STRETCH_PROSE = re.compile(r"stretch[^.]{0,80}?\b2\.(?:3|25)%|\b2\.(?:3|25)%[^.]{0,80}?stretch", re.I)
# sentences the story must keep word for word (tags removed): the cause wording and the stretch line's meaning
# (memo_check.story_sentences builds them from the facts)


def check_questions(questions, fx):
    problems = []
    secs = {m.group(1): m.group(0) for m in re.finditer(r"^### (Q\d+)\..*?(?=^### |^## |\Z)", questions, re.M | re.S)}
    for q, names in QUESTION_FACTS.items():
        for name in names:
            if not re.search(rf"(?<![\d,.]){re.escape(fx[name])}(?!\d|[.,]\d)", secs.get(q, "")):
                problems.append(f"QUESTIONS.md {q}: does not state {name} = {fx[name]}")
    prose = re.sub(r"<!-- kpi-tree:start.*?<!-- kpi-tree:end -->", "", questions, flags=re.S)
    problems += [f"QUESTIONS.md still states the replaced figure {old!r}" for old in RETIRED if old in prose]
    problems += [f"QUESTIONS.md still states the retired stretch value: {m.group(0)!r}" for m in RETIRED_STRETCH_PROSE.finditer(prose)]
    return problems


def check(text, fx=None, design_numbers=None, sf=None, questions=None):
    fx, d, sf = fx or facts(), design_numbers or design(), sf or story_facts()
    questions = questions if questions is not None else (ROOT / "story" / "QUESTIONS.md").read_text()
    n, problems = check_memo(body(text), fx, d, sentences=story_sentences(fx))
    problems += [f"tag f:{t} is the replaced association figure; use the causal review cost (c_cost_causal ...)"
                 for t in sorted(RETIRED_TAGS) if f"<!--f:{t}-->" in text]
    return n, (problems + check_shape(text) + check_number_words(text, fx, {**DESIGN, **d}) + check_scope(text)
               + check_repeat(text, sf) + check_questions(questions, fx))


def main():
    text = (ROOT / "story" / "story.qmd").read_text()
    n, problems = check(text)
    for p in problems:
        print(f"FAIL  {p}")
    print(f"{'PASS' if not problems else 'FAIL'}  story.qmd: {n} numbers tied to facts, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
