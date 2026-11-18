"""Compute the KPI tree in story/kpi_tree.yml from the warehouse and check that it adds up.

  python story/kpi_tree.py            compute, check, write story/data/kpi_tree.json and story/kpi_tree.mmd
  python story/kpi_tree.py --check    compute and check only; also fail if the committed outputs are stale

Checks (exit 1 if any fails):
  sum      every breakdown's rows add up exactly to its parent's value
  product  a parent equals the product of its product children (relative tol 1e-6)
  fact     a node with fact_check equals that key in evidence/recommendation_report.json (to 0.01)
  claims   every claim id names an entry in ontology/ontology.yml
  labels   the comment keyword rule keeps precision >= 0.9 on hand-labelled late-order comments
           (story/comment_labels.csv; "holdout" rows were labelled after the rule was frozen)
  shape    every parent exists; association / not_answerable nodes carry the right marks
"""
import json, math, re, sys
from pathlib import Path

import duckdb, yaml

ROOT = Path(__file__).resolve().parents[1]
TREE = ROOT / "story" / "kpi_tree.yml"
# Portuguese keywords for "did not arrive / late / deadline", matched on lower-cased, accent-stripped text.
NOT_ARRIVED = r"nao (recebi|chegou|foi entregue|entreg|veio)|ainda nao|atras|demor|prazo|aguard|esperand|nada do produto|retornou"


def dig(d, path):
    for k in path.split("."):
        d = d[k]
    return d


def compute(tree, db_path=ROOT / "olist.duckdb", report=None):
    report = report or json.loads((ROOT / "evidence" / "recommendation_report.json").read_text())
    con = duckdb.connect(str(db_path), read_only=True)
    con.execute(f"create temp view judged as {tree['judged_sql']}")
    out = {}
    for n in tree["nodes"]:
        v = {"id": n["id"]}
        if "sql" in n:
            v["value"] = round(float(con.execute(n["sql"].replace("{{NOT_ARRIVED}}", NOT_ARRIVED)).fetchone()[0]), 9)
        elif "rows" in n:
            v["rows"] = [[str(a), float(b)] for a, b in con.execute(n["rows"]).fetchall()]
            v["value"] = sum(b for _, b in v["rows"])
        elif "fact" in n:
            v["value"] = float(dig(report, n["fact"]))
        if "ci" in n:
            c = [dig(report, p) for p in n["ci"]]
            v["ci"] = [float(x) for x in (c[0] if len(c) == 1 else c)]
        if "fact_check" in n:
            v["fact_check"] = float(dig(report, n["fact_check"]))
        out[n["id"]] = v
    return out


def label_eval(db_path=ROOT / "olist.duckdb", rule=None):
    """Precision and recall of the keyword rule on story/comment_labels.csv, per labelled set."""
    import csv
    rule = rule or NOT_ARRIVED
    rows = list(csv.DictReader((ROOT / "story" / "comment_labels.csv").open()))
    con = duckdb.connect(str(db_path), read_only=True)
    out = {}
    for st in sorted({r["set"] for r in rows}):
        tp = fp = fn = tn = 0
        for r in (r for r in rows if r["set"] == st):
            txt = con.execute("select review_comment_message from marts.fct_reviews where order_id = ? and is_chosen_for_order",
                              [r["order_id"]]).fetchone()[0]
            pred = bool(re.search(rule, strip(txt)))
            y = r["about_delay_or_non_arrival"] == "1"
            tp += pred and y; fp += pred and not y; fn += (not pred) and y; tn += (not pred) and not y
        out[st] = {"n": tp + fp + fn + tn, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                   "precision": tp / (tp + fp) if tp + fp else 0.0, "recall": tp / (tp + fn) if tp + fn else 0.0}
    return out


def strip(t):
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFKD", t.lower()) if not unicodedata.combining(ch))


