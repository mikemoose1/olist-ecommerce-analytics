"""Checkout-time features for the per-order delivery-date model.

Every feature for an order uses only what Olist could see at that order's purchase time:
the order itself (route, parcel, freight, printed promise) and history in which a delivery,
a carrier handoff or a purchase counts only if its timestamp is strictly earlier.
"""
from __future__ import annotations

import math
import sys
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "promise_backtest"))
from score import ChunkedSorted, quantile_disc  # noqa: E402,F401

MIN_CELL = 30
LOAD_DAYS = 30
OPEN_DAYS = 30

NUMERIC = [
    "olist_lead", "distance_km", "weight_g", "volume_cm3", "n_items", "freight", "price",
    "freight_share", "same_state", "purchase_month", "purchase_weekday",
    "route_n", "route_p50", "route_p90", "route_p95",
    "cstate_p50", "cstate_p95",
    "seller_n", "seller_mean_days", "seller_late_share", "seller_handoff_days", "seller_load_30d",
    "seller_open", "global_open", "global_buys_7d", "recent_p50_14d",
]
CATEGORICAL = ["customer_state_code", "seller_state_code"]
FEATURES = NUMERIC + CATEGORICAL


def load_orders(con) -> pd.DataFrame:
    return con.execute(
        """
        WITH items AS (
            SELECT i.order_id,
                   count(*) AS n_items,
                   count(DISTINCT i.seller_id) AS n_sellers,
                   min(i.seller_id) AS seller_id,
                   sum(i.freight_value) AS freight,
                   sum(i.price) AS price,
                   sum(p.product_weight_g) AS weight_g,
                   max(p.product_length_cm * p.product_height_cm * p.product_width_cm) AS volume_cm3
            FROM marts.fct_order_items i
            LEFT JOIN marts.dim_product p USING (product_id)
            GROUP BY 1
        )
        SELECT f.order_id, f.purchased_at, f.purchase_date,
               f.delivered_to_carrier_at AS handoff_at,
               f.delivered_to_customer_at AS delivered_at,
               CAST(f.delivered_to_customer_at AS DATE) AS delivered_date,
               f.estimated_delivery_date,
               f.review_score,
               f.ship_to_state AS customer_state,
               f.ship_to_lat AS c_lat, f.ship_to_lng AS c_lng,
               it.n_items, it.n_sellers, it.seller_id, it.freight, it.price, it.weight_g, it.volume_cm3,
               s.state AS seller_state, s.lat AS s_lat, s.lng AS s_lng,
               EXISTS (SELECT 1 FROM metrics.metric_late_rate_orders m WHERE m.order_id = f.order_id) AS is_judged
        FROM marts.fct_orders f
        LEFT JOIN items it USING (order_id)
        LEFT JOIN marts.dim_seller s ON s.seller_id = it.seller_id
        ORDER BY f.order_id
        """
    ).fetchdf()


