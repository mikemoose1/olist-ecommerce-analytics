"""Rebuild the dashboard's order, seller, handoff, region and month counts straight from data/raw/*.csv, without dbt or any model.

verify_dash_exports.py compares these with the CSV files Tableau reads. The population and the two definitions are written out again
here from their plain-language rules, so a mistake in a dbt model cannot also be a mistake in the check:
  judged order   status delivered, a delivered-to-customer date, at least one item, ONE seller on the order, bought 2017-01-01 to 2018-08-31
  late           the delivered-to-customer calendar day is after the estimated delivery day
  late handoff   the carrier pickup time is after the seller's ship-by time (the earliest shipping_limit_date on the order);
                 an order with no pickup time is in neither handoff group
  region         the customer's state, grouped as the story groups it (story/story_data.py NNE)
Set OLIST_RAW_DIR to point at another copy of the raw files. Needs duckdb.
"""
import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW = Path(os.environ.get("OLIST_RAW_DIR", ROOT / "data" / "raw"))


def rebuild(nne_states, raw=RAW):
    raw = Path(raw)
    con = duckdb.connect(":memory:")
    q = lambda f: f"read_csv('{raw / f}', header = true, all_varchar = true)"
    con.execute(f"""
        create temp view judged as
        with one_seller as (
            select order_id, min(seller_id) as seller_id, min(shipping_limit_date) as ship_by
            from {q('olist_order_items_dataset.csv')} group by 1 having count(distinct seller_id) = 1
        )
        select o.order_id, i.seller_id, c.customer_state as state,
               strftime(cast(o.order_purchase_timestamp as timestamp), '%Y-%m') as year_month,
               cast(o.order_delivered_customer_date as date) > cast(o.order_estimated_delivery_date as date) as is_late,
               cast(o.order_delivered_carrier_date as timestamp) > cast(i.ship_by as timestamp) as handed_late
        from {q('olist_orders_dataset.csv')} o
        join one_seller i using (order_id)
        join {q('olist_customers_dataset.csv')} c on c.customer_id = o.customer_id
        where o.order_status = 'delivered' and o.order_delivered_customer_date is not null
          and cast(o.order_purchase_timestamp as date) between date '2017-01-01' and date '2018-08-31'
    """)
    one = lambda sql: con.execute(sql).fetchone()[0]
    out = {
        "judged_orders": one("select count(*) from judged"),
        "late_orders": one("select count(*) from judged where is_late"),
        "late_after_late_handoff": one("select count(*) from judged where is_late and handed_late"),
        "late_handoff_orders": one("select count(*) from judged where handed_late"),
        "no_handoff_time_orders": one("select count(*) from judged where handed_late is null"),
        "months": {r[0]: (r[1], r[2]) for r in con.execute(
            "select year_month, count(*), count(*) filter (where is_late) from judged group by 1").fetchall()},
        "handoff": {r[0]: (r[1], r[2]) for r in con.execute(
            "select handed_late, count(*), count(*) filter (where is_late) from judged where handed_late is not null group by 1").fetchall()},
    }
    nne = ", ".join("'" + s + "'" for s in sorted(nne_states))
    out["region"] = {r[0]: (r[1], r[2]) for r in con.execute(
        f"select case when state in ({nne}) then 'North and northeast' else 'Rest of Brazil' end, count(*), count(*) filter (where is_late) from judged group by 1").fetchall()}
    rows = con.execute("""
        select seller_id, count(*), count(*) filter (where handed_late), count(*) filter (where handed_late and is_late), count(*) filter (where is_late)
        from judged group by 1
        order by 4 desc, 5 desc, 1
    """).fetchall()
    total = out["late_after_late_handoff"]
    out["sellers"] = [
        {"seller_id": s, "seller_code": s[:8], "orders": n, "late_handoff_orders": lh, "late_after_late_handoff_orders": lal, "late_orders": late,
         "late_handoff_rate": lh / n, "late_rate": late / n, "rank": i, "is_top10": i <= 10, "share": lal / total}
        for i, (s, n, lh, lal, late) in enumerate(rows, start=1)]
    out["sellers_with_late_after_late_handoff"] = sum(1 for r in out["sellers"] if r["late_after_late_handoff_orders"] > 0)
    out["top10_late_after_late_handoff"] = sum(r["late_after_late_handoff_orders"] for r in out["sellers"][:10])
    return out


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT / "story"))
    from story_data import NNE
    r = rebuild(NNE)
    print({k: v for k, v in r.items() if k not in ("sellers", "months")})
    print(r["sellers"][0])
