"""Prove story/kpi_tree.py's checks can fail: plant one wrong thing per case and require that check to FAIL.

Each case copies the tree (or the report, or the keyword rule), breaks one thing, recomputes on the real
warehouse and expects a FAIL of the named kind on the named node. The untouched tree must pass first.
"""
import copy, json, sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kpi_tree as K

TREE = yaml.safe_load(K.TREE.read_text())
REPORT = json.loads((K.ROOT / "evidence" / "recommendation_report.json").read_text())


def node(t, nid):
    return next(n for n in t["nodes"] if n["id"] == nid)


QUESTIONS = (K.ROOT / "story" / "QUESTIONS.md").read_text()


def run(tree=None, report=None, rule=None, questions=None):
    tree = tree or TREE
    vals = K.compute(tree, report=report or REPORT)
    vals["labels"] = K.label_eval(rule=rule)
    return K.check(tree, vals) + K.check_thresholds(tree, questions or QUESTIONS)


def mut_sql(nid, key, old, new):
    def f():
        t = copy.deepcopy(TREE)
        n = node(t, nid)
        assert old in n[key], f"{old!r} not in {nid}.{key}"
        n[key] = n[key].replace(old, new)
        return {"tree": t}
    return f


def mut_report(path, delta):
    def f():
        r = copy.deepcopy(REPORT)
        *head, last = path.split(".")
        d = K.dig(r, ".".join(head))
        d[last] += delta
        return {"report": r}
    return f


def mut_node(nid, **kw):
    def f():
        t = copy.deepcopy(TREE)
        node(t, nid).update(kw)
        return {"tree": t}
    return f


def mut_qthr(q, text):
    """Edit question_thresholds and regenerate QUESTIONS.md from it, as `python story/kpi_tree.py` would."""
    def f():
        t = copy.deepcopy(TREE)
        t["question_thresholds"][q] = text
        return {"tree": t, "questions": K.set_question_thresholds(t, QUESTIONS)}
    return f


CASES = [
    ("seller breakdown counts an order once per item", "sum", "late_by_seller",
     mut_sql("late_by_seller", "rows", "select distinct order_id, seller_id from marts.fct_order_items", "select order_id, seller_id from marts.fct_order_items")),
    ("handoff breakdown drops orders with no handoff time", "sum", "late_by_handoff",
     mut_sql("late_by_handoff", "rows", "where is_late", "where is_late and delivered_to_carrier_at is not null")),
    ("state breakdown counts on-time-day deliveries as late", "sum", "late_by_state",
     mut_sql("late_by_state", "rows", "where is_late", "where days_past_promise >= 0")),
    ("month breakdown loses the last month", "sum", "late_by_month",
     mut_sql("late_by_month", "rows", "where is_late", "where is_late and purchase_date < date '2018-08-01'")),
    ("reviewed-late count includes unreviewed orders", "product", "low_star_excess",
     mut_sql("late_reviewed", "sql", " and review_score is not null", "")),
    ("late sales use amount due instead of amount paid", "fact", "late_sales",
     mut_sql("late_sales", "sql", "sum(amount_paid)", "sum(amount_due)")),
    ("report's late-order sales drift by R$1", "fact", "late_sales", mut_report("money.late_order_gmv_window", 1.0)),
    ("claim id that the ontology does not have", "claims", "late_rate", mut_node("late_rate", claims=["metrics.late_rate", "metrics.late_rate_wrong"])),
    ("not-answerable node marked answerable", "shape", "carrier", mut_node("carrier", answerable="yes")),
    ("a node's threshold typed as a literal bar, not from thresholds:", "thresholds", "late_rate",
     mut_node("late_rate", threshold="a segment at 2x the overall rate that holds 10% of late orders is worth targeting")),
    ("QUESTIONS.md states a different bar than thresholds:", "thresholds", "QUESTIONS.md",
     lambda: {"questions": QUESTIONS.replace("at least 1.75 times the overall late rate", "at least 2 times the overall late rate", 1)}),
    ("question_thresholds.Q2 typed as 'at least 2 times', QUESTIONS.md regenerated", "thresholds", "question_thresholds.Q2",
     mut_qthr("Q2", "A segment is a target if its late rate is at least 2 times the overall late rate and it holds at least {segment_share}% of late orders.")),
    ("node threshold written with number words, not bars", "thresholds", "late_rate",
     mut_node("late_rate", threshold="a segment at twice the overall rate that holds a tenth of late orders is worth targeting")),
    ("comment-text node re-edged as a component with its comment claim dropped", "association", "comment_not_arrived_share",
     mut_node("comment_not_arrived_share", edge="component", claims=["terms.chosen_review"])),
    ("matched estimate without its association-only mark", "association", "lost_repeat_sales",
     mut_node("lost_repeat_sales", edge="component", association=False, answerable="yes")),
    ("causal review cost drifts from the per-review rise (total doubled)", "product", "low_star_excess",
     mut_sql("low_star_excess", "sql", "sum(extra_bad_reviews)", "2 * sum(extra_bad_reviews)")),
    ("keyword rule widened to any comment containing a space", "labels", "holdout", lambda: {"rule": K.NOT_ARRIVED + "| "}),
]


def main():
    base = [r for r in run() if not r[2]]
    print(f"{'PASS' if not base else 'FAIL'}  untouched tree passes every check" + (f": {base}" if base else ""))
    fails = bool(base)
    for name, kind, nid, make in CASES:
        res = run(**make())
        hit = [r for r in res if not r[2] and r[0] == kind and r[1] == nid]
        ok = bool(hit)
        fails |= not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name}: {kind} check on {nid} " + (f"fails ({hit[0][3]})" if ok else "did NOT fail"))
    print("SELFTEST FAILED" if fails else f"{len(CASES) + 1}/{len(CASES) + 1} KPI tree selftest cases PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