def check(tree, vals, ontology=None):
    ontology = ontology or yaml.safe_load((ROOT / "ontology" / "ontology.yml").read_text())
    nodes = {n["id"]: n for n in tree["nodes"]}
    res = []
    for n in tree["nodes"]:
        p = n.get("parent")
        if p is not None and p not in nodes:
            res.append(("shape", n["id"], False, f"parent {p} missing"))
        e = n.get("edge")
        if e == "not_answerable":
            res.append(("shape", n["id"], n.get("answerable") == "no" and bool(n.get("reason")), "not_answerable needs answerable: no and a reason"))
        if e == "association" or n.get("association"):
            res.append(("shape", n["id"], str(n.get("answerable", "")).startswith(("association", "yes")), "association node marked"))
        for c in n.get("claims", []):
            sec, _, key = c.partition(".")
            ok = sec in ontology and key in (ontology[sec] or {})
            res.append(("claims", n["id"], ok, f"{c} {'found' if ok else 'NOT in ontology'}"))
        if "fact_check" in vals[n["id"]]:
            a, b = vals[n["id"]]["value"], vals[n["id"]]["fact_check"]
            res.append(("fact", n["id"], abs(a - b) <= 0.01, f"{a:.2f} vs report {b:.2f}"))
    for pid, pn in nodes.items():
        kids = [n for n in tree["nodes"] if n.get("parent") == pid]
        for k in [k for k in kids if k.get("edge") == "sum"]:
            a, b = vals[k["id"]]["value"], vals[pid]["value"]
            res.append(("sum", k["id"], a == b, f"rows sum {a:.2f} vs parent {pid} {b:.2f}"))
        prod = [k for k in kids if k.get("edge") == "product"]
        if prod:
            x = math.prod(vals[k["id"]]["value"] for k in prod)
            b = vals[pid]["value"]
            res.append(("product", pid, abs(x - b) <= 1e-6 * max(1, abs(b)),
                        f"{' x '.join(k['id'] for k in prod)} = {x:.4f} vs {pid} {b:.4f}"))
    if "labels" in vals:
        for st, e in vals["labels"].items():
            res.append(("labels", st, e["precision"] >= 0.9, f"precision {e['precision']:.2f} recall {e['recall']:.2f} on {e['n']} labelled comments"))
    return res


def fmt(n, v):
    if "value" not in v:
        return ""
    x, u = v["value"], n.get("unit", "")
    if u.startswith("share"):
        s = f"{x:.1%}" if abs(x) < 1 else f"{x:.3f}"
    elif u.startswith("R$"):
        s = f"R$ {x/1e6:.2f} M" if abs(x) >= 1e5 else f"R$ {x:,.0f}"
    elif u == "stars":
        s = f"{x:+.2f} stars"
    else:
        s = f"{x:,.0f}"
    if "ci" in v:
        lo, hi = v["ci"]
        f = (lambda y: f"{y:.1%}") if u.startswith("share") else (lambda y: f"{y:,.2f}") if u == "stars" else (lambda y: f"{y:,.0f}")
        s += f" [{f(lo)} to {f(hi)}]"
    return s


def mermaid(tree, vals):
    L = ["flowchart TD"]
    for n in tree["nodes"]:
        v = vals[n["id"]]
        txt = n["label"] + (f"<br/>{fmt(n, v)}" if fmt(n, v) else "")
        if "rows" in v:
            top = sorted(v["rows"], key=lambda r: -r[1])[:3]
            txt += "<br/>top: " + ", ".join(f"{a if len(a) <= 26 else a[:8]} {b:,.0f}" for a, b in top) + f" (of {len(v['rows'])})"
        if n.get("edge") == "not_answerable":
            txt += "<br/><i>not answerable</i>"
        L.append(f'  {n["id"]}["{txt}"]')
    for n in tree["nodes"]:
        p, e = n.get("parent"), n.get("edge")
        if not p:
            continue
        if e == "product" and n.get("association"):
            L.append(f'  {p} -.->|"= x, association only"| {n["id"]}')
        elif e == "association":
            L.append(f'  {p} -.->|association only| {n["id"]}')
        elif e == "not_answerable":
            L.append(f'  {p} -.-x|no data| {n["id"]}')
        elif e == "sum":
            L.append(f'  {p} -->|= sum of rows| {n["id"]}')
        elif e == "product":
            L.append(f'  {p} -->|"= x"| {n["id"]}')
        else:
            L.append(f'  {p} -->|part of| {n["id"]}')
    L.append("  classDef na fill:#eee,stroke:#999,color:#777,stroke-dasharray:4 3")
    L.append("  classDef assoc stroke-dasharray:4 3")
    na = [n["id"] for n in tree["nodes"] if n.get("edge") == "not_answerable"]
    asc = [n["id"] for n in tree["nodes"] if n.get("edge") == "association" or n.get("association")]
    if na: L.append(f"  class {','.join(na)} na")
    if asc: L.append(f"  class {','.join(asc)} assoc")
    return "\n".join(L) + "\n"


