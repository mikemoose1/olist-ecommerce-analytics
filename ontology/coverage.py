"""Coverage: is everything the warehouse and the docs show described in ontology.yml?

Three checks, each a PASS/FAIL line (run from ontology/check.py, so `make ontology` and CI fail on a gap):
  tables   every table in the marts and metrics schemas is an entity table or listed in coverage_allowlist.yml with a
           written reason. A metric card that names a table as its model does not describe it (G7).
  columns  every column of those tables has a contract: an entity key, a relationship column, a `columns:` entry, the source
           of a term that carries values or counts, or an allowlist entry with a written reason. A bare `source:` pointer
           (and every metric source) is not a contract: nothing checks the column itself (G7).
  numbers  every number shown in ONTOLOGY.md (counts with commas, decimals, integers of 3+ digits) is followed by an
           invisible marker <!--n:entities.customer.rows--> naming the ontology.yml value it states. The check follows the
           path and fails if the value there is a different number (so swapping 96,096 for 94,931 fails), if the path
           leads nowhere, or if a marker follows no number. Allowlist entry with a reason = no marker needed.
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


def _blank(m):
    return " " * len(m.group(0))


def mask(text):
    """Blank out what is not a number a reader sees (dates, times, versions, the generated chart, the markers
    themselves), keeping every character position so a match can be looked up in the original text."""
    for pat, flags in ((r"<!--n:[^>]*-->", 0), (r"\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?", 0), (r"\d{4}-\d{2}(?!\d)", 0),
                       (r"\d{2}:\d{2}:\d{2}", 0), (r"v?\d+\.\d+\.\d+", 0), (r"```mermaid.*?```", re.S)):
        text = re.sub(pat, _blank, text, flags=flags)
    return text


def shown_numbers(text):
    """Numbers a reader sees."""
    return {m.group(0).replace(",", "") for m in NUMBER.finditer(mask(text))}


MARKER = re.compile(r"<!--n:([\w.]+)-->")


def resolve(onto, path):
    """Follow a dotted path through ontology.yml (dict keys; list items by index). None when it does not lead to a number."""
    node = onto
    for seg in path.split("."):
        if isinstance(node, dict) and seg in node:
            node = node[seg]
        elif isinstance(node, dict) and seg.isdigit() and int(seg) in node:
            node = node[int(seg)]
        elif isinstance(node, list) and seg.isdigit() and int(seg) < len(node):
            node = node[int(seg)]
        else:
            return None
    return node if isinstance(node, (int, float)) and not isinstance(node, bool) else None


def number_bindings(text, onto):
    """Every number shown in the prose must be followed by <!--n:path--> naming the ontology.yml value it states.
    Returns (bound, problems). A swapped number fails because the value at its path is a different number; a marker that
    follows no number, or points nowhere, fails too."""
    masked, bound, problems, claimed = mask(text), 0, [], set()
    for m in NUMBER.finditer(masked):
        shown = m.group(0).replace(",", "")
        mk = MARKER.match(text, m.end())
        if not mk:
            problems.append(f"{shown}: no <!--n:path--> marker")
            continue
        claimed.add(mk.start())
        val = resolve(onto, mk.group(1))
        if val is None:
            problems.append(f"{shown}: marker {mk.group(1)} is not a number in ontology.yml")
        elif float(val) != float(shown):
            problems.append(f"{shown}: marker {mk.group(1)} holds {val}")
        else:
            bound += 1
    problems += [f"marker {k.group(1)} follows no number" for k in MARKER.finditer(text) if k.start() not in claimed]
    return bound, problems


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
    bound, problems = number_bindings(doc, onto)
    for n in list(problems):   # an allowlisted number needs no marker
        shown = n.split(":")[0]
        hits = [e for e in allow["numbers"] if str(e["value"]) == shown] if ": no <!--n:path--> marker" in n else []
        used.update(id(e) for e in hits)
        if hits:
            problems.remove(n)
    yield "coverage", "numbers in ONTOLOGY.md", not problems, \
        f"{bound} numbers each bound to the ontology.yml value they state; problems: {problems or 'none'}"

    stale = [f"{k}:{e.get('match') or e.get('value')}" for k in allow for e in allow[k] if id(e) not in used]
    yield "coverage", "allowlist is current", not stale, f"entries matching nothing: {stale or 'none'}"
