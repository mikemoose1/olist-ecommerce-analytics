"""Repeat-late sellers, flagged as of each month (no hindsight).

At the 1st of each month, a seller is flagged if, among its orders already delivered by then, it had
orders that were both handed to the carrier after the ship-by date and delivered late in at least
3 different purchase months. The flag is then compared with what those sellers did in the month.
Scored on the holdout months (Mar - Aug 2018) on judged orders.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "promise_backtest"))
sys.path.insert(0, str(HERE))
from evaluate import bin_of, load_v2  # noqa: E402
from model import HOLDOUT_MONTHS  # noqa: E402

MIN_MONTHS = 3


def load(con) -> pd.DataFrame:
    return con.execute(
        """
        WITH s AS (SELECT order_id, min(seller_id) AS seller_id FROM marts.fct_order_items GROUP BY 1)
        SELECT f.order_id, s.seller_id, f.purchase_date, f.delivered_to_customer_at AS delivered_at,
               f.estimated_delivery_date, CAST(f.delivered_to_customer_at AS DATE) AS delivered_date,
               f.review_score, l.is_late,
               coalesce(f.delivered_to_carrier_at > f.last_shipping_limit_at, false) AS handoff_late
        FROM metrics.metric_late_rate_orders l
        JOIN marts.fct_orders f USING (order_id)
        JOIN s USING (order_id)
        ORDER BY f.order_id
        """
    ).fetchdf()


def flags_at(df: pd.DataFrame, cutoff: pd.Timestamp) -> set[str]:
    known = df[(df["delivered_at"] < cutoff) & df["is_late"] & df["handoff_late"]]
    months = known.groupby("seller_id")["purchase_date"].apply(lambda s: s.dt.strftime("%Y-%m").nunique())
    return set(months[months >= MIN_MONTHS].index)


def run(con) -> dict:
    df = load(con)
    df["purchase_date"] = pd.to_datetime(df["purchase_date"])
    df["delivered_at"] = pd.to_datetime(df["delivered_at"])
    df["delivered_date"] = pd.to_datetime(df["delivered_date"])
    df["estimated_delivery_date"] = pd.to_datetime(df["estimated_delivery_date"])
    df["is_late"] = df["is_late"].astype(bool)
    df["handoff_late"] = df["handoff_late"].astype(bool)
    v2 = load_v2()
    ym = df["purchase_date"].dt.strftime("%Y-%m")
    parts, n_flagged = [], {}
    for month in HOLDOUT_MONTHS:
        fl = flags_at(df, pd.Timestamp(f"{month}-01"))
        n_flagged[month] = len(fl)
        m = df[ym == month].copy()
        m["flagged"] = m["seller_id"].isin(fl)
        parts.append(m)
    h = pd.concat(parts)
    dl = (h["delivered_date"] - h["estimated_delivery_date"]).dt.days
    bins = [bin_of(int(d)) for d in dl]
    h["extra_v2"] = [0.0 if (b is None or pd.isna(s)) else v2[b]["effect"] for b, s in zip(bins, h["review_score"])]
    f, o = h[h["flagged"]], h[~h["flagged"]]
    rate_f, rate_o = float(f["is_late"].mean()), float(o["is_late"].mean())
    late_avoid = len(f) * (rate_f - rate_o)
    extra_f = float(f["extra_v2"].sum())
    return {
        "months": HOLDOUT_MONTHS,
        "min_months": MIN_MONTHS,
        "n_orders": int(len(h)),
        "n_late": int(h["is_late"].sum()),
        "flagged_sellers_first_month": n_flagged[HOLDOUT_MONTHS[0]],
        "flagged_sellers_last_month": n_flagged[HOLDOUT_MONTHS[-1]],
        "sellers_active": int(h["seller_id"].nunique()),
        "flagged_orders": int(len(f)),
        "flagged_order_share_pct": 100.0 * len(f) / len(h),
        "flagged_late": int(f["is_late"].sum()),
        "flagged_late_share_pct": 100.0 * float(f["is_late"].sum()) / float(h["is_late"].sum()),
        "handoff_late_flagged_pct": 100.0 * float(f["handoff_late"].mean()),
        "handoff_late_other_pct": 100.0 * float(o["handoff_late"].mean()),
        "late_rate_flagged_pct": 100.0 * rate_f,
        "late_rate_other_pct": 100.0 * rate_o,
        "ceiling_late_avoided": late_avoid,
        "extra_v2_all": float(h["extra_v2"].sum()),
        "extra_v2_flagged": extra_f,
        "ceiling_extra_v2_avoided": extra_f * (1.0 - rate_o / rate_f) if rate_f > 0 else 0.0,
    }


if __name__ == "__main__":
    con = duckdb.connect(os.environ.get("OLIST_DB_PATH", str(HERE.parent.parent / "olist.duckdb")), read_only=True)
    print(json.dumps(run(con), indent=2))
