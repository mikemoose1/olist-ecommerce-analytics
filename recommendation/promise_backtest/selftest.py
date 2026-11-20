#!/usr/bin/env python3
"""Prove that check_headlines.py fails when a locked headline is wrong."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_headlines import compare, identity_problems, readme_drift  # noqa: E402

EXPECTED = HERE / "expected.json"
README = HERE / "README.md"


def report(ok: bool, label: str) -> bool:
    print(f"{'ok  ' if ok else 'MISS'} selftest: {label}")
    return ok


def main() -> None:
    if not EXPECTED.exists():
        sys.exit("missing expected.json; run check_headlines.py first")
    got = json.loads(EXPECTED.read_text())
    results = []

    clean = compare(got, got)
    results.append(report(clean == [], "compare() is clean when the totals match expected.json"))

    tweaked = json.loads(json.dumps(got))
    tweaked["v2_p95"]["reduction"] = tweaked["v2_p95"]["reduction"] + 50
    broken = compare(tweaked, got)
    results.append(report(any("v2_p95.reduction" in line for line in broken), "compare() fails when p95 reduction is shifted by 50"))

    results.append(report(identity_problems(got) == [], "identity_problems() is clean on expected.json"))

    planted = json.loads(json.dumps(got))
    planted["four_states"]["p95"]["still_late"]["sum_delta"] += 1
    planted["display"]["still_late_reduction_rounded"] += 1
    planted_bad = identity_problems(planted)
    results.append(report(len(planted_bad) > 0, "identity_problems() fails when still-late is raised by 1"))

    readme = README.read_text()
    results.append(report(readme_drift(got["display"], readme) == [], "readme_drift() is clean on the package README"))

    missing = readme.replace("about 42 fewer come from orders late either way", "")
    missing_bad = readme_drift(got["display"], missing)
    results.append(report(any("missing fragment" in line for line in missing_bad), "readme_drift() fails when a locked fragment is missing"))

    if not all(results):
        print("planted identity", planted_bad)
        print("missing readme", missing_bad)
        sys.exit(1)


if __name__ == "__main__":
    main()
