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
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile
import duckdb, yaml
import key_file

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("OLIST_DB_PATH", os.path.join(HERE, "..", "..", "olist.duckdb"))
ABSTAIN = "CANNOT_ANSWER"
# ontology/ prints some verified values. A query that spells one out is copying, not computing.
PRINTED = ["6.87", "94931", "94,931", "6518", "6,518", "1.28", "991", "77560", "77,560",
           "4.156", "397176", "397,176", "95560", "95,560", "96096", "96,096", "1278", "1,278",
           "3.04", "2887", "2,887", "94983", "94,983", "17423", "17,423", "1113", "1,113",
           "625", "775", "349", "768", "762", "281"]


def key_queries():
    """the same parser append_only.py fingerprints with (key_file.py), so both read the same blocks"""
    return key_file.queries(open(os.path.join(HERE, "answer_key.sql")).read())


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
    sql = re.sub(r"\$(\w*)\$.*?\$\1\$", "''", sql, flags=re.S)      # dollar-quoted strings: $$x$$, $tag$x$tag$
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
    # (the parse tree or the plan proves a warehouse table is read; a text pattern here rejected `from (pivot marts.x ...)`
    # and `from (select 1) one, marts.x`)
    m = literal.search(bare)
    if m:
        raise ValueError(f"hard-coded value {m.group(0)} copied from the ontology text or the key")
    for t in text_keys:
        if f"'{t.lower()}'" in sql.lower() or re.search(rf"\$(\w*)\${re.escape(t.lower())}\$\1\$", sql.lower()):
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


WAREHOUSE = {"marts", "metrics", "intermediate", "staging"}


def parse(con, sql):
    out = json.loads(con.execute("select json_serialize_sql(?)", [sql]).fetchone()[0])
    if out.get("error"):
        raise NotSerializable(str(out.get("error_message"))[:60])
    if len(out["statements"]) != 1:
        raise ValueError("answer must be one statement")
    return out


class NotSerializable(ValueError):
    pass


def walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from walk(v)


def is_data(n):
    """a node whose value comes from the tables: a column, a subquery, a window, or an aggregate"""
    return n.get("class") in NOT_CONSTANT_CLASSES or n.get("type") in NOT_CONSTANT_CLASSES or \
        (n.get("class") == "FUNCTION" and str(n.get("function_name", "")).lower() in AGGREGATES)


def is_constant_only(expr):
    return not any(is_data(n) for n in walk(expr))


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


def copies_answer(val, literal, text_keys):
    return any(literal.fullmatch(x) for x in folded_forms(val)) or (isinstance(val, str) and val.strip() in text_keys)


def evaluate(con, template, expr):
    """the value of one expression with no FROM, or None if it does not run"""
    probe = json.loads(json.dumps(template))
    probe["statements"][0]["node"]["select_list"] = [expr]
    try:
        text = con.execute("select json_deserialize_sql(?)", [json.dumps(probe)]).fetchone()[0]
        return con.execute(text).fetchone()[0], True
    except Exception:
        return None, False


def identity(node):
    """a node without its position, so the same subexpression written twice is recognised as the same"""
    if isinstance(node, dict):
        return {k: identity(v) for k, v in node.items() if not k.startswith("query_location") and k != "alias"}
    if isinstance(node, list):
        return [identity(v) for v in node]
    return node


def substitute(node, values, template_const, trial):
    """replace every data node by a number; the same data node (by identity) always gets the same number"""
    if isinstance(node, list):
        return [substitute(v, values, template_const, trial) for v in node]
    if not isinstance(node, dict):
        return node
    if is_data(node):
        k = json.dumps(identity(node), sort_keys=True)
        i = values.setdefault(k, len(values))
        c = json.loads(json.dumps(template_const))
        c["literal"]["text"] = f"{3.7 + 11.3 * i + 5.9 * trial + 0.17 * i * trial:.2f}"
        return c
    return {k: substitute(v, values, template_const, trial) for k, v in node.items()}


