"""Build every number the story's charts and captions use, from the warehouse and the recommendation report.

  python story/story_data.py           write story/data/*.csv and story/data/facts.json
  python story/story_data.py --check   fail if the committed files differ from a fresh build

Rates carry 95% Wilson intervals. Matched estimates carry the intervals analyze.py reports.
verification/verify_headlines.py Part C recomputes the chart numbers from the raw CSVs.
"""
import csv, io, json, math, sys
from pathlib import Path

import duckdb, yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kpi_tree as K

ROOT = K.ROOT
OUT = ROOT / "story" / "data"
NNE = ("AC", "AL", "AM", "AP", "BA", "CE", "MA", "PA", "PB", "PE", "PI", "RN", "RO", "RR", "SE", "TO")
LAST12_FROM = "2017-09-01"   # the last 12 months of the window: 2017-09 to 2018-08


def wilson(k, n, z=1.959964):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def rate_rows(con, key_sql, where="true"):
    rows = con.execute(f"""select {key_sql} k, count(*) n, sum(is_late::int) l from judged where {where}
                           group by 1 order by 1""").fetchall()
    total_late = con.execute("select sum(is_late::int) from judged").fetchone()[0]
    out = []
    for k, n, l in rows:
        lo, hi = wilson(l, n)
        out.append({"segment": str(k), "orders": n, "late": int(l), "late_rate": round(l / n, 6),
                    "ci_low": round(lo, 6), "ci_high": round(hi, 6), "share_of_late": round(l / total_late, 6)})
    return out


def build():
    tree = yaml.safe_load(K.TREE.read_text())
    rep = json.loads((ROOT / "evidence" / "recommendation_report.json").read_text())
    con = duckdb.connect(str(ROOT / "olist.duckdb"), read_only=True)
    con.execute(f"create temp view judged as {tree['judged_sql']}")
    one = lambda q: con.execute(q).fetchone()
    n, late = one("select count(*), sum(is_late::int) from judged")
    lo, hi = wilson(late, n)
    tables = {
        "late_by_month": rate_rows(con, "strftime(purchase_date, '%Y-%m')"),
        "late_by_state": sorted(rate_rows(con, "ship_to_state"), key=lambda r: -r["late"]),
        "late_by_region": rate_rows(con, f"case when ship_to_state in {NNE} then 'North and northeast' else 'Rest of Brazil' end"),
        "late_by_handoff": rate_rows(con, "case when delivered_to_carrier_at > last_shipping_limit_at then 'Handed over after ship-by' else 'Handed over on time' end",
                                     "delivered_to_carrier_at is not null"),
    }
    ls = rep["money"]["low_star_reviews"]
    com_n, com_k = one(f"""select count(*), sum(regexp_matches(strip_accents(lower(review_comment_message)), '{K.NOT_ARRIVED}')::int)
                           from judged j join marts.fct_reviews r on r.order_id = j.order_id and r.is_chosen_for_order
                           where j.is_late and r.review_comment_message is not null""")
    sv_n, sv_k = one("select count(*), sum(review_before_delivery::int) from judged where is_late and review_score is not null")
    handoff = {r["segment"]: r for r in tables["late_by_handoff"]}
    hl, ho = handoff["Handed over after ship-by"], handoff["Handed over on time"]
    m = rep["repeat90"]["all"]["matched"]
    facts = {
        "judged_orders": n, "late_orders": int(late), "late_rate": round(late / n, 6), "late_rate_ci": [round(lo, 6), round(hi, 6)],
        "low_star_excess": round(ls["excess_from_lateness"]["mid"], 1),
        "low_star_excess_ci": [round(ls["excess_from_lateness"]["low"], 1), round(ls["excess_from_lateness"]["high"], 1)],
        "low_star_all": ls["all_low_star"],
        "low_star_excess_share": round(ls["share_of_all_low_star_pct"]["mid"] / 100, 6),
        "low_star_excess_share_ci": [round(ls["share_of_all_low_star_pct"]["low"] / 100, 6), round(ls["share_of_all_low_star_pct"]["high"] / 100, 6)],
        "star_penalty": rep["stars"]["all"]["matched"]["effect"], "star_penalty_ci": rep["stars"]["all"]["matched"]["ci"],
        "late_sales_window": round(float(one("select sum(amount_paid) from judged where is_late")[0]), 2),
        "late_sales_last12": round(float(one(f"select sum(amount_paid) from judged where is_late and purchase_date >= date '{LAST12_FROM}'")[0]), 2),
        "total_sales_last12": round(float(one(f"select sum(amount_paid) from judged where purchase_date >= date '{LAST12_FROM}'")[0]), 2),
        "handoff_late_share_of_late": round(hl["late"] / late, 6),
        "handoff_late_rate": hl["late_rate"], "handoff_late_rate_ci": [hl["ci_low"], hl["ci_high"]],
        "handoff_ok_rate": ho["late_rate"], "handoff_ok_rate_ci": [ho["ci_low"], ho["ci_high"]],
        "avoidable_late_upper": round(rep["who_caused"]["avoidable_upper_bound"]["late_orders"], 1),
        "comment_delay_share": round(com_k / com_n, 6), "comment_delay_share_ci": [round(x, 6) for x in wilson(com_k, com_n)], "comments_n": com_n,
        "survey_before_share": round(sv_k / sv_n, 6), "survey_before_share_ci": [round(x, 6) for x in wilson(sv_k, sv_n)],
        "repeat_raw_pts": round(rep["repeat90"]["all"]["raw"]["effect"] * 100, 4),
        "repeat_raw_pts_ci": [round(x * 100, 4) for x in rep["repeat90"]["all"]["raw"]["ci"]],
        "repeat_effect_pts": round(m["effect"] * 100, 4), "repeat_effect_pts_ci": [round(x * 100, 4) for x in m["ci"]],
        "late_first_last12": rep["money"]["late_first_orders_last12"],
        "lost_repeat_last12": [round(rep["money"]["lost_repeat_gmv_last12"][k], 1) for k in ("low", "mid", "high")],
        "label_eval": K.label_eval(),
    }
    top3 = sorted(tables["late_by_month"], key=lambda r: -r["late"])[:3]
    facts["top3_months"] = [r["segment"] for r in top3]
    facts["top3_months_share_of_late"] = round(sum(r["late"] for r in top3) / late, 6)
    facts["captions"] = captions(facts, tables)
    return tables, facts


