#!/usr/bin/env python3
"""Prove the known-answer harness before trusting a score.

1. The hand-written key, fed back as answers (both wordings), must score full marks.
2. Correct answers written other ways (quoted names, catalog prefix, a comment naming a forbidden table) must still score full marks.
3. A deliberately bad answer set must fail every way score.py is meant to catch:
   wrong value, missing answer, abstain, a copied printed number, a forbidden table (also quoted or catalog-qualified), a printed number hidden behind a comment, a null-behavior mistake.
Usage: python verification/known_answers/selftest.py     (after `make build`)   Exit 1 if either half misbehaves.
"""
import os, re, shutil, subprocess, sys, tempfile
import yaml
import key_file
from alternatives import ALTS

HERE = os.path.dirname(os.path.abspath(__file__))
SCORE = os.path.join(HERE, "score.py")


def score(path):
    p = subprocess.run([sys.executable, SCORE, path], capture_output=True, text=True)
    return p.returncode, p.stdout


def main():
    key = {k: v.rstrip(";") for k, v in key_file.queries(open(os.path.join(HERE, "answer_key.sql")).read()).items()}
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
        "q12": 'select count(*) from "metrics"."metric_repeat_rate_90d_people" where repeated',     # quoted forbidden table
        "q13": "select count(*) from olist.metrics.metric_repeat_rate_90d_people",                 # catalog-qualified forbidden table
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
    pivot = "(pivot (select order_status, 1 as x from marts.fct_orders) on order_status using count(x))"
    bypass = [
        ("q01", "select round(0.0687*100,2) from marts.dim_date limit 1"),
        ("q02", "select 94000+931 from marts.dim_date limit 1"),
        ("q03", "select '1.28'::double from marts.dim_date limit 1"),
        ("q06", "select 96000+96 from marts.dim_customer limit 1"),
        ("q09", "select 'C'||'E' from marts.dim_date limit 1"),
        ("q24", "select '2018-'||'03' from marts.dim_date limit 1"),
        ("q11", "select round(100.0 * avg(repeated::int), 2) from query('select repeated from metrics.metric_repeat_rate_90d_people'), (select 1 from marts.dim_date limit 1) one"),
        ("q13", "select count(*) from query('select * from metrics.metric_repeat_rate_90d_people'), (select 1 from marts.dim_date limit 1) one"),
        ("q12", "select count(*) from query_table('metrics.metric_repeat_rate_90d_people'), (select 1 from marts.dim_date limit 1) one where repeated"),
        ("q04", "select cast(4155 + 1 as double) / 1000 from marts.dim_date limit 1"),
        ("q05", "select upper(lower(concat('1', '9', '.', '15'))) from marts.dim_date limit 1"),
        # review M4: literals the text check could not see, and literal arithmetic hidden behind data that cancels out
        ("q02", "select 9.4931e4 from marts.dim_date limit 1"),
        ("q02", "select 94_931 from marts.dim_date limit 1"),
        ("q02", "select 94000 + 931 * (count(*)/count(*)) from marts.dim_date"),
        ("q02", 'select 9.4931e4 as "from marts.fct_orders"'),
        ("q06", "with t as (select count(*) + 96000 + 96 - count(*) as v from marts.dim_customer) select v from t"),
        ("q09", "select $$CE$$ from marts.dim_date limit 1"),
        ("q09", "select 'C'\n'E' from marts.dim_date limit 1"),
        ("q24", "select $$2018-03$$ from marts.dim_date limit 1"),
        ("q24", "select $t$2018-03$t$ from marts.dim_date limit 1"),
        # review L1: PIVOT is judged from the plan; the plan route must not reopen the bypasses
        ("q16", 'select "canceled" * 0 + 6.25e2 from ' + pivot),
        ("q16", "select 625 + 0 * \"canceled\" from " + pivot),
        ("q11", 'select "true" from (pivot (select repeated from metrics.metric_repeat_rate_90d_people) on repeated using count(*))'),
        ("q12", "select \"true\" from (pivot (select * from query('select repeated from metrics.metric_repeat_rate_90d_people')) on repeated using count(*)) p, (select 1 from marts.dim_date limit 1) one"),
        # a constant inside the PIVOT source, so the plan carries no folded answer
        ("q16", 'select "canceled" from (pivot (select order_status, 600 as a, 25 as b from marts.fct_orders) on order_status using max(a + b))'),
        ("q16", 'select "canceled" from (pivot (select order_status, 625 as x from marts.fct_orders) on order_status using max(x))'),
        # 2: constants laundered through a CTE, a subquery, VALUES or a table function, so no constant-only expression holds the answer
        ("q02", "with c as (select 94000 as a, 931 as b) select a + b from c, marts.dim_date limit 1"),
        ("q02", "select (select a + b from (select 94000 as a, 931 as b)) from marts.dim_date limit 1"),
        ("q02", "select a + b from (values (94000, 931)) v(a, b), marts.dim_date limit 1"),
        ("q02", "select r.range + 931 from range(94000, 94001) r, marts.dim_date limit 1"),
        ("q06", "select max(a) * 2 + max(b) from (select 48000 as a, 96 as b), marts.dim_customer"),
        # a constant behind a data fingerprint; the answer changes on a changed copy, but not to the key's value,
        #   or errors there, or returns no rows there
        ("q02", "select case when count(*) % 1000 = 441 then 94000 + 931 else count(*) end from marts.fct_orders"),
        ("q02", "select greatest(94000 + 931, (count(*) - 99000) * 1000) from marts.fct_orders"),
        ("q02", "select 94000 + 931 from (select count(*) n from marts.fct_orders) where n % 1000 = 441"),
        ("q02", "select 94000 + 931 + 1 / (case when count(*) % 1000 = 441 then 1 else 0 end)::int from marts.fct_orders"),
        ("q09", "select case when count(*) % 1000 = 441 then 'C' || 'E' else 'SP' end from marts.fct_orders"),
        ("q24", "select case when count(*) % 1000 = 441 then '2018-' || '03' else max(strftime(purchase_date, '%Y-%m')) end from marts.fct_orders"),
    ]
    # correct answers written differently must still score right
    differently = [
        ("q02", "with t as (select * from marts.fct_orders) select count(*) from t where order_status = 'delivered' and delivered_to_customer_at is not null and n_items > 0 and purchase_date between date '2017-01-01' and date '2018-08-31' and n_parcels = 1;"),
        ("q06", "select cast(count(distinct customer_unique_id) as bigint) + 0 from marts.fct_orders"),
        ("q10", "select round(100.0 * count(*) filter (where order_status = 'canceled') / count(*), 2) from marts.fct_orders"),
        ("q16", 'select "canceled" from ' + pivot),                        # review L1: a correct PIVOT answer was rejected
        # a bare PIVOT statement and a comma join that starts with a subquery were rejected
        ("q07", "select count(*) from (select 1) one, (select order_id from marts.fct_order_items group by 1 having count(distinct seller_id) > 1) x"),
        ("q06", "select count(distinct customer_unique_id) from (select 1) one, marts.fct_orders"),
        ("q16", "pivot (select order_status from marts.fct_orders) on order_status in ('canceled') using count(*)"),
        ("q16", "select sum(\"canceled\") from (pivot marts.fct_orders on order_status in ('canceled') using count(*) group by order_status)"),
    ] + ALTS                                              # honest answers from other layers and idioms
    ok = True
    d2 = tempfile.mkdtemp()
    for name, overrides, expect in (("bypass", bypass, "WRONG"), ("different", differently, "RIGHT")):
        rounds = []                                       # one answer file per round, each id at most once per file
        for qid, sql in overrides:
            r = next((r for r in rounds if qid not in r), None)
            if r is None:
                rounds.append(r := {})
            r[qid] = sql
        offenders = []
        for n, r in enumerate(rounds):
            answers = dict(key)
            answers.update(r)
            path = os.path.join(d2, f"{name}{n}.yml")
            yaml.safe_dump(answers, open(path, "w"), width=100000)
            rc, out = score(path)
            got = {i: v for v, i in re.findall(r"^(RIGHT|WRONG|ABSTAIN)\s+(q\d\d)", out, re.M)}
            offenders += [f"{i}: {r[i][:60]}" for i in r if got.get(i) != expect]
        good = not offenders
        print(f"{'PASS' if good else 'FAIL'}  {name}: all {len(overrides)} overrides score {expect} (offenders: {offenders})")
        ok &= good
    # a constant can only be caught on a copy where the key's value moves, so every key must move on one copy
    sys.path.insert(0, HERE)
    import duckdb, score as scorer
    real = duckdb.connect(scorer.DB, read_only=True)
    copies = [duckdb.connect(pth, read_only=True) for pth in scorer.perturbed_paths()]
    still = [q for q, sql in key.items() if all(scorer.one(c, sql) == scorer.one(real, sql) for c in copies)]
    print(f"{'PASS' if not still else 'FAIL'}  every key value moves on at least one changed copy (unmoved: {still})")
    ok &= not still
    # review M1: a malformed header must stop the scorer, not silently re-cut the key blocks
    sb = tempfile.mkdtemp()
    for f in ("score.py", "key_file.py", "questions.yml", "questions_reworded.yml", "answer_key.sql"):
        if os.path.exists(os.path.join(HERE, f)):
            shutil.copy(os.path.join(HERE, f), sb)
    open(os.path.join(sb, "answer_key.sql"), "a").write("\n--q25\nselect 'XX';\n")
    open(os.path.join(d, "none.yml"), "w").write("{}\n")
    p = subprocess.run([sys.executable, os.path.join(sb, "score.py"), os.path.join(d, "none.yml")], capture_output=True, text=True,
                       env={**os.environ, "OLIST_DB_PATH": os.path.abspath(os.path.join(HERE, "..", "..", "olist.duckdb"))})
    good = p.returncode != 0 and "looks like a header" in p.stdout + p.stderr
    print(f"{'PASS' if good else 'FAIL'}  a malformed key header ('--q25') stops the scorer: {(p.stdout + p.stderr).strip().splitlines()[-1:]}")
    ok &= good
    shutil.rmtree(sb)
    # an answer file that gives one id twice (a plain loader keeps the last) is refused
    dup = os.path.join(d, "dup.yml")
    open(dup, "w").write("q05: \"select 1\"\n" + yaml.safe_dump(key, width=100000))
    p2 = subprocess.run([sys.executable, SCORE, dup], capture_output=True, text=True)
    good = p2.returncode != 0 and "duplicate key" in p2.stdout + p2.stderr
    print(f"{'PASS' if good else 'FAIL'}  an answer file with q05 twice is refused: {(p2.stdout + p2.stderr).strip().splitlines()[-1:]}")
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
