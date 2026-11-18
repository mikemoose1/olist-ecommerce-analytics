#!/usr/bin/env python3
"""Score an agent's answers to questions.yml against answer_key.sql.

Usage:  python verification/known_answers/score.py ANSWERS.yml
ANSWERS.yml maps each question id to one DuckDB SQL query returning one value, e.g.
  q01: "select ..."
A numeric answer is correct when it equals the key exactly at the rounding the question asks for;
a text answer when it equals the key. Prints one line per question and the score; exit 1 below 10/10.
"""
import os, re, sys
import duckdb, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("OLIST_DB_PATH", os.path.join(HERE, "..", "..", "olist.duckdb"))


def key_queries():
    text = open(os.path.join(HERE, "answer_key.sql")).read()
    return dict(re.findall(r"-- (q\d\d)\n(.*?)(?=\n-- q\d\d\n|\Z)", text, re.S))


def one(con, sql):
    rows = con.execute(sql).fetchall()
    if len(rows) != 1 or len(rows[0]) != 1:
        raise ValueError(f"expected one value, got {len(rows)} rows")
    v = rows[0][0]
    return float(v) if isinstance(v, (int, float)) or hasattr(v, "as_integer_ratio") else str(v).strip()


def main():
    answers = yaml.safe_load(open(sys.argv[1]))
    con = duckdb.connect(DB, read_only=True)
    questions = yaml.safe_load(open(os.path.join(HERE, "questions.yml")))
    keys, right = key_queries(), 0
    for q in questions:
        want = one(con, keys[q["id"]])
        try:
            sql = answers[q["id"]]
            # ontology.yml prints some answers (row counts, verified values); a hard-coded number proves nothing
            if not re.search(r"\bfrom\s+(marts|metrics|intermediate|staging)\.", sql, re.I):
                raise ValueError("answer must query a warehouse table, not hard-code a value")
            got = one(con, sql)
            ok = got == want
        except Exception as e:  # a query that does not run is a wrong answer
            got, ok = f"error: {str(e).splitlines()[0][:80]}", False
        right += ok
        print(f"{'RIGHT' if ok else 'WRONG'}  {q['id']}  key={want}  agent={got}")
    print(f"\n{right}/{len(questions)} correct")
    sys.exit(0 if right == len(questions) else 1)


if __name__ == "__main__":
    main()