def captions(f, t):
    """Numbers as the story prints them. story/check_story.py ties each printed number to one of these names
    (or to a recommendation/analyze.py memo fact)."""
    pct = lambda x: f"{100 * x:.1f}"
    seg = lambda table, k: next(r for r in t[table] if r["segment"] == k)
    nne, rest = seg("late_by_region", "North and northeast"), seg("late_by_region", "Rest of Brazil")
    mar, nov = seg("late_by_month", "2018-03"), seg("late_by_month", "2017-11")
    lab = f["label_eval"]
    bars = yaml.safe_load(K.TREE.read_text())["thresholds"]
    return {
        "c_late_rate_lo": f"{100 * f['late_rate_ci'][0]:.2f}", "c_late_rate_hi": f"{100 * f['late_rate_ci'][1]:.2f}",
        "c_low_star_all": f"{f['low_star_all']:,}",
        "c_late_sales_window": f"R${f['late_sales_window'] / 1e6:.2f} million",
        "c_nne_lo": pct(nne["ci_low"]), "c_nne_hi": pct(nne["ci_high"]), "c_rest_rate": pct(rest["late_rate"]),
        "c_mar_lo": pct(mar["ci_low"]), "c_mar_hi": pct(mar["ci_high"]),
        "c_nov_lo": pct(nov["ci_low"]), "c_nov_hi": pct(nov["ci_high"]),
        "c_handoff_late_n": f"{seg('late_by_handoff', 'Handed over after ship-by')['late']:,}",
        "c_handoff_late_lo": pct(f["handoff_late_rate_ci"][0]), "c_handoff_late_hi": pct(f["handoff_late_rate_ci"][1]),
        "c_handoff_orders": f"{seg('late_by_handoff', 'Handed over after ship-by')['orders']:,}",
        "c_segment_thr": f"{bars['segment_ratio'] * 100 * f['late_rate']:.1f}",
        "c_last12_n": "12",
        "c_late_sales_last12_m": f"R${f['late_sales_last12'] / 1e6:.2f} million",
        "c_total_sales_last12_m": f"R${f['total_sales_last12'] / 1e6:.1f} million",
        "c_late_sales_last12_share": pct(f["late_sales_last12"] / f["total_sales_last12"]),
        "c_avoidable_exact": f"{f['avoidable_late_upper']:,.0f}",
        "c_money_high_exact": f"R${f['lost_repeat_last12'][2]:,.0f}",
        "c_rep_raw": f"{f['repeat_raw_pts']:.2f}", "c_rep_raw_lo": f"{f['repeat_raw_pts_ci'][0]:.2f}",
        "c_rule_negatives_n": str(sum(e["fp"] + e["tn"] for e in lab.values())),
        "c_low_star_excess_exact": f"{f['low_star_excess']:,.0f}",
        "c_handoff_ratio": f"{f['handoff_late_rate'] / f['handoff_ok_rate']:.1f}",
        "c_comment_pct": pct(f["comment_delay_share"]),
        "c_comment_lo": pct(f["comment_delay_share_ci"][0]), "c_comment_hi": pct(f["comment_delay_share_ci"][1]),
        "c_comments_n": f"{f['comments_n']:,}",
        "c_rule_labelled_n": str(sum(e["n"] for e in lab.values())), "c_rule_holdout_n": str(lab["holdout"]["n"]),
        "c_rule_false_matches": str(sum(e["fp"] for e in lab.values())),
        "c_rule_holdout_missed": f"{100 * (1 - lab['holdout']['recall']):.0f}",
        "c_survey_lo": pct(f["survey_before_share_ci"][0]), "c_survey_hi": pct(f["survey_before_share_ci"][1]),
    }


def render(tables, facts):
    files = {}
    for name, rows in tables.items():
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(rows)
        files[f"{name}.csv"] = buf.getvalue()
    files["facts.json"] = json.dumps(facts, indent=1) + "\n"
    return files


def main():
    files = render(*build())
    if "--check" in sys.argv:
        stale = [f for f, t in files.items() if not (OUT / f).exists() or (OUT / f).read_text() != t]
        print(f"{'PASS' if not stale else 'FAIL'}  committed story/data matches the warehouse" + (f" (stale: {stale})" if stale else ""))
        sys.exit(1 if stale else 0)
    OUT.mkdir(exist_ok=True)
    for f, t in files.items():
        (OUT / f).write_text(t)
    print(f"wrote {len(files)} files to story/data")


if __name__ == "__main__":
    main()