def check_structure(con, sql, literal, text_keys, forbidden):
    try:
        tree = parse(con, sql)
    except NotSerializable as e:
        return check_plan(con, sql, literal, text_keys, forbidden, e)
    template = parse(con, "select 1")
    template_const = parse(con, "select 7.25")["statements"][0]["node"]["select_list"][0]
    reads_warehouse = False
    for n in walk(tree):
        if n.get("type") == "TABLE_FUNCTION":
            name = str((n.get("function") or {}).get("function_name", "")).lower()
            if name not in ALLOWED_TABLE_FUNCTIONS:
                raise ValueError(f"table function {name}() can hide a table; query base tables directly")
        if n.get("type") == "BASE_TABLE":
            reads_warehouse |= n.get("schema_name", "").lower() in WAREHOUSE
            for pat in forbidden:
                schema, _, table = pat.lower().partition(".")
                if n.get("schema_name", "").lower() == schema and table in ("", "*", n.get("table_name", "").lower()):
                    raise ValueError(f"reads forbidden table {pat}")
    if not reads_warehouse:
        raise ValueError("answer must read a warehouse table (marts, metrics, intermediate or staging)")
    # 1. a constant-only expression (a literal in any spelling: 9.4931e4, 94_931, $$CE$$, 'C' 'E'; or arithmetic,
    #    concatenation, casts on literals) whose value is a key or printed value is copying
    for n in walk(tree):
        if "class" not in n or n["class"] == "COLUMN_REF" or not is_constant_only(n):
            continue
        if not any(m.get("class") == "CONSTANT" for m in walk(n)):
            continue
        val, ran = evaluate(con, template, n)
        if ran and copies_answer(val, literal, text_keys):
            raise ValueError(f"computes the answer from literals ({str(val)[:20]}); derive it from the tables")
    # 2. an expression that mixes literals with data but whose value does not depend on the data
    #    (94000 + 931 * (count(*)/count(*))): give every data node two different made-up values; same answer both times = copying
    for sel in (n for n in walk(tree) if isinstance(n.get("select_list"), list)):
        for expr in sel["select_list"]:
            if is_constant_only(expr) or not any(m.get("class") == "CONSTANT" for m in walk(expr)):
                continue
            got = []
            for trial in (0, 1):
                val, ran = evaluate(con, template, substitute(expr, {}, template_const, trial))
                if not ran:
                    break
                got.append(val)
            if len(got) == 2 and got[0] == got[1] and copies_answer(got[0], literal, text_keys):
                raise ValueError(f"the value ({str(got[0])[:20]}) does not depend on the data; derive it from the tables")


SCANS_OK = {"SEQ_SCAN", "DUMMY_SCAN", "EMPTY_RESULT", "DELIM_SCAN", "CTE_SCAN", "COLUMN_DATA_SCAN"}


def plan(con, sql, optimize):
    con.execute("pragma enable_optimizer" if optimize else "pragma disable_optimizer")
    try:
        rows = con.execute("explain (format json) " + sql).fetchall()
    finally:
        con.execute("pragma enable_optimizer")
    nodes = []

    def w(n):
        nodes.append(n)
        for c in n.get("children", []):
            w(c)
    for _, text in rows:
        for top in json.loads(text):
            w(top)
    return nodes


