"""Check every number in README.md (the short summary) and docs/CASE_STUDY.md (the full case study) against the data.

Each CLAIM is a sentence fragment as the page prints it, rebuilt here from a query on the warehouse (source "warehouse"),
from the analysis report (source "report", numbers that the recommendation analysis produces and `make verify` already
reconciles) or from another repo file (source "repo"). A claim names the pages it must appear in ("f" full, "s" short).
The check fails when
  - a fragment is missing from a page it belongs to, or differs from what the data gives,
  - any number or number word left in a page's prose is not inside a checked fragment,
  - the ERD in docs/CASE_STUDY.md differs from case_study/erd.py, or the ERD fails its data checks,
  - docs/index.md is not the current output of case_study/build_pages.py.
Needs `make build` and `make recommendation` first. Selftest: case_study/selftest_check.py.
"""
import json
import re
import sys

from common import ROOT, connect, facts, row
import erd

README = ROOT / "README.md"                      # the short summary
FULL = ROOT / "docs" / "CASE_STUDY.md"           # the full case study; docs/index.md (Pages) is built from it
DEFINITION_PHRASES = ["one- and two-star", "one or two stars", "one- or two-star", "Test 1", "test 1"]   # the 1-2 star definition (review_score <= 2); a list label   # the 1-2 star definition: review_score <= 2


def pct(x, d=1):
    return f"{x:.{d}f}"


