#!/usr/bin/env python3
"""Prove that check_headlines.py fails when a locked result is wrong."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from check_headlines import (PASS_BAR, TUNE, bar_problems, compare, identity_problems, locks, readme_drift,  # noqa: E402
                             tradeoff_problems, tune_diff)
import holdout  # noqa: E402

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
    # the locked bar: PASS_BAR.md, the code that applies it and the recorded hashes must agree
    bar = PASS_BAR.read_text()
    tune = json.loads(TUNE.read_text())
    res.append(report(bar_problems(bar, tune) == [], "bar_problems() is clean on PASS_BAR.md"))
    res.append(report(len(bar_problems(bar.replace("at most 1.0 day longer", "at most 2.0 day longer"), tune)) > 0,
                      "bar_problems() fails when PASS_BAR.md's length cap is edited"))
    res.append(report(len(bar_problems(bar.replace("At least 90% of scored", "At least 85% of scored"), tune)) > 0,
                      "bar_problems() fails when PASS_BAR.md's coverage target is edited"))
    res.append(report(len(bar_problems(bar.replace("coverage was 90.73%", "coverage was 91.73%"), tune)) > 0,
                      "bar_problems() fails when the 90.73% tune-block coverage is misquoted"))
    res.append(report(len(bar_problems(bar.replace("quantile 0.97, a 45-day", "quantile 0.96, a 45-day"), tune)) > 0,
                      "bar_problems() fails when the scored setting in PASS_BAR.md differs from the code"))
    res.append(report(locks() == got["locks"], "locks() matches the hashes recorded in expected.json"))
    t = json.loads(json.dumps(got))
    t["locks"]["pass_bar_sha256"] = "0" * 64
    res.append(report(any("locks.pass_bar_sha256" in x for x in compare(t, got)), "compare() fails when PASS_BAR.md's hash changes"))
    t = json.loads(json.dumps(got))
    t["locks"]["tune_results_sha256"] = "0" * 64
    res.append(report(any("locks.tune_results_sha256" in x for x in compare(t, got)), "compare() fails when tune_results.json's hash changes"))
    # the trade-off chart's claims about the tuning grid
    d = got["display"]
    res.append(report(tradeoff_problems(tune, d) == [], "tradeoff_problems() is clean on tune_results.json"))
    t = json.loads(json.dumps(tune))
    far = max((x for x in t["results"] if x["summary"]["mean_extra_days_vs_olist"] > 1.0), key=lambda x: x["summary"]["reduction_v2"])
    far["summary"]["mean_extra_days_vs_olist"] = 0.9
    res.append(report(len(tradeoff_problems(t, d)) > 0, "tradeoff_problems() fails when a setting that cut more sits within the cap"))
    t = json.loads(json.dumps(tune))
    t["results"].pop()
    res.append(report(len(tradeoff_problems(t, d)) > 0, "tradeoff_problems() fails when a setting is missing"))
    # the tuning-block rerun: a rerun equal to the file is clean; a drift in any compared value fails
    info = next(x["summary"] for x in tune["results"] if x["cfg"] == holdout.INFO_CFG)
    same = {"summary": json.loads(json.dumps(info)), "route_reduction": tune["route_p95_tune"]["v2"]["reduction"],
            "route_extra_days": tune["route_p95_tune"]["mean_extra_days_vs_olist"], "olist_mean_lead": tune["olist_tune"]["mean_lead"]}
    res.append(report(tune_diff(same, tune) == [], "tune_diff() is clean when the rerun matches tune_results.json"))
    for label, change in (("labelled setting's extra days", lambda r: r["summary"].__setitem__("mean_extra_days_vs_olist", r["summary"]["mean_extra_days_vs_olist"] + 0.3)),
                          ("November 2017 spike", lambda r: r["summary"]["spikes"]["2017-11"].__setitem__("model", r["summary"]["spikes"]["2017-11"]["model"] - 30)),
                          ("route p95 reduction", lambda r: r.__setitem__("route_reduction", r["route_reduction"] + 50))):
        r = json.loads(json.dumps(same))
        change(r)
        res.append(report(len(tune_diff(r, tune)) > 0, f"tune_diff() fails when the {label} drifts"))
    if not all(res):
        sys.exit(1)


if __name__ == "__main__":
    main()
