"""Walk-forward route-median, route-p90 and route-p95 delivery dates.

For each purchase, only deliveries strictly before that purchase may be used.
Fallback is customer state, then global. A cell needs at least 30 prior deliveries
except when falling back to a thin global history.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

BURN_IN = date(2017, 4, 1)
MIN_CELL = 30


def quantile_disc(n: int, q: float) -> int | None:
    if n == 0:
        return None
    idx = int(math.ceil(q * n) - 1)
    if idx < 0:
        idx = 0
    if idx >= n:
        idx = n - 1
    return idx


class ChunkedSorted:
    __slots__ = ("chunk", "chunks", "n")

    def __init__(self, chunk: int = 256):
        self.chunk = chunk
        self.chunks: list[list[int]] = []
        self.n = 0

    def add(self, x: int) -> None:
        from bisect import bisect_left

        self.n += 1
        if not self.chunks:
            self.chunks.append([x])
            return
        lo, hi = 0, len(self.chunks) - 1
        target = hi
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.chunks[mid][-1] >= x:
                target = mid
                hi = mid - 1
            else:
                lo = mid + 1
        ch = self.chunks[target]
        ch.insert(bisect_left(ch, x), x)
        if len(ch) >= self.chunk * 2:
            mid = len(ch) // 2
            self.chunks.insert(target + 1, ch[mid:])
            del ch[mid:]

    def at(self, idx: int) -> int:
        for ch in self.chunks:
            if idx < len(ch):
                return ch[idx]
            idx -= len(ch)
        raise IndexError(idx)

    def q(self, quantile: float, min_n: int = MIN_CELL) -> tuple[int | None, int]:
        if self.n < min_n:
            return None, self.n
        idx = quantile_disc(self.n, quantile)
        return int(self.at(idx)), self.n


class KeyHists:
    def __init__(self):
        self._h: dict[str, ChunkedSorted] = {}

    def add(self, key: str, value: int) -> None:
        h = self._h.get(key)
        if h is None:
            h = ChunkedSorted()
            self._h[key] = h
        h.add(value)

    def first(self, keys: list[tuple[str, str]], q: float) -> tuple[int | None, str, int]:
        for label, key in keys:
            h = self._h.get(key)
            if h is not None:
                val, n2 = h.q(q)
                if val is not None:
                    return val, label, n2
        h = self._h.get("global")
        if h is None:
            return None, "global_thin", 0
        val, n = h.q(q, min_n=1)
        return val, "global_thin", n


def route_keys(route: str, state: str) -> list[tuple[str, str]]:
    return [("route", f"r|{route}"), ("state", f"c|{state}"), ("global", "global")]


def load_orders(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    con.execute(
        """
        CREATE OR REPLACE TEMP VIEW seller_per_order AS
        SELECT i.order_id,
               count(DISTINCT i.seller_id) AS n_sellers,
               any_value(i.seller_id) AS seller_id,
               any_value(s.state) AS seller_state
        FROM marts.fct_order_items i
        JOIN marts.dim_seller s USING (seller_id)
        GROUP BY 1
        """
    )
    return con.execute(
        """
        SELECT
            f.order_id,
            f.purchased_at,
            f.purchase_date,
            f.delivered_to_customer_at AS delivered_at,
            CAST(f.delivered_to_customer_at AS DATE) AS delivered_date,
            f.estimated_delivery_date,
            f.review_score,
            CASE WHEN f.delivered_to_customer_at IS NOT NULL
                 THEN date_diff('day', f.purchase_date, CAST(f.delivered_to_customer_at AS DATE))
            END AS actual_days,
            f.ship_to_state AS customer_state,
            sp.seller_id,
            sp.seller_state,
            sp.n_sellers,
            (sp.seller_state || '→' || f.ship_to_state) AS route,
            EXISTS (
                SELECT 1 FROM metrics.metric_late_rate_orders m
                WHERE m.order_id = f.order_id
            ) AS is_judged
        FROM marts.fct_orders f
        LEFT JOIN seller_per_order sp ON sp.order_id = f.order_id
        """
    ).fetchdf()


def pack(purchase_date, delivered_date, lead, tag):
    if lead is None:
        return None
    d = purchase_date + timedelta(days=int(lead))
    days_late = (delivered_date - d).days
    return {
        f"{tag}_lead": int(lead),
        f"{tag}_date": d,
        f"{tag}_days_late": int(days_late),
        f"{tag}_late": days_late > 0,
    }


def score_dates(con: duckdb.DuckDBPyConnection) -> tuple[pd.DataFrame, dict]:
    orders = load_orders(con).reset_index(drop=True)
    recs = orders.to_dict("records")
    for r in recs:
        r["in_history"] = (
            pd.notna(r["delivered_at"])
            and pd.notna(r["actual_days"])
            and r["n_sellers"] == 1
            and pd.notna(r["seller_id"])
            and pd.notna(r["route"])
        )
        r["is_judged"] = bool(r["is_judged"])

    events = []
    for i, r in enumerate(recs):
        events.append((pd.Timestamp(r["purchased_at"]), 0, i))
        if pd.notna(r["delivered_at"]):
            events.append((pd.Timestamp(r["delivered_at"]), 1, i))
    events.sort(key=lambda e: (e[0], e[1], e[2]))

    hist = KeyHists()
    last_delivery = None
    leak_count = 0
    missing_pred = 0
    scored_rows = []

    for ts, kind, i in events:
        r = recs[i]
        if kind == 1:
            if r["in_history"]:
                route = r["route"]
                state = r["customer_state"] if pd.notna(r["customer_state"]) else "__unknown__"
                actual = int(r["actual_days"])
                for _label, key in route_keys(route, state):
                    hist.add(key, actual)
            if last_delivery is None or ts > last_delivery:
                last_delivery = ts
            continue

        purchased_at = pd.Timestamp(r["purchased_at"])
        if last_delivery is not None and last_delivery >= purchased_at:
            leak_count += 1

        is_scored = r["is_judged"] and pd.Timestamp(r["purchase_date"]).date() >= BURN_IN
        if not is_scored:
            continue

        route = r["route"] if pd.notna(r["route"]) else "__unknown__"
        state = r["customer_state"] if pd.notna(r["customer_state"]) else "__unknown__"
        keys = route_keys(route, state)
        med, _fb_med, _n_med = hist.first(keys, 0.5)
        p90, _fb_p90, _n_p90 = hist.first(keys, 0.9)
        p95, _fb_p95, _n_p95 = hist.first(keys, 0.95)
        if med is None or p90 is None or p95 is None:
            missing_pred += 1
            continue

        purchase_date = pd.Timestamp(r["purchase_date"]).date()
        delivered_date = pd.Timestamp(r["delivered_date"]).date()
        olist_date = pd.Timestamp(r["estimated_delivery_date"]).date()
        olist_days = (delivered_date - olist_date).days
        row = {
            "order_id": r["order_id"],
            "purchased_at": purchased_at,
            "purchase_date": purchase_date,
            "year_month": purchase_date.strftime("%Y-%m"),
            "delivered_date": delivered_date,
            "olist_date": olist_date,
            "olist_days_late": int(olist_days),
            "olist_late": olist_days > 0,
            "review_score": r["review_score"],
        }
        for p in (
            pack(purchase_date, delivered_date, med, "likely"),
            pack(purchase_date, delivered_date, p90, "p90"),
            pack(purchase_date, delivered_date, p95, "p95"),
        ):
            row.update(p)
        scored_rows.append(row)

    scored = pd.DataFrame(scored_rows)
    integrity = {
        "leak_count": leak_count,
        "missing_pred": missing_pred,
        "n_scored": int(len(scored)),
        "burn_in": BURN_IN.isoformat(),
        "min_cell": MIN_CELL,
    }
    return scored, integrity


def connect(db_path: str | Path):
    return duckdb.connect(str(db_path), read_only=True)
