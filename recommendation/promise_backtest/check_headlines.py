#!/usr/bin/env python3
"""Rebuild the honest-date bad-review totals from the warehouse and fail if they drift.

Usage: python recommendation/promise_backtest/check_headlines.py
Needs `make build`. OLIST_DB_PATH picks the warehouse file (default: olist.duckdb in the repo root).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from evaluate import evaluate  # noqa: E402
from score import connect, score_dates  # noqa: E402

EXPECTED = HERE / "expected.json"
ABS_TOL = 1e-6
BOOT_TOL = {"reduction": 2.0, "percent": 0.2, "share": 0.02}


def db_path() -> Path:
    raw = os.environ.get("OLIST_DB_PATH", str(ROOT / "olist.duckdb"))
    path = Path(raw)
    if not path.exists():
        sys.exit(f"warehouse not found: {path} (run make build, or set OLIST_DB_PATH)")
    return path


def near(a, b, tol=ABS_TOL) -> bool:
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


def flatten(prefix, obj, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            flatten(f"{prefix}.{k}" if prefix else k, v, out)
    elif isinstance(obj, list):
        if obj and not isinstance(obj[0], (dict, list)):
            out[prefix] = obj
        else:
            for i, v in enumerate(obj):
                flatten(f"{prefix}.{i}", v, out)
    else:
        out[prefix] = obj


def compare(got: dict, expected: dict) -> list[str]:
    g, e = {}, {}
    flatten("", got, g)
    flatten("", expected, e)
    bad = []
    for key, ev in e.items():
        if key not in g:
            bad.append(f"missing {key}")
            continue
        gv = g[key]
        if isinstance(ev, bool) or isinstance(gv, bool):
            if bool(gv) != bool(ev):
                bad.append(f"{key}: got {gv!r}, expected {ev!r}")
        elif isinstance(ev, (int, float)) and not isinstance(ev, bool):
            if key.startswith("bootstrap.reduction_"):
                tol = BOOT_TOL["reduction"]
            elif key.startswith("bootstrap.percent_"):
                tol = BOOT_TOL["percent"]
            elif key.startswith("bootstrap.share_"):
                tol = BOOT_TOL["share"]
            else:
                tol = ABS_TOL
            if key.startswith("bootstrap.") and not key.startswith("bootstrap.n_") and key != "bootstrap.seed":
                if abs(float(gv) - float(ev)) > tol:
                    bad.append(f"{key}: got {gv!r}, expected {ev!r} (tol {tol})")
            elif not near(gv, ev, ABS_TOL):
                bad.append(f"{key}: got {gv!r}, expected {ev!r}")
        elif gv != ev:
            bad.append(f"{key}: got {gv!r}, expected {ev!r}")
    return bad


def headline_payload(scored, integrity, ev) -> dict:
    p95 = ev["v2"]["window"]["p95"]
    return {
        "integrity": integrity,
        "n_scored": ev["n_scored"],
        "n_reviewed": ev["n_reviewed"],
        "n_unreviewed": ev["n_unreviewed"],
        "n_reviewed_march2018": ev["n_reviewed_march2018"],
        "v2_olist_extra": ev["v2"]["window"]["olist_extra"],
        "v2_p90": ev["v2"]["window"]["p90"],
        "v2_p95": ev["v2"]["window"]["p95"],
        "v2_march_olist_extra": ev["v2"]["march"]["olist_extra"],
        "v2_march_p90": ev["v2"]["march"]["p90"],
        "v2_march_p95": ev["v2"]["march"]["p95"],
        "v4_olist_extra": ev["v4"]["window"]["olist_extra"],
        "v4_p90": ev["v4"]["window"]["p90"],
        "v4_p95": ev["v4"]["window"]["p95"],
        "four_states": ev["four_states"],
        "bar": ev["bar"],
        "overall": ev["overall"],
        "bootstrap": ev["bootstrap"],
        "display": ev["display"],
        "p95_share_pct": 100.0 * p95["reduction"] / ev["v2"]["window"]["olist_extra"],
    }


def run() -> dict:
    con = connect(db_path())
    try:
        scored, integrity = score_dates(con)
    finally:
        con.close()
    if integrity["leak_count"] != 0:
        sys.exit(f"as-of leak_count={integrity['leak_count']}, expected 0")
    if integrity["missing_pred"] != 0:
        sys.exit(f"missing_pred={integrity['missing_pred']}, expected 0")
    ev = evaluate(scored)
    # The 7-11% range on the page is the bootstrap percent interval rounded outward
    # on the low end and to the nearest whole percent on the high end.
    lo, hi = ev["bootstrap"]["percent_p025"], ev["bootstrap"]["percent_p975"]
    if not (7 <= lo < 8 and 11 <= hi < 12):
        sys.exit(f"bootstrap percent interval {lo:.3f} to {hi:.3f} no longer supports a 7% to 11% range")
    if ev["display"]["range_lo_pct"] != 7 or ev["display"]["range_hi_pct"] != 11:
        sys.exit("display range drifted from 7% to 11%")
    return headline_payload(scored, integrity, ev)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--write-expected", action="store_true", help="overwrite expected.json (only when locking a new run)")
    args = p.parse_args()
    got = run()
    if args.write_expected:
        EXPECTED.write_text(json.dumps(got, indent=2) + "\n")
        print(f"wrote {EXPECTED}")
        return
    if not EXPECTED.exists():
        sys.exit(f"missing {EXPECTED}")
    expected = json.loads(EXPECTED.read_text())
    bad = compare(got, expected)
    # print a short line either way
    d = got["display"]
    status = "PASS" if not bad else "FAIL"
    print(
        f"{status}  promise backtest: p95 reduction {d['p95_reduction_rounded']} of "
        f"{d['olist_extra_rounded']} extra bad reviews "
        f"({d['p95_share_rounded_pct']}%, range {d['range_lo_pct']}-{d['range_hi_pct']}%), "
        f"p90 {'PASS' if got['overall']['p90_pass'] else 'FAIL'}, "
        f"p95 {'PASS' if got['overall']['p95_pass'] else 'FAIL'}"
    )
    for line in bad:
        print("FAIL ", line)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
