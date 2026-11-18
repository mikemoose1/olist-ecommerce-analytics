"""Coverage: is everything the warehouse and the docs show described in ontology.yml?

Three checks, each a PASS/FAIL line (run from ontology/check.py, so `make ontology` and CI fail on a gap):
  tables   every table in the marts and metrics schemas is an entity table or listed in coverage_allowlist.yml with a
           written reason. A metric card that names a table as its model does not describe it (G7).
  columns  every column of those tables has a contract: an entity key, a relationship column, a `columns:` entry, the source
           of a term that carries values or counts, or an allowlist entry with a written reason. A bare `source:` pointer
           (and every metric source) is not a contract: nothing checks the column itself (G7).
  numbers  every number shown in ONTOLOGY.md (any integer, decimal or comma-grouped count, a date, a month, a timestamp or
           a clock time; ordered-list ordinals and the generated chart excepted) is followed by an invisible marker
           <!--n:entities.customer.rows--> naming the ontology.yml value it states. The check follows the path and fails
           if the value there is different (so swapping 96,096 for 94,931 fails), if the path leads nowhere, or if a marker
           follows no number. The marker must also belong where it stands: its table row, or in prose its sentence, has to
           name the marker's owner (the entity, term or metric key or a `doc_anchor` on that card, a relationship's
           entities, a column's name, or a fact's or stage rule's `doc_anchor`), so swapping both the number and the
           marker (96,096 customer -> 99,441 order) fails too. Limit: two owners named in one row or sentence can
           still be swapped with each other.
           A number with no ontology.yml value (a design constant such as "90 days", a worked example) needs an
           allowlist entry with a `context`: the exact phrase it sits in, and a reason. Editing the number breaks the
           phrase, so the edit fails; a bare value with no context is not accepted.
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


NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+){2,}(?![\w.])"                                         # dotted triple (a version)
                    r"|(?<![\w.:-])\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}(?::\d{2})?)?(?![\w:-])"      # date, timestamp
                    r"|(?<![\w.:-])\d{4}-\d{2}(?![\w-])"                                       # month
                    r"|(?<![\w.:])\d{1,2}:\d{2}(?::\d{2})?(?![\w:])"                             # clock time
                    r"|(?<![\w.])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w])"                        # 96,096
                    r"|(?<![\w.])-?\d+\.\d+(?![\w.])"                                           # 6.87
                    r"|(?<![\w.,:-])\d+(?![\w:]|,\d|\.\d|-\d)")                                # any integer


def _blank(m):
    return " " * len(m.group(0))


def mask(text):
    """Blank out what is not a number a reader sees (dates, times, versions, the generated chart, the markers
    themselves), keeping every character position so a match can be looked up in the original text."""
    for pat, flags in ((r"<!--n:[^>]*-->", 0), (r"```mermaid.*?```", re.S)):
        text = re.sub(pat, _blank, text, flags=flags)
    # ordered-list ordinals, but only a real list: 1, 2, 3 ... in order. A lone "9. orders ..." is a number
    out, expect = [], 1
    for line in text.split("\n"):
        m = re.match(r"([ \t]*)(\d+)\.(?= )", line)
        if m and int(m.group(2)) == expect:
            line = m.group(1) + " " * (len(m.group(2)) + 1) + line[m.end():]
            expect += 1
        elif line.strip() and not line.startswith((" ", "\t")):
            expect = 1
        out.append(line)
    return "\n".join(out)


VULGAR = "\u00bc\u00bd\u00be\u2150-\u215e\u00b2\u00b3\u00b9\u2070-\u2079\u2080-\u2089"   # fractions and super/subscript digits


def names_in(onto):
    """every key in ontology.yml and every word with letters and digits in its strings: the identifiers a glued digit may belong
    to (repeat_rate_90d, metric_repeat_rate_90d_people, decision C1)"""
    out, stack = set(), [onto]
    while stack:
        n = stack.pop()
        if isinstance(n, dict):
            out |= {str(k) for k in n}
            stack += list(n.values())
        elif isinstance(n, list):
            stack += n
        elif isinstance(n, str):
            out |= {w for w in re.findall(r"\w+", n) if re.search(r"\d", w) and re.search(r"[A-Za-z]", w)}
    return out


def stray_digits(masked, names=frozenset()):
    """digit runs no NUMBER token covers (a range '1-3', '..5', a glued unit '30d', an ordinal '2nd', 'count:9', '3,9'),
    digits glued after letters ('top5', 'p95', 'x_7') unless the whole word is a name ontology.yml uses (repeat_rate_90d,
    decision C1), and fraction or super/subscript digits ('\u00bd', '\u00b2')."""
    spans = [(m.start(), m.end()) for m in NUMBER.finditer(masked)]
    out = []
    for m in re.finditer(rf"\d+|[{VULGAR}]", masked):
        if any(a <= m.start() < b for a, b in spans):
            continue
        a, b = m.start(), m.end()
        while a > 0 and (masked[a - 1].isalnum() or masked[a - 1] == "_"):
            a -= 1
        while b < len(masked) and (masked[b].isalnum() or masked[b] == "_"):
            b += 1
        if a < m.start() and masked[a:b] in names:
            continue
        out.append(m)
    return out


def shown_numbers(text):
    """Numbers a reader sees."""
    return {m.group(0).replace(",", "") for m in NUMBER.finditer(mask(text))}


MARKER = re.compile(r"<!--n:([\w.]+)-->")


def resolve(onto, path):
    """Follow a dotted path through ontology.yml (dict keys; list items by index). None when it does not lead to a number."""
    node, segs = onto, path.split(".")
    while segs:
        seg = segs.pop(0)
        joined = next((".".join([seg] + segs[:k]) for k in range(len(segs), 0, -1)
                       if isinstance(node, dict) and ".".join([seg] + segs[:k]) in node), None)
        if joined:                                    # a dotted key such as columns: marts.fct_orders.amount_paid
            segs = segs[joined.count("."):]
            node = node[joined]
        elif isinstance(node, dict) and seg in node:
            node = node[seg]
        elif isinstance(node, dict) and seg.isdigit() and int(seg) in node:
            node = node[int(seg)]
        elif isinstance(node, list) and seg.isdigit() and int(seg) < len(node):
            node = node[int(seg)]
        else:
            return None
    if isinstance(node, bool):
        return None
    return node if isinstance(node, (int, float, str)) else None


def same_value(val, shown):
    if isinstance(val, str):
        return val.strip() == shown
    try:
        return float(val) == float(shown)
    except ValueError:
        return False


def norm_words(text):
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()).strip() + " "


def anchors(onto, path):
    """the names the line holding a marker must mention, so a marker cannot be moved to a number it does not describe"""
    seg = path.split(".")
    extra = lambda card: ([card["doc_anchor"]] if isinstance(card.get("doc_anchor"), str) else list(card.get("doc_anchor") or []))
    try:
        if seg[0] in ("entities", "terms", "metrics"):
            return [seg[1]] + extra(onto[seg[0]][seg[1]])
        if seg[0] == "relationships":
            r = onto["relationships"][int(seg[1])]
            return extra(r) or [r["from"]["entity"], r["to"] if isinstance(r["to"], str) else r["to"]["entity"]]
        if seg[0] == "columns":
            rest = ".".join(seg[1:])
            return [next(k for k in onto["columns"] if rest.startswith(k + ".")).split(".")[-1]]
        if seg[0] in ("facts", "stage_rules"):
            item = onto[seg[0]][int(seg[1])]
            return extra(item) or [item.get("claim") or item.get("rule")]
    except (KeyError, IndexError, ValueError, TypeError):
        pass
    return []


def context_of(text, pos):
    """where a marker's owner must be named: the whole row of a table, otherwise the sentence holding the number"""
    a, b = text.rfind("\n", 0, pos) + 1, text.find("\n", pos)
    line = text[a:b if b >= 0 else len(text)]
    if line.lstrip().startswith("|"):
        return MARKER.sub("", line)
    i = pos - a
    starts = [0] + [m.end() for m in re.finditer(r"[.!?](?=\s)", line) if m.end() <= i]
    end = re.search(r"[.!?](?=\s|$)", line[i:])
    return MARKER.sub("", line[starts[-1]:i + (end.end() if end else len(line) - i)])


