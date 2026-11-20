"""Shared access to the warehouse and the analysis report for the case study scripts."""
import json
import pathlib

import duckdb

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "olist.duckdb"
REPORT = ROOT / "evidence" / "recommendation_report.json"


def connect():
    return duckdb.connect(str(DB), read_only=True)


def facts():
    """Numbers the recommendation memo prints, as strings exactly as the memo shows them."""
    return json.loads(REPORT.read_text())["memo_facts"]


def row(con, sql):
    """First row of a query. DuckDB 2.0 relations have no fetchone()."""
    return con.sql(sql).fetchall()[0]