EDGE_TEXT = {"sum": "parent = sum of these rows", "product": "parent = product of the x children",
             "component": "one measured part of the parent", "association": "association only (matched comparison or text)",
             "not_answerable": "no data"}


def node_table(tree, vals):
    H = ["| Node | Value | Edge to parent | Grain | Counts | Denominator | Why it moves | Threshold that changes the action | Model / metric | Ontology claims | Answerable |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    cell = lambda x: str(x or "").replace("|", "/").replace("\n", " ").strip() or "-"
    for n in tree["nodes"]:
        e = EDGE_TEXT.get(n.get("edge"), "root") + (" (association only)" if n.get("association") else "")
        src = n.get("fact") and f"recommendation_report.json: {n['fact']}"
        H.append("| " + " | ".join(cell(x) for x in [
            f"**{n['label']}** (`{n['id']}`)", fmt(n, vals[n["id"]]), e, n.get("grain", "judged order" if n.get("edge") != "not_answerable" else ""),
            n.get("counts") or n.get("reason"), n.get("denominator"), n.get("why_moves"), n.get("threshold"),
            ", ".join(n.get("models", [])) + (f"; {src}" if src else ""), ", ".join(n.get("claims", [])), n.get("answerable")]) + " |")
    return "\n".join(H) + "\n"


START, END = "<!-- kpi-tree:start (generated by story/kpi_tree.py; do not edit) -->", "<!-- kpi-tree:end -->"


def questions_block(tree, vals):
    return f"{START}\n```mermaid\n{mermaid(tree, vals)}```\n\n{node_table(tree, vals)}{END}"


def splice(text, block):
    a, b = text.index(START), text.index(END) + len(END)
    return text[:a] + block + text[b:]


def main():
    tree = yaml.safe_load(TREE.read_text())
    vals = compute(tree)
    vals["labels"] = label_eval()
    res = check(tree, vals)
    bad = [r for r in res if not r[2]]
    for kind, nid, ok, msg in res:
        if not ok or kind in ("sum", "product", "fact", "labels"):
            print(f"{'PASS' if ok else 'FAIL'}  {kind:8} {nid:26} {msg}")
    print(f"{len(res) - len(bad)}/{len(res)} KPI tree checks PASS")
    out = ROOT / "story" / "data" / "kpi_tree.json"
    fresh = json.dumps(vals, indent=1) + "\n"
    if "--check" in sys.argv:
        q = (ROOT / "story" / "QUESTIONS.md").read_text()
        same = (out.exists() and out.read_text() == fresh and (ROOT / "story" / "kpi_tree.mmd").read_text() == mermaid(tree, vals)
                and splice(q, questions_block(tree, vals)) == q)
        print(f"{'PASS' if same else 'FAIL'}  committed kpi_tree.json, kpi_tree.mmd and the tree in QUESTIONS.md match the warehouse"
              + ("" if same else " (run python story/kpi_tree.py and commit)"))
        bad += [] if same else [("stale",)]
    else:
        (ROOT / "story" / "data").mkdir(exist_ok=True)
        out.write_text(fresh)
        qp = ROOT / "story" / "QUESTIONS.md"
        qp.write_text(splice(qp.read_text(), questions_block(tree, vals)))
        (ROOT / "story" / "kpi_tree.mmd").write_text(mermaid(tree, vals))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
