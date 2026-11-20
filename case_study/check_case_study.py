"""Check every number in README.md against the data.

Each CLAIM is a sentence fragment as README.md prints it, rebuilt here from a query on the warehouse (source "warehouse"),
from the analysis report (source "report", numbers that the recommendation analysis produces and `make verify` already
reconciles) or from another repo file (source "repo"). The check fails when
  - a fragment is missing from README.md or differs from what the data gives,
  - any number or number word left in the README prose is not inside a checked fragment,
  - the ERD in README.md differs from case_study/erd.py, or the ERD fails its data checks,
  - docs/index.md is not the current output of case_study/build_pages.py.
Needs `make build` and `make recommendation` first. Selftest: case_study/selftest_check.py.
"""
import json
import re
import sys

from common import ROOT, connect, facts, row
import erd

README = ROOT / "README.md"
DEFINITION_PHRASES = ["one- and two-star", "one or two stars", "one- or two-star", "Test 1", "test 1"]   # the 1-2 star definition (review_score <= 2); a list label   # the 1-2 star definition: review_score <= 2


def pct(x, d=1):
    return f"{x:.{d}f}"


def build_claims(con):
    F = facts()
    one = lambda q: row(con, q)
    out = []   # (fragment, source)

    def add(fragment, source):
        out.append((fragment, source))

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

    add(f"about {round(orders_raw, -3):,} real orders", "warehouse")
    add(f"about {caused_r:,} of the {total_bad:,} one- and two-star reviews on {judged:,} delivered orders, about {100 * caused / total_bad:.0f}%, with a range of {F['c_cost_range_lo']} to {F['c_cost_range_hi']}", "warehouse+report")
    add(f"because {pct(seller_side)}% of late orders were handed to the carrier late", "warehouse")
    add(f"nine tables from {y0} to {y1}" if manifest_n == 9 else "NINE_MISMATCH", "warehouse")
    add(f"{ids:,} IDs for {people:,} people", "warehouse")
    add(f"{multi:,} orders ship from several sellers", "warehouse")
    add(f"{pct(100 * survey_before / survey_n, 2)}% of the reviews on delivered orders are dated before delivery", "warehouse")
    add(f"{pct(rate, 2)}% of delivered orders ({late:,} of {judged:,}) arrived late. Late orders average {s_late:.2f} stars and on-time orders {s_ok:.2f}", "warehouse")
    add(f"{pct(bad_late)}% of late ones get", "warehouse")
    add(f"against {pct(bad_ok)}% of on-time ones", "warehouse")
    add(f"climb about {F['c_ramp_slope']} points for each day late and level off near {F['c_ramp_plateau']}% from day {F['c_ramp_end_day']}", "report")
    add(f"The estimate is about {caused_r:,} of {total_bad:,} ({100 * caused / total_bad:.0f}%)", "warehouse")
    add(f"give {F['c_cost_range_lo']} to {F['c_cost_range_hi']}", "report")
    add(f"Roughly one bad review in four" if 0.23 <= caused / total_bad <= 0.30 else "QUARTER_MISMATCH", "warehouse")
    add(f"About a quarter of the bad reviews" if 0.23 <= caused / total_bad <= 0.30 else "QUARTER_MISMATCH", "warehouse")
    memo = (ROOT / "recommendation" / "MEMO.md").read_text()
    window = "90" if "90<!--d:repeat_window_days-->" in memo else "WINDOW_MISMATCH"
    add(f"{repeat90:.2f}% of customers order again within {window} days", "warehouse+repo")
    add(f"came back {abs(float(F['rep_matched'])):.2f} points less often, with a range of {F['rep_matched_lo']} to {F['rep_matched_hi']} points", "report")
    add(f"Three months ({n_months[top_months[0]]}, {n_months[top_months[1]]} and {n_months[top_months[2]]}) hold {pct(100 * top_late / all_late)}% of late orders and {pct(100 * top_orders / all_orders)}% of all orders", "warehouse")
    add(f"run {pct(nne)}% late", "warehouse")
    add(f"On {pct(hl_share)}% of orders the seller handed the parcel to the carrier after the ship-by date. Those orders were late {pct(late_if_hl)}% of the time, against {pct(late_if_ok)}% when the handoff was on time", "warehouse")
    ratio = late_if_hl / late_if_ok
    add("about four times as likely" if round(ratio) == 4 else "RATIO_MISMATCH", "warehouse")
    add(f"they make up {pct(seller_side)}% of late orders", "warehouse")
    add(f"About {F['avoidable_late']} fewer late orders ({F['avoidable_share']}% of them) would take the late rate from {pct(rate, 2)}% to {F['c_whatif_rate']}%" if abs(100 * (late - int(F['avoidable_late'].replace(',', ''))) / judged - float(F['c_whatif_rate'])) < 0.1 else "WHATIF_MISMATCH", "report+warehouse")
    add(f"{pct(survey_before_late)}% of late orders' surveys went out before delivery", "warehouse")
    add(f"about {F['c_cost_bias_hi']} of the reviews at the top of its range", "report")
    n_hold = int(F["holdout_last_month"][-2:]) - int(F["holdout_first_month"][-2:]) + 1
    words = {3: "three", 4: "four", 5: "five", 6: "six"}
    add(f"It was {abs(hold):.2f} stars in the last {words[n_hold]} months, against {abs(disc):.2f} earlier" if F["holdout_first_month"][:4] == F["holdout_last_month"][:4] else "HOLDOUT_MISMATCH", "report")
    add(f"Late delivery caused about {caused_r:,} bad reviews", "warehouse")
    readme = README.read_text()
    after = readme.split("Three problems in the tables would have skewed the results.\n", 1)[1].split("\n\n", 1)[0]
    add("Three problems in the tables" if len([l for l in after.splitlines() if l.startswith("- ")]) == 3 else "THREE_MISMATCH", "repo")
    add("the nine source tables" if manifest_n == 9 else "NINE_MISMATCH", "repo")
    add(f"The keys and links in the diagram above pass {erd_ok} of {len(erd_res)} checks", "warehouse")
    add(f"All {proven} rules in the check suite", "repo" if proven == len(mut) else "MUTATION_MISMATCH")
    add("and six reasonable ways of comparing" if "six specifications" in (ROOT / "review_cost_causal" / "README.md").read_text() else "SIX_MISMATCH", "repo")
    add("two randomized tests" if "## What to do: two tests" in memo else "TWO_MISMATCH", "repo")
    add("Run two randomized tests" if "## What to do: two tests" in memo else "TWO_MISMATCH", "repo")
    add("over 8 weeks" if "8<!--d:test_weeks--> weeks" in memo else "WEEKS_MISMATCH", "repo")
    add("8 weeks of orders" if "8<!--d:test_weeks--> weeks" in memo else "WEEKS_MISMATCH", "repo")
    add("Half of the sellers, picked at random" if "Pick half of sellers at random" in memo else "HALF_MISMATCH", "repo")
    add("The other half see no change" if "The other half see no change" in memo else "HALF_MISMATCH", "repo")
    add("on a random half of orders" if "on a random half of orders" in memo else "HALF_MISMATCH", "repo")
    return out


NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?%?|\b(?:three|four|five|six|seven|eight|nine|ten|half|quarter|two)\b", re.I)


def prose(text):
    """README text without code blocks, link targets, image files and list numbers."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"\]\([^)]*\)", "]", text)
    text = re.sub(r"`[^`]*`", "", text)
    text = re.sub(r"(?m)^\s*\d+\.\s", "", text)
    return text


def problems(readme_text, claims, erd_text, index_text=None, pages_text=None):
    out = []
    text = original = prose(readme_text)
    for frag, src in claims:
        if frag not in original:
            out.append(f"claim fragment not in README (or the data disagrees): {frag!r} [{src}]")
        text = text.replace(frag, " ")
    for ph in DEFINITION_PHRASES:
        text = text.replace(ph, " ")
    for m in NUMBER.finditer(text):
        s = max(0, m.start() - 30)
        out.append(f"unchecked number {m.group(0)!r} near: {text[s:m.end() + 20]!r}")
    block = re.search(r"```mermaid\n(.*?)\n```", readme_text, re.S)
    if not block or block.group(1) != erd_text:
        out.append("README's erDiagram differs from case_study/erd.py")
    if pages_text is not None and index_text != pages_text:
        out.append("docs/index.md is stale: run python case_study/build_pages.py")
    return out


def main():
    con = connect()
    claims = build_claims(con)
    readme_text = README.read_text()
    index = ROOT / "docs" / "index.md"
    import build_pages
    current = index.read_text() if index.exists() else ""
    pages_text = build_pages.render(readme_text, build_pages.embedded_url(current))
    found = problems(readme_text, claims, erd.mermaid(), index.read_text() if index.exists() else "", pages_text)
    for p in found:
        print("FAIL ", p)
    erd_bad = [d for d, ok, _ in erd.check_data() if not ok]
    for d in erd_bad:
        print("FAIL  ERD:", d)
    n = len(claims)
    print(f"{'FAIL' if found or erd_bad else 'PASS'}  case study: {n} fragments checked against the data, {len(found)} problems, {len(erd_bad)} ERD check failures")
    sys.exit(1 if found or erd_bad else 0)


if __name__ == "__main__":
    main()