def anchored(line, names):
    words = norm_words(line)
    for n in names:
        w = norm_words(n).strip()
        if w and re.search(rf" {re.escape(w)}(?:s|es)? ", words):
            return True
    return False


def number_bindings(text, onto):
    """Every number shown in the prose must be followed by <!--n:path--> naming the ontology.yml value it states.
    Returns (bound, problems). A swapped number fails because the value at its path is a different number; a marker that
    follows no number, or points nowhere, fails too."""
    masked, bound, problems, claimed = mask(text), 0, [], set()
    for m in NUMBER.finditer(masked):
        shown = m.group(0).replace(",", "")
        mk = MARKER.match(text, m.end())
        if not mk:
            problems.append((m.group(0), m.start(), True))
            continue
        claimed.add(mk.start())
        val = resolve(onto, mk.group(1))
        line = context_of(text, m.start())
        if val is None:
            problems.append(f"{shown}: marker {mk.group(1)} is not a value in ontology.yml")
        elif not same_value(val, shown):
            problems.append(f"{shown}: marker {mk.group(1)} holds {val}")
        elif not anchored(line, anchors(onto, mk.group(1))):
            problems.append(f"{shown}: marker {mk.group(1)} belongs to {anchors(onto, mk.group(1))}, which its row or sentence does not name")
        else:
            bound += 1
    problems += [(m.group(0), m.start(), True) for m in stray_digits(masked, names_in(onto))]     # no escape from the number rule
    problems += [f"marker {k.group(1)} follows no number" for k in MARKER.finditer(text) if k.start() not in claimed]
    return bound, [p if isinstance(p, tuple) else (p, -1, False) for p in problems]


