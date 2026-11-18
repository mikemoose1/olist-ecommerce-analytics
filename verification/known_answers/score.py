#!/usr/bin/env python3
"""Score an agent's answers against answer_key.sql.

Usage:  python verification/known_answers/score.py ANSWERS.yml [--questions FILE]

ANSWERS.yml maps each question id to either
  q01: "select ..."                                   (one DuckDB query returning one value), or
  q01: {reasoning: "why", sql: "select ..."}          (same, with the agent's reasoning), or
  q01: {reasoning: "why", sql: CANNOT_ANSWER}         (the ontology does not say enough)

--questions picks the question file. It defaults to questions_reworded.yml when the answers file name
contains "reworded", and to questions.yml otherwise. Both files must list the same ids as the key.

A numeric answer is correct when it equals the key exactly at the rounding the question asks for;
a text answer when it equals the key. CANNOT_ANSWER counts as not correct and prints ABSTAIN, so an
honest gap in the ontology is distinguishable from a wrong query. Prints one line per question and the
score; exit 1 below 10/10.
"""
import argparse, os, re, sys
import duckdb, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("OLIST_DB_PATH", os.path.join(HERE, "..", "..", "olist.duckdb"))
ABSTAIN = "CANNOT_ANSWER"
# ontology/ prints these verified values. A query that spells one out is copying, not computing.
PRINTED = ["6.87", "94931", "94,931", "6518", "6,518", "1.28", "991", "77560", "77,560",
           "4.156", "397176", "397,176", "95560", "95,560", "96096", "96,096", "1278", "1,278",
           "3.04", "2887", "2,887", "94983", "94,983"]
LITERAL = re.compile(r"(?<![\w.,])(?:%s)(?![\w.,]|,\d)" % "|".join(re.escape(p) for p in PRINTED))


def key_queries():
    text = open(os.path.join(HERE, "answer_key.sql")).read()
    return dict(re.findall(r"-- (q\d\d)\n(.*?)(?=\n-- q\d\d\n|\Z)", text, re.S))


def one(con, sql):
    rows = con.execute(sql).fetchall()
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError(f"expected one value, got {len(rows)} rows")
    v = rows[0][0]
    return float(v) if isinstance(v, (int, float)) or hasattr(v, "as_integer_ratio") else str(v).strip()


def sql_of(entry):
    return (entry.get("sql") if isinstance(entry, dict) else entry)


def check_hardcode(sql):
    if not re.search(r"\bfrom\s+(marts|metrics|intermediate|staging)\.", sql, re.I):
        raise ValueError("answer must query a warehouse table, not hard-code a value")
    m = LITERAL.search(sql)
    if m:
        raise ValueError(f"hard-coded value {m.group(0)} copied from the ontology text")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("answers")
    ap.add_argument("--questions")
    a = ap.parse_args()
    qfile = a.questions or os.path.join(
        HERE, "questions_reworded.yml" if "reworded" in os.path.basename(a.answers) else "questions.yml")
    answers = yaml.safe_load(open(a.answers)) or {}
    questions = yaml.safe_load(open(qfile))
    keys = key_queries()
    ids = [q["id"] for q in questions]
    if sorted(ids) != sorted(keys):
        sys.exit(f"{qfile} ids {sorted(ids)} do not match the key ids {sorted(keys)}")
    con = duckdb.connect(DB, read_only=True)
    right = abstain = 0
    print(f"questions: {os.path.basename(qfile)}   answers: {os.path.basename(a.answers)}")
    for q in questions:
        want = one(con, keys[q["id"]])
        sql = sql_of(answers.get(q["id"]))
        if sql is not None and str(sql).strip().upper() == ABSTAIN:
            abstain += 1
            print(f"ABSTAIN  {q['id']}  key={want}  agent={ABSTAIN}")
            continue
        try:
            if sql is None:
                raise ValueError("no answer given")
            check_hardcode(sql)
            got = one(con, sql)
            ok = got == want
        except Exception as e:  # a query that does not run is a wrong answer
            got, ok = f"error: {str(e).splitlines()[0][:80]}", False
        right += ok
        print(f"{'RIGHT  ' if ok else 'WRONG  '}  {q['id']}  key={want}  agent={got}")
    print(f"\n{right}/{len(questions)} correct, {abstain} abstained")
    sys.exit(0 if right == len(questions) else 1)


if __name__ == "__main__":
    main()
