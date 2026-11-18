#!/usr/bin/env python3
"""Prove ontology/ontology.yml against the built warehouse.

Checks, each a PASS/FAIL line:
  entity        table exists, key is unique and never null, row count equals the card
  relationship  no unexpected nulls or orphans; children per parent inside [min, max]
  column        every card's source (schema.table.column) exists
  term_count    every count printed on a term card (values, count, counts) equals the warehouse
  column_fact   each documented column has the stated type and null count, and its row rules hold on every row
  fact          each cross-table fact's query returns the stated number
  stage_rule    each order-stage rule's count equals the documented count
  model_link    each rule's `model:` is `not_modeled` or names an invariant that exists in OrderLifecycle.tla and .cfg with the result
                report.md records, and the Model column of ONTOLOGY.md says exactly that (TLC itself is run by hand, not in CI)
  metric        each verified card equals the metric table AND MetricFlow (`mf query`)
  diagram       the Mermaid diagram in ONTOLOGY.md equals the one generated from the YAML
  coverage      every marts and metrics table and column, and every number shown in ONTOLOGY.md, is described in
                ontology.yml or exempted with a written reason in coverage_allowlist.yml (see coverage.py)

Usage:  python ontology/check.py [--skip-semantic]   (after `make build`; OLIST_DB_PATH picks the warehouse)
        python ontology/check.py --mermaid           (print the entity diagram)
Output: evidence/ontology_report.md and .json; exit 1 on any FAIL.
"""
import csv, json, os, re, subprocess, sys, tempfile
import duckdb, yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coverage

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ONTOLOGY_YML / ONTOLOGY_MD / COVERAGE_ALLOWLIST point the check at edited copies (mutation proofs only)
YML = os.environ.get("ONTOLOGY_YML", os.path.join(ROOT, "ontology", "ontology.yml"))
MD = os.environ.get("ONTOLOGY_MD", os.path.join(ROOT, "ontology", "ONTOLOGY.md"))
ALLOW = os.environ.get("COVERAGE_ALLOWLIST", os.path.join(ROOT, "ontology", "coverage_allowlist.yml"))
ONTO = yaml.safe_load(open(YML))
DB = os.environ.get("OLIST_DB_PATH", os.path.join(ROOT, "olist.duckdb"))
MF = os.path.join(os.path.dirname(sys.executable), "mf")
E = ONTO["entities"]


def keys(entity):
    k = E[entity]["key"]
    return k if isinstance(k, list) else [k]


def mermaid():
    ends = {0: "o", 1: "|"}
    lines = ["erDiagram"]
    for name, e in E.items():
        lines.append(f"    {name.upper()} {{")
        lines += [f"        string {k} PK" for k in keys(name)]
        lines.append("    }")
    for r in ONTO["relationships"]:
        lo, hi = r["children_per_parent"]
        child = ("|o" if hi == 1 else "o{") if lo == 0 else ("||" if hi == 1 else "|{")
        lines.append(f'    {r["to"].upper()} ||--{child} {r["from"]["entity"].upper()} : "{r["name"]}"')
    return "\n".join(lines)


def check_entities(con):
    for name, e in E.items():
        k = ", ".join(keys(name))
        nulls = " or ".join(f"{c} is null" for c in keys(name))
        n, d, nn = con.execute(f"select count(*), (select count(*) from (select distinct {k} from {e['table']})), "
                               f"count(*) filter (where {nulls}) from {e['table']}").fetchone()
        yield "entity", name, n == e["rows"] and d == n and nn == 0, \
            f"rows={n} (card {e['rows']}), distinct keys={d}, null keys={nn}"


def check_relationships(con):
    for r in ONTO["relationships"]:
        child, col = E[r["from"]["entity"]], r["from"]["column"]
        parent_key = keys(r["to"])[0]
        parent = E[r["to"]]["table"]
        where = f"where {r['from']['where']}" if r["from"].get("where") else ""
        ch = f"(select * from {child['table']} {where})"
        nulls, orphans = con.execute(
            f"select count(*) filter (where c.{col} is null), "
            f"count(*) filter (where c.{col} is not null and p.{parent_key} is null) "
            f"from {ch} c left join {parent} p on p.{parent_key} = c.{col}").fetchone()
        lo, hi = con.execute(
            f"select min(n), max(n) from (select p.{parent_key}, count(c.{col}) n from {parent} p "
            f"left join {ch} c on c.{col} = p.{parent_key} group by 1)").fetchone()
        want_lo, want_hi = r["children_per_parent"]
        ok = (nulls == r.get("nulls", 0) and orphans == r.get("orphans", 0) and lo >= want_lo
              and (want_hi is None or hi <= want_hi))
        yield "relationship", r["name"], ok, (f"nulls={nulls} (card {r.get('nulls', 0)}), orphans={orphans} "
                                              f"(card {r.get('orphans', 0)}), children per parent {lo}..{hi} "
                                              f"(card {want_lo}..{want_hi if want_hi is not None else 'many'})")