def check_plan(con, sql, literal, text_keys, forbidden, why):
    """PIVOT (and only PIVOT) cannot be serialized to a parse tree. Judge it from DuckDB's plan instead:
    every scan must be a warehouse table (unoptimized plan, so no scan is answered from statistics), and no constant in the
    optimized plan (where DuckDB has already folded literal arithmetic) may be a key or printed value."""
    if not re.search(r"\b(un)?pivot\b", strip_strings(sql), re.I):
        raise ValueError(f"not a single select statement: {why}")
    stmts = con.extract_statements(sql)
    if len(stmts) != 1 or stmts[0].type.name not in ("SELECT", "MULTI"):
        raise ValueError("answer must be one SELECT statement")
    tables = []
    for n in plan(con, sql, optimize=False):
        name = n.get("name", "")
        if name.endswith("_SCAN") or name in ("READ_CSV", "READ_PARQUET", "READ_JSON", "TABLE_SCAN"):
            if name not in SCANS_OK:
                raise ValueError(f"plan has a {name} scan; query base tables directly")
            t = (n.get("extra_info") or {}).get("Table")
            if name == "SEQ_SCAN":
                if not t:
                    raise ValueError("plan has a scan with no table name")
                tables.append(t.lower().split(".")[-2:])
    if not any(s in WAREHOUSE for s, _ in tables):
        raise ValueError("answer must read a warehouse table (marts, metrics, intermediate or staging)")
    for schema, table in tables:
        for pat in forbidden:
            ps, _, pt = pat.lower().partition(".")
            if schema == ps and pt in ("", "*", table):
                raise ValueError(f"reads forbidden table {pat}")
    for n in plan(con, sql, optimize=True):
        info = {k: v for k, v in (n.get("extra_info") or {}).items() if k not in ("Estimated Cardinality", "Table")}
        text = json.dumps(info)
        for tok in re.findall(r"(?<![\w.#])-?\d+(?:\.\d+)?(?:e-?\d+)?(?![\w.])", text):
            if copies_answer(float(tok), literal, text_keys) or literal.fullmatch(tok):
                raise ValueError(f"plan computes the answer from literals ({tok}); derive it from the tables")
        for t in text_keys:
            if f"'{t}'" in text:
                raise ValueError(f"hard-coded text answer '{t}'")


# --- changed copies of the warehouse: no text or tree check can see every way to
#     launder a constant (a CTE, a subquery, VALUES, a table function, a PIVOT source, a data fingerprint such as
#     `case when count(*) % 1000 = 931`). So the answer must also equal the key on two copies of the warehouse rebuilt by dbt
#     from changed raw files. Each copy removes about 1 order in 10, picked by a hash of order_id, with its items, payments,
#     reviews and customer row, so every layer (staging, intermediate, marts, metrics) agrees with every other, as on the
#     real data. Each copy also removes half the on-time orders in one half of the states and months (copy a one half,
#     copy b the other), so rates and the state or month that tops them move too. An answer computed from the data
#     follows the key on both copies; a typed-in value, or a rule that matches the real data only by chance, does not.
PERTURB_VERSION = "3"
COPIES = ("a", "b")
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
RAW = os.path.abspath(os.path.join(ROOT, os.environ.get("OLIST_RAW_DIR", os.path.join("data", "raw"))))


def _inputs_tag():
    """a copy is rebuilt when the dbt project, the raw files or this perturbation changes"""
    h = hashlib.sha256(f"{PERTURB_VERSION}|{RAW}".encode())
    for top in ("models", "macros", "seeds", "dbt_project.yml", "packages.yml"):
        base = os.path.join(ROOT, top)
        files = [base] if os.path.isfile(base) else sorted(os.path.join(dp, f) for dp, _, fs in os.walk(base) for f in fs)
        for f in files:
            h.update(f"{os.path.relpath(f, ROOT)}\0".encode() + open(f, "rb").read())
    for f in sorted(os.listdir(RAW)):
        st = os.stat(os.path.join(RAW, f))
        h.update(f"{f}|{st.st_size}|{st.st_mtime_ns}".encode())
    return h.hexdigest()[:16]


def _write_raw(out, copy):
    """the raw CSVs for one copy: orders removed (and everything that hangs off them), other files linked unchanged"""
    c = duckdb.connect()
    rd = lambda n: f"read_csv('{RAW}/{n}', header=true, all_varchar=true)"
    half = "= 0" if copy == "a" else "= 1"
    c.execute(f"""create temp table gone as
        select o.order_id, o.customer_id from {rd('olist_orders_dataset.csv')} o
        left join {rd('olist_customers_dataset.csv')} c using (customer_id)
        where hash(o.order_id || '|{copy}') % 10 = 0
           or (try_cast(o.order_delivered_customer_date as date) <= try_cast(o.order_estimated_delivery_date as date)
               and hash(o.order_id || '|on-time|{copy}') % 2 = 0
               and (hash(coalesce(c.customer_state, '') || '|state') % 2 {half}
                    or hash(substr(o.order_purchase_timestamp, 1, 7) || '|month') % 2 {half}))""")
    for f in sorted(os.listdir(RAW)):
        cols = [r[0] for r in c.execute(f"describe select * from {rd(f)}").fetchall()]
        key = "order_id" if "order_id" in cols else "customer_id" if "customer_id" in cols else None
        if key is None:
            os.symlink(os.path.join(RAW, f), os.path.join(out, f))
            continue
        c.execute(f"copy (select * from {rd(f)} where {key} not in (select {key} from gone)) to '{out}/{f}' (header, force_quote *)")
    c.close()


