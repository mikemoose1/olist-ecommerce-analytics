"""Shared set-up for the stress tests: the six existing fixed-effects specifications, exactly as analyze.py runs them."""
import os, sys
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import estimators as E  # noqa: E402
from data import load  # noqa: E402
ROOT = os.path.dirname(os.path.dirname(HERE))

SPECS = {"V2_preferred": dict(fe_cols=("seller", "category", "ym"), early_slope=True),
         "V1_baseline_all_on_time": dict(fe_cols=("seller", "category", "ym")),
         "V3_product_fe": dict(fe_cols=("seller", "product", "ym"), early_slope=True),
         "V4_same_actual_delivery_time": dict(fe_cols=("seller", "category", "ym", "deliv_days_cap")),
         "V5_plus_state_fe": dict(fe_cols=("seller", "category", "ym", "state"), early_slope=True),
         "V0_no_seller_fe": dict(fe_cols=("category", "ym"))}


def add_spec_columns(d):
    """The extra columns analyze.py adds before running the specifications."""
    d = d.copy()
    d["product"] = d.product_id; d["state"] = d.ship_to_state
    d["deliv_days_cap"] = (d.delivered_to_customer_at.dt.normalize() - d.purchased_at.dt.normalize()).dt.days.clip(upper=60)
    return d


def published():
    import json
    return json.load(open(os.path.join(ROOT, "evidence", "review_cost_causal_report.json")))
