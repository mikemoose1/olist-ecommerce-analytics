"""Coverage: is everything the warehouse and the docs show described in ontology.yml?

Three checks, each a PASS/FAIL line (run from ontology/check.py, so `make ontology` and CI fail on a gap):
  tables   every table in the marts and metrics schemas is an entity table or listed in coverage_allowlist.yml with a
           written reason. A metric card that names a table as its model does not describe it (G7).
  columns  every column of those tables has a contract: an entity key, a relationship column, a `columns:` entry, the source
           of a term that carries values or counts, or an allowlist entry with a written reason. A bare `source:` pointer
           (and every metric source) is not a contract: nothing checks the column itself (G7).
  numbers  every number shown in ONTOLOGY.md (counts with commas, decimals, integers of 3+ digits) is a CHECKED value in
           ontology.yml (expected, nulls, rows, verified ...; a number inside a sentence does not count), or is in the
           allowlist with a reason
The allowlist cannot rot: an entry with no reason, or one that matches nothing, fails.

Why not the memo? Its numbers are analysis results, not definitions. recommendation/analyze.py already fails
`make verify` when a memo number is not produced by its own run, so a second check against ontology.yml
would only flag results (measured: 76 of 77 memo numbers).
"""
import fnmatch, os, re
import yaml

SCHEMAS = ("marts", "metrics")


def key_columns(entity):
    k = entity["key"]
    return k if isinstance(k, list) else [k]


def described(onto):
    """(tables, columns) the ontology describes, as schema.table and schema.table.column strings."""
    tables, cols = set(), set(onto.get("columns", {}))
    for e in onto["entities"].values():
        tables.add(e["table"])
        cols |= {f"{e['table']}.{k}" for k in key_columns(e)}
    for r in onto["relationships"]:
        cols.add(f"{onto['entities'][r['from']['entity']]['table']}.{r['from']['column']}")
    for card in onto["terms"].values():
        # a term's source column is only "described" when the term carries values or counts the check compares
        # to the warehouse. A bare pointer (and every metric source) proves nothing about the column itself.
        if any(k in card for k in ("values", "count", "counts")):
            cols.add(card["source"])
    return tables, cols


def load_allowlist(path):
    a = yaml.safe_load(open(path)) or {}
    return {k: a.get(k) or [] for k in ("tables", "columns", "numbers")}


def match(pattern, name):
    return fnmatch.fnmatchcase(name, pattern)


NUMBER = re.compile(r"(?<![\w.])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w])|(?<![\w.])-?\d+\.\d+(?![\w.])|(?<![\w.,-])\d{3,}(?![\w]|,\d)")


def shown_numbers(text):
    """Numbers a reader sees: dates, times and version strings are removed first."""
    text = re.sub(r"\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?", " ", text)
    text = re.sub(r"\d{4}-\d{2}(?!\d)", " ", text)
    text = re.sub(r"\d{2}:\d{2}:\d{2}", " ", text)
    text = re.sub(r"v?\d+\.\d+\.\d+", " ", text)
    text = re.sub(r"```mermaid.*?```", " ", text, flags=re.S)   # generated chart, checked by the diagram check
    return {m.group(0).replace(",", "") for m in NUMBER.finditer(text)}


def checked_numbers(onto):
    """Numbers ontology.yml holds as values the checks compare (expected, nulls, rows, verified ...).
    A number that appears only inside a sentence is not here: nothing proves it."""
    out = set()

    def walk(x):
        if isinstance(x, dict):
            [walk(v) for v in x.values()]
        elif isinstance(x, list):
            [walk(v) for v in x]
        elif isinstance(x, (int, float)) and not isinstance(x, bool):
            out.add(str(x))
            if float(x).is_integer():
                out.add(str(int(x)))
    walk(onto)
    return out


def check_coverage(con, onto, md_path, allowlist_path):
    allow = load_allowlist(allowlist_path)
    bad_allow = [f"{k}:{e.get('match') or e.get('value')}" for k in allow for e in allow[k]
                 if not str(e.get("reason", "")).strip() or not (e.get("match") or e.get("value"))]
    yield "coverage", "allowlist reasons", not bad_allow, \
        f"{sum(len(v) for v in allow.values())} exemptions, each with a reason" if not bad_allow else f"missing reason or match: {bad_allow}"

    want_tables, want_cols = described(onto)
    rows = con.execute(
        "select table_schema, table_name, column_name from information_schema.columns "
        f"where table_schema in {SCHEMAS} order by 1, 2, ordinal_position").fetchall()
    tables = sorted({f"{s}.{t}" for s, t, _ in rows})
    cols = [f"{s}.{t}.{c}" for s, t, c in rows]

    used = set()

    def free(names, kind, have):
        out = []
        for n in names:
            if n in have:
                continue
            hits = [e for e in allow[kind] if match(e["match"], n)]
            used.update(id(e) for e in hits)
            if not hits:
                out.append(n)
        return out

    miss_t, miss_c = free(tables, "tables", want_tables), free(cols, "columns", want_cols)
    yield "coverage", "tables", not miss_t, f"{len(tables)} tables; undescribed: {miss_t or 'none'}"
    yield "coverage", "columns", not miss_c, f"{len(cols)} columns; undescribed: {miss_c or 'none'}"

    doc = open(md_path).read()
    yml_nums = checked_numbers(onto)
    shown = shown_numbers(doc)
    miss_n = []
    for n in sorted(shown - yml_nums, key=float):
        hits = [e for e in allow["numbers"] if str(e["value"]) == n]
        used.update(id(e) for e in hits)
        if not hits:
            miss_n.append(n)
    yield "coverage", "numbers in ONTOLOGY.md", not miss_n, \
        f"{len(shown)} numbers shown; not a checked value in ontology.yml: {miss_n or 'none'}"

    stale = [f"{k}:{e.get('match') or e.get('value')}" for k in allow for e in allow[k] if id(e) not in used]
    yield "coverage", "allowlist is current", not stale, f"entries matching nothing: {stale or 'none'}"