def _build_copy(base, copy):
    final = os.path.join(base, copy)
    path = os.path.join(final, "olist.duckdb")            # same catalog name, so olist.marts.x still resolves
    if os.path.exists(path):
        return path
    os.makedirs(base, exist_ok=True)
    work = tempfile.mkdtemp(dir=base, prefix=f"{copy}.building.")
    raw = os.path.join(work, "raw")
    os.mkdir(raw)
    _write_raw(raw, copy)
    dbt = os.path.join(os.path.dirname(sys.executable), "dbt")
    dbt = dbt if os.path.exists(dbt) else (shutil.which("dbt") or "dbt")
    p = subprocess.run([dbt, "build", "--resource-type", "model", "--resource-type", "seed", "--project-dir", ROOT,
                        "--profiles-dir", ROOT, "--target-path", os.path.join(work, "target"), "--log-path", os.path.join(work, "logs")],
                       cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "OLIST_RAW_DIR": raw, "OLIST_DB_PATH": os.path.join(work, "olist.duckdb")})
    if p.returncode:
        raise RuntimeError(f"building changed copy {copy} of the warehouse failed:\n{p.stdout[-2000:]}{p.stderr[-2000:]}")
    for d in ("raw", "target", "logs"):
        shutil.rmtree(os.path.join(work, d), ignore_errors=True)
    try:
        os.rename(work, final)
    except OSError:                                       # another scorer finished the same copy first
        shutil.rmtree(work, ignore_errors=True)
    return path


def perturbed_paths():
    base = os.path.join(tempfile.gettempdir(), f"olist_perturbed_{_inputs_tag()}")
    return [_build_copy(base, c) for c in COPIES]


def check_copies(sql, wants, pcons):
    """the answer must run, give one value, and equal the key on every changed copy (fails closed)"""
    for copy, pcon, want in zip(COPIES, pcons, wants):
        try:
            got = one(pcon, sql)
        except Exception as e:
            raise ValueError(f"fails on changed copy {copy} of the warehouse (some orders removed): {str(e).splitlines()[0][:60]}")
        if got != want:
            raise ValueError(f"on changed copy {copy} of the warehouse (some orders removed) it gives {got}, the key {want}: "
                             f"a typed-in value, or a rule that fits the real data only by chance")


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
    answers = key_file.load_yaml(open(a.answers).read()) or {}     # an id given twice is refused, not last-wins
    questions = key_file.load_yaml(open(qfile).read())
    keys = key_queries()
    ids = [q["id"] for q in questions]
    if len(ids) != len(set(ids)):
        sys.exit(f"{qfile} lists an id twice: {sorted(i for i in set(ids) if ids.count(i) > 1)}")
    if sorted(ids) != sorted(keys):
        sys.exit(f"{qfile} ids {sorted(ids)} do not match the key ids {sorted(keys)}")
    con = duckdb.connect(DB, read_only=True)
    want_all = {k: one(con, v) for k, v in keys.items()}
    pcons = [duckdb.connect(p, read_only=True) for p in perturbed_paths()]
    want_copies = [{k: one(pc, v) for k, v in keys.items()} for pc in pcons]
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
            if ok:
                check_copies(sql, [w[q["id"]] for w in want_copies], pcons)
        except Exception as e:  # a query that does not run is a wrong answer
            got, ok = f"error: {str(e).splitlines()[0][:80]}", False
        right += ok
        print(f"{'RIGHT  ' if ok else 'WRONG  '}  {q['id']}  key={want}  agent={got}")
    print(f"\n{right}/{len(selected)} correct, {abstain} abstained")
    sys.exit(0 if right == len(selected) else 1)


if __name__ == "__main__":
    main()
