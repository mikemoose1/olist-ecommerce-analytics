#!/usr/bin/env python3
"""Score an agent's answers against answer_key.sql.

Usage:  python verification/known_answers/score.py ANSWERS.yml [--questions FILE] [--ids q01-q10]

ANSWERS.yml maps each question id to either
  q01: "select ..."                                   (one DuckDB query returning one value), or
  q01: {reasoning: "why", sql: "select ..."}          (same, with the agent's reasoning), or
  q01: {reasoning: "why", sql: CANNOT_ANSWER}         (the ontology does not say enough)

--ids scores only a range or list of ids (e.g. q01-q10 or q03,q11), for answer files written before later questions existed.

A question may carry  forbidden_tables: ["metrics.*", "marts.dim_customer"]  (a schema wildcard or a table name).
An answer whose SQL reads a forbidden table is WRONG, so it must be rebuilt from base tables.

--questions picks the question file. It defaults to questions_reworded.yml when the answers file name
contains "reworded", and to questions.yml otherwise. Both files must list the same ids as the key.

A numeric answer is correct when it equals the key exactly at the rounding the question asks for;
a text answer when it equals the key. CANNOT_ANSWER counts as not correct and prints ABSTAIN, so an
honest gap in the ontology is distinguishable from a wrong query. Prints one line per question and the
score; exit 1 below 10/10.
"""
import argparse, json, os, re, sys
import duckdb, yaml

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("OLIST_DB_PATH", os.path.join(HERE, "..", "..", "olist.duckdb"))
ABSTAIN = "CANNOT_ANSWER"
# ontology/ prints some verified values. A query that spells one out is copying, not computing.
PRINTED = ["6.87", "94931", "94,931", "6518", "6,518", "1.28", "991", "77560", "77,560",
           "4.156", "397176", "397,176", "95560", "95,560", "96096", "96,096", "1278", "1,278",
           "3.04", "2887", "2,887", "94983", "94,983", "17423", "17,423", "1113", "1,113",
           "625", "775", "349", "768", "762", "281"]


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


def strip_strings(sql):
    """Drop string literals and comments, and unquote identifiers, so a table name cannot hide in quotes."""
    sql = re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"'(?:[^']|'')*'", "''", sql)
    return sql.replace('"', "")


def literal_re(key_values):
    """Numbers printed in the ontology, plus every numeric key value, spelled the usual ways."""
    vals = set(PRINTED)
    for v in key_values:
        if isinstance(v, float):
            vals |= {repr(v), f"{v:.2f}", f"{v:.3f}"}
            if v == int(v) and v >= 100:
                vals |= {str(int(v)), f"{int(v):,}"}
    vals = {x for x in vals if len(x) >= 3}  # never block a bare 0, 1, 2 or 90
    return re.compile(r"(?<![\w.,])(?:%s)(?![\w.,]|,\d)" % "|".join(re.escape(x) for x in sorted(vals, key=len, reverse=True)))


def check_hardcode(sql, literal, text_keys, forbidden):
    bare = strip_strings(sql)
    if not re.search(r"\b(from|join)\s+(\w+\s*\.\s*)?(marts|metrics|intermediate|staging)\s*\.", bare, re.I):
        raise ValueError("answer must query a warehouse table, not hard-code a value")
    m = literal.search(bare)
    if m:
        raise ValueError(f"hard-coded value {m.group(0)} copied from the ontology text or the key")
    for t in text_keys:
        if f"'{t.lower()}'" in sql.lower():
            raise ValueError(f"hard-coded text answer '{t}'")
    for pat in forbidden:
        schema, _, table = pat.partition(".")
        rx = rf"(?<!\w){re.escape(schema)}\s*\.\s*" + (r"\w+" if table in ("", "*") else re.escape(table) + r"\b")
        if re.search(rx, bare, re.I):
            raise ValueError(f"reads forbidden table {pat}")


# --- structural checks on the parsed query (DuckDB's own parser), so wrapping or arithmetic cannot hide a value ---
ALLOWED_TABLE_FUNCTIONS = {"unnest", "generate_series", "range"}   # produce rows from nothing; they cannot read a table
NOT_CONSTANT_CLASSES = {"COLUMN_REF", "STAR", "SUBQUERY", "WINDOW", "PARAMETER", "LAMBDA"}
AGGREGATES = {"count", "count_star", "sum", "avg", "min", "max", "median", "mode", "any_value", "first", "last", "list",
              "string_agg", "stddev", "stddev_samp", "var_samp", "regr_slope", "corr", "bool_or", "bool_and", "arg_max", "arg_min"}


