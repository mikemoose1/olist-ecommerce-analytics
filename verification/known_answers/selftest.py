#!/usr/bin/env python3
"""Prove the known-answer harness before trusting a score.

1. The hand-written key, fed back as answers (both wordings), must score full marks.
2. Correct answers written other ways (quoted names, catalog prefix, a comment naming a forbidden table) must still score full marks.
3. A deliberately bad answer set must fail every way score.py is meant to catch:
   wrong value, missing answer, abstain, a copied printed number, a forbidden table (also quoted or catalog-qualified), a printed number hidden behind a comment, a null-behavior mistake.
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
        "q11": "select round(100.0 * avg(repeated::int), 2) from query('select repeated from metrics.metric_repeat_rate_90d_people'), (select 1 from marts.dim_date limit 1) one",
        "q16": "select count(*) from marts.fct_orders where order_status = 'canceled' and delivery_state = 'not_delivered'",  # misses the 6
        "q18": "select count(*) from marts.fct_orders where n_parcels is null",     # wrong null assumption
        "q12": 'select count(*) from "metrics"."metric_repeat_rate_90d_people" where repeated',     # quoted forbidden table
        "q13": "select count(*) from query('select * from metrics.metric_repeat_rate_90d_people'), (select 1 from marts.dim_date limit 1) one",
        "q24": "select '2018-03' from marts.fct_orders limit 1",                                    # typed text answer (a text key blocks only its own question)
        "q22": "select 94983 /* from marts.dim_customer */",                                         # printed value hidden behind a comment
    })
    del bad["q02"]                                                                   # missing answer
    want_fail = ["q01", "q02", "q03", "q06", "q09", "q11", "q12", "q13", "q16", "q18", "q22", "q24"]
    d = tempfile.mkdtemp()
    variants = dict(key)   # correct answers written another way must still score right
    variants["q22"] = 'select count(*) from "marts"."dim_customer" where n_qualifying_orders >= 1'
    variants["q21"] = "select count(*) from olist.marts.dim_customer where n_orders >= 1 and n_qualifying_orders = 0"
    variants["q13"] = "select count(*) from marts.dim_customer -- metrics.x is not read\nwhere first_qualifying_order_at <= (select max(purchased_at) from marts.fct_orders where is_qualifying_order) - interval 90 day"
    # S4 counterexamples: values computed from literals, and forbidden tables wrapped in a string for query()
    bypass = {
        "q01": "select round(0.0687*100,2) from marts.dim_date limit 1",
        "q02": "select 94000+931 from marts.dim_date limit 1",
        "q03": "select '1.28'::double from marts.dim_date limit 1",
        "q06": "select 96000+96 from marts.dim_customer limit 1",
        "q09": "select 'C'||'E' from marts.dim_date limit 1",
        "q24": "select '2018-'||'03' from marts.dim_date limit 1",
        "q11": "select round(100.0 * avg(repeated::int), 2) from query('select repeated from metrics.metric_repeat_rate_90d_people'), (select 1 from marts.dim_date limit 1) one",
        "q13": "select count(*) from query('select * from metrics.metric_repeat_rate_90d_people'), (select 1 from marts.dim_date limit 1) one",
        "q12": "select count(*) from query_table('metrics.metric_repeat_rate_90d_people'), (select 1 from marts.dim_date limit 1) one where repeated",
        "q04": "select cast(4155 + 1 as double) / 1000 from marts.dim_date limit 1",
        "q05": "select upper(lower(concat('1', '9', '.', '15'))) from marts.dim_date limit 1",
    }
    # correct answers written differently must still score right
    differently = {
        "q02": "with t as (select * from marts.fct_orders) select count(*) from t where order_status = 'delivered' and delivered_to_customer_at is not null and n_items > 0 and purchase_date between date '2017-01-01' and date '2018-08-31' and n_parcels = 1;",
        "q06": "select cast(count(distinct customer_unique_id) as bigint) + 0 from marts.fct_orders",
        "q10": "select round(100.0 * count(*) filter (where order_status = 'canceled') / count(*), 2) from marts.fct_orders",
    }
    ok = True
    d2 = tempfile.mkdtemp()
    for name, overrides, expect in (("bypass.yml", bypass, "WRONG"), ("different.yml", differently, "RIGHT")):
        answers = dict(key)
        answers.update(overrides)
        path = os.path.join(d2, name)
        yaml.safe_dump(answers, open(path, "w"), width=100000)
        rc, out = score(path)
        got = {i: v for v, i in re.findall(r"^(RIGHT|WRONG|ABSTAIN)\s+(q\d\d)", out, re.M)}
        bad_ids = sorted(i for i in overrides if got.get(i) != expect)
        good = not bad_ids
        print(f"{'PASS' if good else 'FAIL'}  {name}: every override scores {expect} (offenders: {bad_ids})")
        ok &= good
    for name, answers in (("key.yml", key), ("key_reworded.yml", key), ("variants.yml", variants), ("bad.yml", bad)):
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
