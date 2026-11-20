#!/usr/bin/env python3
"""Prove that check_headlines.py fails when a locked headline is wrong."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_headlines import compare  # noqa: E402

EXPECTED = HERE / "expected.json"


def main() -> None:
    if not EXPECTED.exists():
        sys.exit("missing expected.json; run check_headlines.py first")
    got = json.loads(EXPECTED.read_text())
    clean = compare(got, got)
    tweaked = json.loads(json.dumps(got))
    tweaked["v2_p95"]["reduction"] = tweaked["v2_p95"]["reduction"] + 50
    broken = compare(tweaked, got)
    ok_clean = clean == []
    ok_broken = any("v2_p95.reduction" in line for line in broken)
    print(f"{'ok  ' if ok_clean else 'MISS'} selftest: compare() is clean when the totals match expected.json")
    print(f"{'ok  ' if ok_broken else 'MISS'} selftest: compare() fails when p95 reduction is shifted by 50")
    if not ok_clean or not ok_broken:
        print("clean", clean)
        print("broken", broken)
        sys.exit(1)


if __name__ == "__main__":
    main()