def exempt(text, problems, allow, used):
    """drop 'no marker' problems for numbers that sit inside an allowlisted context phrase; returns the bad entries"""
    masked = mask(text)
    spans = []
    bad = []
    for e in allow:
        ctx = str(e.get("context") or "")
        if not ctx or str(e.get("value")) not in ctx:
            bad.append(f"numbers:{e.get('value')} needs a context phrase that contains it")
            continue
        for m in re.finditer(re.escape(ctx), text):
            spans.append((m.start(), m.end(), str(e["value"]), e))
    keep = []
    for p in problems:
        if not p[2]:
            keep.append(p)
            continue
        hit = [e for a, b, v, e in spans if a <= p[1] and p[1] + len(p[0]) <= b and v == p[0]]
        if hit:
            used.update(id(e) for e in hit)
        else:
            keep.append(p)
    return keep, bad


def check_coverage(con, onto, md_path, allowlist_path):
    allow = load_allowlist(allowlist_path)
    bad_allow = [f"{k}:{e.get('match') or e.get('value')}" for k in allow for e in allow[k]
                 if not str(e.get("reason", "")).strip() or (e.get("match") is None and e.get("value") is None)]
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
    problems, bad_ctx = exempt(doc, problems, allow["numbers"], used)      # an allowlisted number in its exact phrase needs no marker
    problems = [f"{p[0]}: no <!--n:path--> marker (line {doc.count(chr(10), 0, p[1]) + 1})" if p[2] else p[0] for p in problems] + bad_ctx
    yield "coverage", "numbers in ONTOLOGY.md", not problems, \
        f"{bound} numbers each bound to the ontology.yml value they state; problems: {problems or 'none'}"

    stale = [f"{k}:{e.get('match') if e.get('match') is not None else e.get('value')}" for k in allow for e in allow[k] if id(e) not in used]
    yield "coverage", "allowlist is current", not stale, f"entries matching nothing: {stale or 'none'}"
