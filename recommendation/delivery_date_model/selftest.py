#!/usr/bin/env python3
"""Prove that check_headlines.py fails when a locked result is wrong."""
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
    got = json.loads(EXPECTED.read_text())
    res = [report(compare(got, got) == [], "compare() is clean when the results match expected.json")]
    t = json.loads(json.dumps(got))
    t["holdout"]["model"]["v2"]["reduction"] += 5
    res.append(report(any("model.v2.reduction" in x for x in compare(t, got)), "compare() fails when the model's reduction moves by 5"))
    t = json.loads(json.dumps(got))
    t["holdout"]["bar"]["model"]["checks"][1]["pass"] = True
    res.append(report(any("checks.1.pass" in x for x in compare(t, got)), "compare() fails when the length-cap check flips to pass"))
    t = json.loads(json.dumps(got))
    t["holdout"]["model"]["bootstrap_vs_olist"]["reduction_p025"] += 3
    res.append(report(len(compare(t, got)) > 0, "compare() fails when a bootstrap bound moves past its tolerance"))
    res.append(report(identity_problems(got) == [], "identity_problems() is clean on expected.json"))
    t = json.loads(json.dumps(got))
    t["holdout"]["decision"]["model_adopted"] = True
    res.append(report(len(identity_problems(t)) > 0, "identity_problems() fails when the model is marked adopted"))
    t = json.loads(json.dumps(got))
    t["display"]["model_newly_late_added"] += 1
    res.append(report(len(identity_problems(t)) > 0, "identity_problems() fails when a rounded part no longer adds up"))
    readme = README.read_text()
    res.append(report(readme_drift(got["display"], readme) == [], "readme_drift() is clean on the README"))
    res.append(report(len(readme_drift(got["display"], readme.replace("a cut of about 811", "a cut of about 911"))) > 0,
                      "readme_drift() fails when the README's cut is edited"))
    if not all(res):
        sys.exit(1)


if __name__ == "__main__":
    main()