def build_claims(con):
    F = facts()
    one = lambda q: row(con, q)
    out = []   # (fragment, source, pages): pages is "f" (full case study), "s" (short README) or "fs" (both)

    def add(fragment, source, pages="f"):
        out.append((fragment, source, pages))

    # --- the data behind the sentences
    orders_raw = one("select count(*) from staging.stg_orders")[0]
    ids, people = one("select count(*), count(distinct customer_unique_id) from (select customer_id, customer_unique_id from staging.stg_customers)")
    multi = one("select count(*) from (select order_id from marts.fct_order_items group by 1 having count(distinct seller_id) > 1)")[0]
    survey_n, survey_before = one("select count(*), sum(review_before_delivery::int) from marts.fct_orders where delivery_state like 'delivered%' and review_id is not null")
    judged, late = one("select count(*), sum(is_late::int) from metrics.metric_late_rate_orders")
    s_late, s_ok = one("select avg(review_score) filter (where is_late), avg(review_score) filter (where not is_late) from metrics.metric_late_rate_orders")
    bad_late, bad_ok = one(
        "select 100.0*avg((review_score<=2)::int) filter (where is_late and review_score is not null), "
        "100.0*avg((review_score<=2)::int) filter (where not is_late and review_score is not null) from metrics.metric_late_rate_orders")
    total_bad = one("select count(*) from metrics.metric_late_rate_orders where review_score <= 2")[0]
    caused = one("select sum(extra_bad_reviews) from metrics.metric_review_cost_causal")[0]
    y0, y1 = one("select min(year(purchase_date)), max(year(purchase_date)) from marts.fct_orders")
    repeat90 = one("select value_pct from metrics.metric_repeat_rate_90d")[0]
    top_months = sorted(r[0] for r in con.sql("select year_month from metrics.metric_late_rate_monthly order by value_pct desc limit 3").fetchall())
    top_late, top_orders = one(
        "select sum(numerator), sum(denominator) from (select * from metrics.metric_late_rate_monthly order by value_pct desc limit 3)")
    all_late, all_orders = one("select sum(numerator), sum(denominator) from metrics.metric_late_rate_monthly")
    nne = one(
        "select 100.0*avg(is_late::int) from metrics.metric_late_rate_orders o join seeds.dash_region_map r on r.state = o.ship_to_state "
        "where r.region_group = 'North and northeast'")[0]
    hl_share, late_if_hl, late_if_ok, seller_side = one(
        "with b as (select l.is_late, o.delivered_to_carrier_at > o.last_shipping_limit_at as hl from metrics.metric_late_rate_orders l "
        "join marts.fct_orders o using (order_id) where o.delivered_to_carrier_at is not null) "
        "select 100.0*avg(hl::int), 100.0*avg(is_late::int) filter (where hl), 100.0*avg(is_late::int) filter (where not hl), "
        "100.0*sum(hl::int) filter (where is_late)/sum(is_late::int) from b")
    survey_before_late = one("select 100.0*avg(review_before_delivery::int) from metrics.metric_late_rate_orders where is_late and review_score is not null")[0]
    n_months = {f"{y}-{m:02d}": f"{name} {y}" for y in (2016, 2017, 2018) for m, name in enumerate(
        "January February March April May June July August September October November December".split(), 1)}
    mut = json.loads((ROOT / "evidence" / "mutation_report.json").read_text())
    proven = sum(r["verdict"] == "PROVEN" for r in mut)
    erd_res = erd.check_data()
    erd_ok = sum(ok for _, ok, _ in erd_res)
    rep = json.loads((ROOT / "evidence" / "recommendation_report.json").read_text())
    hold = rep["stars"]["holdout"]["matched"]["effect"]
    disc = rep["stars"]["discovery"]["matched"]["effect"]
    manifest_n = one(f"select count(*) from read_csv_auto('{ROOT / 'seeds' / 'raw_file_manifest.csv'}')")[0]
    rate = 100 * late / judged
    caused_r = round(caused)

    add(f"about {round(orders_raw, -3):,} real orders", "warehouse", "fs")
    add(f"about {caused_r:,} of the {total_bad:,} one- and two-star reviews on {judged:,} delivered orders, about {100 * caused / total_bad:.0f}%, with a range of {F['c_cost_range_lo']} to {F['c_cost_range_hi']}", "warehouse+report", "fs")
    add(f"because {pct(seller_side)}% of late orders were handed to the carrier late", "warehouse", "fs")
    add(f"nine tables from {y0} to {y1}" if manifest_n == 9 else "NINE_MISMATCH", "warehouse")
    add(f"{ids:,} IDs for {people:,} people", "warehouse")
    add(f"{multi:,} orders ship from several sellers", "warehouse")
    add(f"{pct(100 * survey_before / survey_n, 2)}% of the reviews on delivered orders are dated before delivery", "warehouse")
    add(f"{pct(rate, 2)}% of delivered orders ({late:,} of {judged:,}) arrived late. Late orders average {s_late:.2f} stars and on-time orders {s_ok:.2f}", "warehouse", "fs")
    add(f"{pct(bad_late)}% of late ones get", "warehouse")
    add(f"against {pct(bad_ok)}% of on-time ones", "warehouse")
    add(f"climb about {F['c_ramp_slope']} percentage points for each day late and level off near {F['c_ramp_plateau']}% from day {F['c_ramp_end_day']}", "report")
    add(f"The estimate is about {caused_r:,} of {total_bad:,} ({100 * caused / total_bad:.0f}%)", "warehouse")
    add(f"give {F['c_cost_range_lo']} to {F['c_cost_range_hi']}", "report", "fs")
    add(f"Roughly one bad review in four" if 0.23 <= caused / total_bad <= 0.30 else "QUARTER_MISMATCH", "warehouse")
    add(f"About a quarter of the bad reviews" if 0.23 <= caused / total_bad <= 0.30 else "QUARTER_MISMATCH", "warehouse")
    memo = (ROOT / "recommendation" / "MEMO.md").read_text()
    window = "90" if "90<!--d:repeat_window_days-->" in memo else "WINDOW_MISMATCH"
    add(f"{repeat90:.2f}% of customers order again within {window} days", "warehouse+repo")
    add(f"came back {abs(float(F['rep_matched'])):.2f} percentage points less often, with a range of {F['rep_matched_lo']} to {F['rep_matched_hi']} percentage points", "report", "fs")
    add(f"Three months ({n_months[top_months[0]]}, {n_months[top_months[1]]} and {n_months[top_months[2]]}) hold {pct(100 * top_late / all_late)}% of late orders and {pct(100 * top_orders / all_orders)}% of all orders", "warehouse")
    add(f"run {pct(nne)}% late", "warehouse")
    add(f"On {pct(hl_share)}% of orders the seller handed the parcel to the carrier after the ship-by date. Those orders were late {pct(late_if_hl)}% of the time, against {pct(late_if_ok)}% when the handoff was on time", "warehouse", "fs")
    ratio = late_if_hl / late_if_ok
    add("about four times as likely" if round(ratio) == 4 else "RATIO_MISMATCH", "warehouse")
    add(f"they make up {pct(seller_side)}% of late orders", "warehouse")
    add(f"About {F['avoidable_late']} fewer late orders ({F['avoidable_share']}% of them) would take the late rate from {pct(rate, 2)}% to {F['c_whatif_rate']}%" if abs(100 * (late - int(F['avoidable_late'].replace(',', ''))) / judged - float(F['c_whatif_rate'])) < 0.1 else "WHATIF_MISMATCH", "report+warehouse")
    add(f"{pct(survey_before_late)}% of late orders' surveys went out before delivery", "warehouse")
    add(f"about {F['c_cost_bias_hi']} of the reviews at the top of its range", "report")
    n_hold = int(F["holdout_last_month"][-2:]) - int(F["holdout_first_month"][-2:]) + 1
    words = {3: "three", 4: "four", 5: "five", 6: "six"}
    add(f"It was {abs(hold):.2f} stars in the last {words[n_hold]} months, against {abs(disc):.2f} earlier" if F["holdout_first_month"][:4] == F["holdout_last_month"][:4] else "HOLDOUT_MISMATCH", "report")
    add(f"Late delivery is estimated to account for about {caused_r:,} bad reviews", "warehouse")
    # the goal line, the warning line and the what-if rates, from the targets table and the memo's own figures
    t = one("select 100*alarm_line_late_rate, 100*goal_late_rate, 100*stretch_goal_late_rate, 100*late_rate_if_handoffs_ok, stable_months, laney_signal_months, typical_orders "
            "from metrics.metric_late_rate_targets")
    alarm, goal, stretch, whatif_pooled, stable, flagged_n, typical = t
    flagged = sorted(F[f"c_flagged_{i}"] for i in (1, 2, 3))
    assert flagged_n == 3 and len(flagged) == 3
    assert f"{goal:.1f}" == F["c_goal_line"] and f"{stretch:.1f}" == F["c_stretch_line"] and f"{whatif_pooled:.2f}" == F["c_whatif_rate"]
    assert f"{alarm:.2f}" == F["c_alarm_line"] and int(stable) == int(F["c_stable_months"]) and f"{typical:,.0f}" == F["c_typical_orders"]
    gap = f"{goal - stretch:.1f}"
    assert gap == F["c_whatif_gap"], (gap, F["c_whatif_gap"])
    spc = (ROOT / "late_rate_targets" / "spc.py").read_text()
    memo = (ROOT / "recommendation" / "MEMO.md").read_text()
    add(f"The {goal:.1f}% goal and the {alarm:.1f}% warning line", "warehouse")
    add(f"It sits at {alarm:.1f}% for a typical month of {typical:,.0f} orders", "warehouse")
    add(f"the average late rate of the stable months plus three standard deviations" if "centre + 3 * sigma_z * sig" in spc else "SPC_MISMATCH", "repo")
    add(f"Three months crossed it: {n_months[flagged[0]]}, {n_months[flagged[1]]} and {n_months[flagged[2]]}", "warehouse")
    add(f"The goal, {goal:.1f}%, is the median late rate of the {int(stable)} stable months", "warehouse", "fs")
    add(f"and the warning line, {alarm:.1f}%,", "warehouse", "s")
    add("so half of them already beat it" if "so half of them already beat it" in memo else "HALF_MISMATCH", "repo")
    add("it includes the three spike months" if flagged_n == 3 else "SPIKE_MISMATCH", "warehouse")
    add("Three months crossed the line", "warehouse", "s")
    add(f"The {whatif_pooled:.2f}% is the pooled version: it takes all {judged:,} orders and moves the late rate from {rate:.2f}% to {whatif_pooled:.2f}%", "warehouse")
    add(f"The {stretch:.1f}% is the dashboard's version for a typical stable month: it moves the median stable month from the {goal:.1f}% goal down to {stretch:.1f}%, a drop of about {gap} percentage point", "warehouse")
    add(f"Why the dashboard says {stretch:.1f}% and this page says {whatif_pooled:.2f}%", "warehouse")
    add(f"The what-if rate of {stretch:.1f}% on the dashboard moves a typical stable month down from the goal by about {gap} percentage point", "warehouse", "s")
    add(f"The {whatif_pooled:.2f}% on the full page is the same what-if on all {judged:,} orders pooled, from {rate:.2f}%", "warehouse", "s")
    add(f"The estimated effect is about {caused_r:,} of {total_bad:,} ({100 * caused / total_bad:.0f}%)", "warehouse", "s")
    readme = FULL.read_text()
    after = readme.split("Three problems in the tables would have skewed the results.\n", 1)[1].split("\n\n", 1)[0]
    add("Three problems in the tables" if len([l for l in after.splitlines() if l.startswith("- ")]) == 3 else "THREE_MISMATCH", "repo")
    add("the nine source tables" if manifest_n == 9 else "NINE_MISMATCH", "repo")
    add(f"The keys and links in the diagram above pass {erd_ok} of {len(erd_res)} checks", "warehouse")
    add(f"All {proven} rules in the check suite", "repo" if proven == len(mut) else "MUTATION_MISMATCH")
    add("and six reasonable ways of comparing" if "six specifications" in (ROOT / "review_cost_causal" / "README.md").read_text() else "SIX_MISMATCH", "repo", "fs")
    add("two randomized tests" if "## What to do: two tests" in memo else "TWO_MISMATCH", "repo", "fs")
    add("Run two randomized tests" if "## What to do: two tests" in memo else "TWO_MISMATCH", "repo", "fs")
    add("over 8 weeks" if "8<!--d:test_weeks--> weeks" in memo else "WEEKS_MISMATCH", "repo")
    add("8 weeks of orders" if "8<!--d:test_weeks--> weeks" in memo else "WEEKS_MISMATCH", "repo")
    add("Half of the sellers, picked at random" if "Pick half of sellers at random" in memo else "HALF_MISMATCH", "repo", "fs")
    add("The other half see no change" if "The other half see no change" in memo else "HALF_MISMATCH", "repo", "fs")
    add("on a random half of orders" if "on a random half of orders" in memo else "HALF_MISMATCH", "repo", "fs")
    return out


NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?|\b(?:three|four|five|six|seven|eight|nine|ten|half|quarter|two)\b", re.I)


def prose(text):
    """Page text without code blocks, link targets, image files and list numbers."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"\]\([^)]*\)", "]", text)
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"(?m)^\s*\d+\.\s", "", text)
    return text


def problems(page_text, claims, which, erd_text=None):
    """Problems on one page. which is "f" (docs/CASE_STUDY.md) or "s" (README.md). The ERD is checked on the full page only."""
    out = []
    text = original = prose(page_text)
    for frag, src, pages in claims:
        if which in pages and frag not in original:
            out.append(f"claim fragment not in page (or the data disagrees): {frag!r} [{src}]")
        text = text.replace(frag, " ") if which in pages else text
    for ph in DEFINITION_PHRASES:
        text = text.replace(ph, " ")
    for m in NUMBER.finditer(text):
        s = max(0, m.start() - 30)
        out.append(f"unchecked number {m.group(0)!r} near: {text[s:m.end() + 20]!r}")
    if erd_text is not None:
        block = re.search(r"```mermaid\n(.*?)\n```", page_text, re.S)
        if not block or block.group(1) != erd_text:
            out.append("the page's erDiagram differs from case_study/erd.py")
    return out


def pages_problems(index_text, pages_text):
    return [] if index_text == pages_text else ["docs/index.md is stale: run python case_study/build_pages.py"]


def main():
    con = connect()
    claims = build_claims(con)
    index = ROOT / "docs" / "index.md"
    import build_pages
    current = index.read_text() if index.exists() else ""
    full_text = FULL.read_text()
    found = [f"[README.md] {p}" for p in problems(README.read_text(), claims, "s")]
    found += [f"[docs/CASE_STUDY.md] {p}" for p in problems(full_text, claims, "f", erd.mermaid())]
    found += pages_problems(current, build_pages.render(full_text, build_pages.embedded_url(current)))
    for p in found:
        print("FAIL ", p)
    erd_bad = [d for d, ok, _ in erd.check_data() if not ok]
    for d in erd_bad:
        print("FAIL  ERD:", d)
    n = len(claims)
    print(f"{'FAIL' if found or erd_bad else 'PASS'}  case study: {n} fragments checked against the data on README.md and docs/CASE_STUDY.md, {len(found)} problems, {len(erd_bad)} ERD check failures")
    sys.exit(1 if found or erd_bad else 0)


if __name__ == "__main__":
    main()
