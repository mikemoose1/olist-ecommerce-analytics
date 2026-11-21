"""Route p95 leads from the promise backtest, keyed by order, so all dates are scored on the same orders."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "promise_backtest"))
from score import score_dates  # noqa: E402


def route_p95_leads(con) -> pd.Series:
    scored, _ = score_dates(con)
    return scored.set_index("order_id")["p95_lead"].astype(int)