def check_columns(con):
    cols = {f"{s}.{t}.{c}" for s, t, c in con.execute(
        "select table_schema, table_name, column_name from information_schema.columns").fetchall()}
    for kind in ("terms", "metrics"):
        for name, card in ONTO[kind].items():
            yield "column", f"{kind}.{name}", card["source"] in cols, card["source"]


def check_term_counts(con):
    for name, card in ONTO["terms"].items():
        schema, table, col = card["source"].split(".")
        if "values" in card:
            got = {str(k): v for k, v in sorted(con.execute(f"select {col}, count(*) from {schema}.{table} group by 1").fetchall(), key=lambda r: str(r[0]))}
            want = {str(k): v for k, v in card["values"].items()}
            yield "term_count", name, got == want, f"{got}"
        for c in ([card["count"]] if "count" in card else []):
            n = con.execute(f"select count(*) from {schema}.{table} where {c['where']}").fetchone()[0]
            yield "term_count", name, n == c["expected"], f"{c['where']}: {n} (card {c['expected']})"
        if "counts" in card:
            got = [(c, con.execute(f"select count(*) from {schema}.{table} where {c['where']}").fetchone()[0]) for c in card["counts"]]
            yield "term_count", name, all(n == c["expected"] for c, n in got), \
                "; ".join(f"{c['where']}: {n} (card {c['expected']})" for c, n in got)


def check_column_facts(con):
    types = {f"{s}.{t}.{c}": d for s, t, c, d in con.execute(
        "select table_schema, table_name, column_name, data_type from information_schema.columns").fetchall()}
    for ref, f in ONTO["columns"].items():
        schema, table, col = ref.split(".")
        tbl = f"{schema}.{table}"
        parts, ok = [f"type {types.get(ref)} (card {f['type']})"], types.get(ref) == f["type"]
        nulls = con.execute(f"select count(*) from {tbl} where {col} is null").fetchone()[0]
        ok &= nulls == f["nulls"]
        parts.append(f"nulls {nulls} (card {f['nulls']})")
        if "null_when" in f:
            bad = con.execute(f"select count(*) from {tbl} where ({col} is null) is distinct from ({f['null_when']})").fetchone()[0]
            ok &= bad == 0
            parts.append(f"null exactly when [{f['null_when']}]: {bad} violations")
        for rule in f.get("holds", []):
            bad = con.execute(f"select count(*) from {tbl} where not coalesce({rule}, false)").fetchone()[0]
            ok &= bad == 0
            parts.append(f"holds [{rule}]: {bad} violations")
        yield "column_fact", ref, ok, "; ".join(parts)


def check_facts(con):
    for f in ONTO["facts"]:
        n = con.execute(f["sql"]).fetchone()[0]
        yield "fact", f["claim"], n == f["expected"], f"count={n} (card {f['expected']})"


def check_stage_rules(con):
    for s in ONTO["stage_rules"]:
        n = con.execute(s["sql"]).fetchone()[0]
        yield "stage_rule", s["rule"], n == s["expected"], f"count={n} (card {s['expected']})"


LIFECYCLE = os.environ.get("ONTOLOGY_LIFECYCLE", os.path.join(ROOT, "ontology", "order_lifecycle"))