def parse(con, sql):
    out = json.loads(con.execute("select json_serialize_sql(?)", [sql]).fetchone()[0])
    if out.get("error"):
        raise ValueError(f"not a single select statement: {str(out.get('error_message'))[:60]}")
    if len(out["statements"]) != 1:
        raise ValueError("answer must be one statement")
    return out


def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def is_constant_only(expr):
    for n in walk(expr):
        if n.get("class") in NOT_CONSTANT_CLASSES or n.get("type") in NOT_CONSTANT_CLASSES:
            return False
        if n.get("class") == "FUNCTION" and str(n.get("function_name", "")).lower() in AGGREGATES:
            return False
    return True


def folded_forms(v):
    """Every way a computed constant might be printed, for comparison with the key and the printed values."""
    if isinstance(v, bool) or v is None:
        return set()
    if isinstance(v, (int, float)) or hasattr(v, "as_integer_ratio"):
        f = float(v)
        forms = {repr(f), f"{f:.2f}", f"{f:.3f}", f"{f:.4f}"}
        if f == int(f):
            forms |= {str(int(f)), f"{int(f):,}"}
        return forms
    return {str(v).strip()} if isinstance(v, str) else set()


def check_structure(con, sql, literal, text_keys, forbidden):
    tree = parse(con, sql)
    template = parse(con, "select 1")
    for n in walk(tree):
        if n.get("type") == "TABLE_FUNCTION":
            name = str((n.get("function") or {}).get("function_name", "")).lower()
            if name not in ALLOWED_TABLE_FUNCTIONS:
                raise ValueError(f"table function {name}() can hide a table; query base tables directly")
        if n.get("type") == "BASE_TABLE":
            full = f"{n.get('schema_name', '')}.{n.get('table_name', '')}".lower()
            for pat in forbidden:
                schema, _, table = pat.lower().partition(".")
                if n.get("schema_name", "").lower() == schema and table in ("", "*", n.get("table_name", "").lower()):
                    raise ValueError(f"reads forbidden table {pat}")
    # a constant-only expression (arithmetic, concatenation, cast on literals) that folds to a key or printed value is copying
    for n in walk(tree):
        if "class" not in n or n["class"] in ("CONSTANT", "COLUMN_REF") or not is_constant_only(n):
            continue
        if not any(m.get("class") == "CONSTANT" for m in walk(n)):
            continue
        probe = json.loads(json.dumps(template))
        probe["statements"][0]["node"]["select_list"] = [n]
        try:
            text = con.execute("select json_deserialize_sql(?)", [json.dumps(probe)]).fetchone()[0]
            val = con.execute(text).fetchone()[0]
        except Exception:
            continue
        forms = folded_forms(val)
        if any(literal.fullmatch(x) for x in forms) or (isinstance(val, str) and val.strip() in text_keys):
            raise ValueError(f"computes the answer from literals ({str(val)[:20]}); derive it from the tables")


def parse_ids(spec, all_ids):
    if not spec:
        return all_ids
    out = []
    for part in spec.split(","):
        lo, _, hi = part.partition("-")
        hi = hi or lo
        out += [i for i in all_ids if lo <= i <= hi]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("answers")
    ap.add_argument("--questions")
    ap.add_argument("--ids")
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
    want_all = {k: one(con, v) for k, v in keys.items()}
    literal = literal_re(v for v in want_all.values())
    selected = parse_ids(a.ids, ids)
    right = abstain = 0
    print(f"questions: {os.path.basename(qfile)}   answers: {os.path.basename(a.answers)}   scored: {len(selected)}")
    for q in questions:
        if q["id"] not in selected:
            continue
        want = want_all[q["id"]]
        sql = sql_of(answers.get(q["id"]))
        if sql is not None and str(sql).strip().upper() == ABSTAIN:
            abstain += 1
            print(f"ABSTAIN  {q['id']}  key={want}  agent={ABSTAIN}")
            continue
        try:
            if sql is None:
                raise ValueError("no answer given")
            texts = [want] if isinstance(want, str) else []
            check_hardcode(sql, literal, texts, q.get("forbidden_tables", []))
            check_structure(con, sql, literal, texts, q.get("forbidden_tables", []))   # a text key blocks only its own question: q05 may say '2018-03'
            got = one(con, sql)
            ok = got == want
        except Exception as e:  # a query that does not run is a wrong answer
            got, ok = f"error: {str(e).splitlines()[0][:80]}", False
        right += ok
        print(f"{'RIGHT  ' if ok else 'WRONG  '}  {q['id']}  key={want}  agent={got}")
    print(f"\n{right}/{len(selected)} correct, {abstain} abstained")
    sys.exit(0 if right == len(selected) else 1)


if __name__ == "__main__":
    main()