def _haversine(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lng2) - np.radians(lng1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def _q(h: ChunkedSorted | None, q: float, min_n: int = MIN_CELL) -> float:
    if h is None or h.n < min_n:
        return math.nan
    return float(h.at(quantile_disc(h.n, q)))


def build(con) -> pd.DataFrame:
    """One row per order with label, promise and as-of features."""
    df = load_orders(con)
    df["purchased_at"] = pd.to_datetime(df["purchased_at"])
    df["purchase_date"] = pd.to_datetime(df["purchase_date"])
    df["delivered_at"] = pd.to_datetime(df["delivered_at"])
    df["delivered_date"] = pd.to_datetime(df["delivered_date"])
    df["handoff_at"] = pd.to_datetime(df["handoff_at"])
    df["estimated_delivery_date"] = pd.to_datetime(df["estimated_delivery_date"])
    df["is_judged"] = df["is_judged"].astype(bool)
    df["actual_days"] = (df["delivered_date"] - df["purchase_date"]).dt.days
    df["olist_lead"] = (df["estimated_delivery_date"] - df["purchase_date"]).dt.days
    df["olist_days_late"] = (df["delivered_date"] - df["estimated_delivery_date"]).dt.days
    df["route"] = df["seller_state"].fillna("?") + ">" + df["customer_state"].fillna("?")
    df["in_history"] = df["delivered_at"].notna() & df["actual_days"].notna() & (df["n_sellers"] == 1) & df["seller_id"].notna()
    df["distance_km"] = _haversine(df["s_lat"], df["s_lng"], df["c_lat"], df["c_lng"])
    df["freight_share"] = df["freight"] / (df["freight"] + df["price"])
    df["same_state"] = (df["seller_state"] == df["customer_state"]).astype(float)
    df["purchase_month"] = df["purchase_date"].dt.month.astype(float)
    df["purchase_weekday"] = df["purchase_date"].dt.weekday.astype(float)
    states = sorted(set(df["customer_state"].dropna()) | set(df["seller_state"].dropna()))
    code = {s: i for i, s in enumerate(states)}
    df["customer_state_code"] = df["customer_state"].map(code).astype(float)
    df["seller_state_code"] = df["seller_state"].map(code).astype(float)

    recs = df.to_dict("records")
    events = []
    for i, r in enumerate(recs):
        events.append((r["purchased_at"].value, 0, i))
        if pd.notna(r["handoff_at"]):
            events.append((r["handoff_at"].value, 1, i))
        if pd.notna(r["delivered_at"]):
            events.append((r["delivered_at"].value, 2, i))
    # Purchases sort first at a tied timestamp, so history only holds strictly earlier events.
    events.sort()

    route_h: dict[str, ChunkedSorted] = {}
    cstate_h: dict[str, ChunkedSorted] = {}
    seller_n = defaultdict(int)
    seller_sum = defaultdict(float)
    seller_late = defaultdict(int)
    seller_ho_n = defaultdict(int)
    seller_ho_sum = defaultdict(float)
    seller_buys: dict[str, deque] = defaultdict(deque)
    seller_open = defaultdict(int)
    open_orders: deque = deque()  # (purchase ns, idx) for orders not yet delivered
    global_buys: deque = deque()
    recent_deliv: deque = deque()  # (delivered ns, actual_days)
    day_ns = 86_400 * 10**9

    out = {k: np.full(len(recs), np.nan) for k in (
        "route_n", "route_p50", "route_p90", "route_p95", "cstate_p50", "cstate_p95",
        "seller_n", "seller_mean_days", "seller_late_share", "seller_handoff_days", "seller_load_30d",
        "seller_open", "global_open", "global_buys_7d", "recent_p50_14d")}
    open_count = 0

    for ts, kind, i in events:
        r = recs[i]
        sid = r["seller_id"]
        if kind == 2:
            if r.get("_counted_open"):
                open_count -= 1
                if isinstance(sid, str):
                    seller_open[sid] -= 1
                r["_counted_open"] = False
            if r["in_history"]:
                a = int(r["actual_days"])
                route_h.setdefault(r["route"], ChunkedSorted()).add(a)
                if isinstance(r["customer_state"], str):
                    cstate_h.setdefault(r["customer_state"], ChunkedSorted()).add(a)
                seller_n[sid] += 1
                seller_sum[sid] += a
                seller_late[sid] += int(r["olist_days_late"] > 0)
                recent_deliv.append((ts, a))
            continue
        if kind == 1:
            if r["in_history"] and isinstance(sid, str):
                seller_ho_n[sid] += 1
                seller_ho_sum[sid] += (r["handoff_at"] - r["purchased_at"]).total_seconds() / 86400.0
            continue
        # purchase: compute features from strictly earlier history, then register the purchase
        while open_orders and open_orders[0][0] < ts - OPEN_DAYS * day_ns:
            _, j = open_orders.popleft()
            if recs[j].get("_counted_open"):
                open_count -= 1
                sj = recs[j]["seller_id"]
                if isinstance(sj, str):
                    seller_open[sj] -= 1
                recs[j]["_counted_open"] = False
        while global_buys and global_buys[0] < ts - 7 * day_ns:
            global_buys.popleft()
        while recent_deliv and recent_deliv[0][0] < ts - 14 * day_ns:
            recent_deliv.popleft()
        rh = route_h.get(r["route"])
        out["route_n"][i] = rh.n if rh else 0
        out["route_p50"][i] = _q(rh, 0.5)
        out["route_p90"][i] = _q(rh, 0.9)
        out["route_p95"][i] = _q(rh, 0.95)
        ch = cstate_h.get(r["customer_state"]) if isinstance(r["customer_state"], str) else None
        out["cstate_p50"][i] = _q(ch, 0.5)
        out["cstate_p95"][i] = _q(ch, 0.95)
        out["global_open"][i] = open_count
        out["global_buys_7d"][i] = len(global_buys)
        if len(recent_deliv) >= MIN_CELL:
            out["recent_p50_14d"][i] = float(np.median([a for _, a in recent_deliv]))
        if isinstance(sid, str):
            n = seller_n[sid]
            out["seller_n"][i] = n
            if n > 0:
                out["seller_mean_days"][i] = seller_sum[sid] / n
                out["seller_late_share"][i] = seller_late[sid] / n
            if seller_ho_n[sid] > 0:
                out["seller_handoff_days"][i] = seller_ho_sum[sid] / seller_ho_n[sid]
            dq = seller_buys[sid]
            while dq and dq[0] < ts - LOAD_DAYS * day_ns:
                dq.popleft()
            out["seller_load_30d"][i] = len(dq)
            out["seller_open"][i] = seller_open[sid]
            dq.append(ts)
            seller_open[sid] += 1
        global_buys.append(ts)
        open_orders.append((ts, i))
        r["_counted_open"] = True
        open_count += 1

    for k, v in out.items():
        df[k] = v
    return df