def check_model_links():
    """The Model column in ONTOLOGY.md may only claim what a named TLA+ invariant checks (S6)."""
    read = lambda f: open(os.path.join(LIFECYCLE, f)).read()
    tla, cfg, report = read("OrderLifecycle.tla"), read("OrderLifecycle.cfg"), read("report.md")
    defined = set(re.findall(r"^(\w+) ==", tla, re.M))
    in_cfg = set(re.findall(r"^INVARIANT (\w+)", cfg, re.M))
    breaks = set(re.findall(r"^## (\w+) breaks", report, re.M))
    holds = set(re.split(r"\s*,\s*", (re.search(r"## Rules that hold\n(.*)", report) or [0, ""])[1].strip()))
    cells = {}
    for line in open(MD).read().splitlines():
        parts = [p.strip() for p in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(parts) > 2:
            cells[parts[0]] = parts[1]
    claimed = []
    for s in ONTO["stage_rules"]:
        m, name = s.get("model"), s["rule"]
        if m == "not_modeled":
            want, why, ok = "not modeled", "no invariant in the model", True
        elif isinstance(m, dict) and m.get("result") in ("holds", "breaks"):
            inv, res = m.get("invariant"), m["result"]
            claimed.append(inv)
            seen = inv in breaks if res == "breaks" else inv in holds and inv not in breaks
            ok = inv in defined and inv in in_cfg and seen
            want = "**breaks**" if res == "breaks" else "holds"
            why = f"invariant {inv}: defined={inv in defined} in cfg={inv in in_cfg} report says {res}={seen}"
        else:
            want, why, ok = "?", f"model must be `not_modeled` or {{invariant, result: holds|breaks}}, got {m!r}", False
        shown = cells.get(name)
        yield "model_link", name, ok and shown == want, f"{why}; ONTOLOGY.md Model column shows {shown!r}, card says {want!r}"
    unclaimed = sorted(in_cfg - set(claimed))
    yield "model_link", "every invariant TLC checks backs a rule", not unclaimed, f"invariants in the cfg that no rule claims: {unclaimed or 'none'}"


def mf_rows(names, group_by=None):
    out = os.path.join(tempfile.mkdtemp(), "mf.csv")
    env = dict(os.environ, DBT_PROFILES_DIR=ROOT, OLIST_DB_PATH=DB)
    cmd = [MF, "query", "--metrics", ",".join(names), "--decimals", "6", "--csv", out]
    p = subprocess.run(cmd + (["--group-by", group_by] if group_by else []), cwd=ROOT, env=env, capture_output=True, text=True)
    if p.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(p.stdout[-2000:] + p.stderr[-2000:])
    return list(csv.DictReader(open(out)))


def mf_values(names):
    return {k: float(v) for k, v in mf_rows(names)[0].items()}


def mf_monthly_late():
    return {r["metric_time__month"][:7]: (round(float(r["late_orders"])), round(float(r["judged_orders"])))
            for r in mf_rows(["late_orders", "judged_orders"], "metric_time__month")}


CARDS = {n: m for n, m in ONTO["metrics"].items() if "verified" in m}


def check_metrics(con, mf):
    table = {r[0]: r[1:] for r in con.execute(
        "select metric_name, numerator, denominator, value_pct from metrics.metrics_headline").fetchall()}
    for name, m in CARDS.items():
        v = m["verified"]
        num, den, val = table[name]
        ok = den == v["denominator"] and float(val) == v["value_pct"] and (
            "numerator" not in v or float(num) == v["numerator"])
        detail = f"table {num}/{den}={val} (card {v.get('numerator', '-')}/{v['denominator']}={v['value_pct']})"
        if m.get("semantic_metric") and mf:
            got = mf[m["semantic_metric"]]
            shown = round(got * 100, 2) if name != "review_score" else round(got, 3)
            n, d = (mf[x] for x in m["semantic_parts"])
            ok = ok and shown == v["value_pct"] and n == v["numerator"] and d == v["denominator"]
            detail += f"; MetricFlow {n:.0f}/{d:.0f}={got:.6f} -> {shown}"
        yield "metric", name, ok, detail
    if mf:
        table_m = {r[0]: (r[1], r[2]) for r in con.execute(
            "select year_month, numerator, denominator from metrics.metric_late_rate_monthly").fetchall()}
        same = sum(mf["monthly"].get(m) == v for m, v in table_m.items())
        yield "metric", "late_rate_monthly", same == len(table_m) == len(mf["monthly"]), \
            f"MetricFlow by month vs table: {same}/{len(table_m)} months identical (numerator and denominator)"


def check_diagram():
    doc = open(MD).read()
    yield "diagram", "ONTOLOGY.md entity diagram", mermaid() in doc, "regenerate with: python ontology/check.py --mermaid"


def main():
    if "--mermaid" in sys.argv:
        print(mermaid()); return
    mf = {}
    if "--skip-semantic" not in sys.argv:  # MetricFlow opens the file itself, so query it before we hold a connection
        mf = mf_values([x for m in CARDS.values() if m.get("semantic_metric")
                        for x in [m["semantic_metric"], *m["semantic_parts"]]])
        mf["monthly"] = mf_monthly_late()
    con = duckdb.connect(DB, read_only=True)
    results = []
    for gen in (check_entities(con), check_relationships(con), check_columns(con), check_term_counts(con), check_column_facts(con), check_facts(con), check_stage_rules(con), check_model_links(),
                coverage.check_coverage(con, ONTO, MD, ALLOW),
                check_metrics(con, mf), check_diagram()):
        for kind, name, ok, detail in gen:
            results.append({"kind": kind, "name": name, "ok": bool(ok), "detail": detail})
            print(f"{'PASS' if ok else 'FAIL'}  {kind:12s} {name}: {detail}", flush=True)
    bad = [r for r in results if not r["ok"]]
    if not os.environ.get("ONTOLOGY_NO_REPORT"):
        os.makedirs(os.path.join(ROOT, "evidence"), exist_ok=True)
        json.dump(results, open(os.path.join(ROOT, "evidence", "ontology_report.json"), "w"), indent=1)
        with open(os.path.join(ROOT, "evidence", "ontology_report.md"), "w") as f:
            f.write("# Ontology check: every claim in ontology/ontology.yml against the warehouse\n\n")
            f.write(f"{len(results) - len(bad)}/{len(results)} PASS\n\n| Kind | Claim | Result | Detail |\n|---|---|---|---|\n")
            for r in results:
                f.write(f"| {r['kind']} | {r['name']} | {'PASS' if r['ok'] else '**FAIL**'} | {r['detail']} |\n")
    print(f"\n{len(results) - len(bad)}/{len(results)} ontology claims PASS")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
