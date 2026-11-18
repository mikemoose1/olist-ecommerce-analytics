"""Part C of the headline reconciliation: the story's chart numbers, recomputed from the raw CSVs.

from_story(data_dir)  reads the counts behind every chart from story/data (what build_story.py draws)
from_raw(raw_dir)     recomputes the same counts straight from the raw CSVs, with no dbt code and no story code
compare(story, raw)   one (name, ok, message) per number; ok only when numerator and denominator are equal,
                      and the stored rate equals numerator / denominator
"""
import csv, json, os

NOT_ARRIVED = r"nao (recebi|chegou|foi entregue|entreg|veio)|ainda nao|atras|demor|prazo|aguard|esperand|nada do produto|retornou"
NNE = ("AC", "AL", "AM", "AP", "BA", "CE", "MA", "PA", "PB", "PE", "PI", "RN", "RO", "RR", "SE", "TO")


def from_story(data_dir):
    out = {}
    for table in ("late_by_month", "late_by_state", "late_by_region", "late_by_handoff"):
        for r in csv.DictReader(open(os.path.join(data_dir, f"{table}.csv"))):
            out[f"{table}:{r['segment']}"] = {"num": int(r["late"]), "den": int(r["orders"]), "rate": float(r["late_rate"])}
    f = json.load(open(os.path.join(data_dir, "facts.json")))
    out["late_orders"] = {"num": f["late_orders"], "den": f["judged_orders"], "rate": f["late_rate"]}
    out["comment_delay_share"] = {"num": round(f["comment_delay_share"] * f["comments_n"]), "den": f["comments_n"], "rate": f["comment_delay_share"]}
    out["late_sales_window"] = {"num": round(f["late_sales_window"], 2), "den": None}
    return out


def from_raw(raw_dir):
    import duckdb
    raw = duckdb.connect()
    for name, f in {"orders": "olist_orders_dataset", "items": "olist_order_items_dataset", "reviews": "olist_order_reviews_dataset",
                    "customers": "olist_customers_dataset", "payments": "olist_order_payments_dataset"}.items():
        raw.execute(f"create view {name} as select * from read_csv_auto('{raw_dir}/{f}.csv', header=true)")
    raw.execute(f"""
    create table ia as select order_id, count(distinct seller_id) n_sellers, max(shipping_limit_date) ship_by from items group by 1;
    create table rev1 as select * from (select *, row_number() over (partition by order_id order by review_answer_timestamp desc, review_id) rn
                                        from reviews) where rn = 1;
    create table pay as select order_id, sum(payment_value) paid from payments group by 1;
    create table pop as
     select o.order_id, c.customer_state state, strftime(o.order_purchase_timestamp, '%Y-%m') ym,
            (o.order_delivered_customer_date::date > o.order_estimated_delivery_date::date) late,
            o.order_delivered_carrier_date carrier_at, ia.ship_by, r.review_comment_message msg, pay.paid
     from orders o join ia using(order_id) join customers c using(customer_id) left join rev1 r using(order_id) left join pay using(order_id)
     where o.order_status = 'delivered' and o.order_delivered_customer_date is not null and ia.n_sellers = 1
       and o.order_purchase_timestamp >= '2017-01-01' and o.order_purchase_timestamp < '2018-09-01';""")
    out = {}
    def groups(prefix, key, where="true"):
        for k, n, l in raw.execute(f"select {key}, count(*), sum(late::int) from pop where {where} group by 1").fetchall():
            out[f"{prefix}:{k}"] = {"num": int(l), "den": int(n)}
    groups("late_by_month", "ym")
    groups("late_by_state", "state")
    groups("late_by_region", f"case when state in {NNE} then 'North and northeast' else 'Rest of Brazil' end")
    groups("late_by_handoff", "case when carrier_at > ship_by then 'Handed over after ship-by' else 'Handed over on time' end", "carrier_at is not null")
    n, l = raw.execute("select count(*), sum(late::int) from pop").fetchone()
    out["late_orders"] = {"num": int(l), "den": int(n)}
    n, k = raw.execute(f"""select count(*), sum(regexp_matches(strip_accents(lower(msg)), '{NOT_ARRIVED}')::int)
                           from pop where late and msg is not null""").fetchone()
    out["comment_delay_share"] = {"num": int(k), "den": int(n)}
    out["late_sales_window"] = {"num": round(float(raw.execute("select sum(paid) from pop where late").fetchone()[0]), 2), "den": None}
    return out


def compare(story, raw):
    res = []
    for name in sorted(set(story) | set(raw)):
        s, r = story.get(name), raw.get(name)
        if s is None or r is None:
            res.append((name, False, f"only in {'raw' if s is None else 'story'}"))
            continue
        ok = s["num"] == r["num"] and s["den"] == r["den"]
        if "rate" in s and s["den"]:
            ok &= abs(s["rate"] - s["num"] / s["den"]) < 5e-7
        res.append((name, ok, f"story {s['num']}/{s['den']} raw {r['num']}/{r['den']}"))
    return res
