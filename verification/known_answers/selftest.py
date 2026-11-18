#!/usr/bin/env python3
"""Prove the known-answer harness before trusting a score.

1. The hand-written key, fed back as answers (both wordings), must score full marks.
2. A deliberately bad answer set must fail every way score.py is meant to catch:
   wrong value, missing answer, abstain, a copied printed number, a forbidden table, a null-behavior mistake.
Usage: python verification/known_answers/selftest.py     (after `make build`)   Exit 1 if either half misbehaves.
"""
import os, re, subprocess, sys, tempfile
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
SCORE = os.path.join(HERE, "score.py")


def score(path):
    p = subprocess.run([sys.executable, SCORE, path], capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    text = open(os.path.join(HERE, "answer_key.sql")).read()
    key = {k: v.strip().rstrip(";") for k, v in re.findall(r"-- (q\d\d)\n(.*?)(?=\n-- q\d\d\n|\Z)", text, re.S)}
    bad = dict(key)
    bad.update({
        "q01": "select round(100.0 * avg((cast(delivered_to_customer_at as date) > estimated_delivery_date)::int), 2) "
               "from marts.fct_orders where order_status = 'delivered'",            # wrong population -> wrong value
        "q03": "select 1.28 from metrics.metrics_headline limit 1",                 # copied printed value
        "q06": "select 96096 from marts.fct_orders limit 1",                        # copied printed value
        "q09": "CANNOT_ANSWER",                                                     # abstain
        "q11": "select value_pct from metrics.metrics_headline where metric_name = 'repeat_rate_90d'",  # forbidden table
        "q16": "select count(*) from marts.fct_orders where order_status = 'canceled' and delivery_state = 'not_delivered'",  # misses the 6
        "q18": "select count(*) from marts.fct_orders where n_parcels is null",     # wrong null assumption
    })
    del bad["q02"]                                                                   # missing answer
    want_fail = ["q01", "q02", "q03", "q06", "q09", "q11", "q16", "q18"]
    d = tempfile.mkdtemp()
    ok = True
    for name, answers in (("key.yml", key), ("key_reworded.yml", key), ("bad.yml", bad)):
        path = os.path.join(d, name)
        yaml.safe_dump(answers, open(path, "w"), width=100000)
        rc, out = score(path)
        if name == "bad.yml":
            failed = sorted(re.findall(r"^(?:WRONG|ABSTAIN)\s+(q\d\d)", out, re.M))
            good = rc == 1 and failed == sorted(want_fail)
            print(f"{'PASS' if good else 'FAIL'}  bad answer set fails exactly {want_fail}: got {failed}")
        else:
            n = out.strip().splitlines()[-1]
            good = rc == 0
            print(f"{'PASS' if good else 'FAIL'}  key as answers ({name}): {n}")
        ok &= good
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
