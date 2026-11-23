"""Hiring-manager slice of ontology/ontology.yml, plus the late-rate population bridge.

`case_study_section(con)` is the markdown that docs/CASE_STUDY.md must contain. check_case_study.py
fails if the page drifts from this text. Meanings come from the YAML; the bridge counts come from
the warehouse.
"""
import yaml

from common import ROOT, row

YML = ROOT / "ontology" / "ontology.yml"

# Heading shown on the case study page, then the term name in ontology.yml.
CONCEPTS = [
    ("Customer ID", "customer_id"),
    ("Person", "person"),
    ("Order", "order"),
    ("Late", "late"),
    ("Ship-by date", "ship_by_date"),
    ("Handoff to carrier", "handoff_to_carrier"),
    ("Late handoff", "late_handoff"),
    ("Multi-seller order", "multi_seller_order"),
]


def load():
    return yaml.safe_load(YML.read_text())


def _meaning(onto, name):
    if name in onto["terms"]:
        card = onto["terms"][name]
        return card["meaning"], card["source"]
    e = onto["entities"][name]
    return e["meaning"], f"{e['table']}.{e['key']}" if isinstance(e["key"], str) else f"{e['table']}.{e['key'][0]}"


def concepts_table(onto=None):
    onto = onto or load()
    lines = [
        "| Concept | Meaning | Lives in |",
        "|---|---|---|",
    ]
    for heading, name in CONCEPTS:
        meaning, source = _meaning(onto, name)
        lines.append(f"| {heading} | {meaning} | `{source}` |")
    return "\n".join(lines)


def _fmt(n):
    return f"{n:,}"


def bridge(con):
    """Sequential filters from fct_orders that end at metric_late_rate_orders."""
    a, b, c, d, e, nd, conf, multi, judged = row(con, """
        select
          count(*),
          count(*) filter (where delivery_state in ('delivered_on_time', 'delivered_late')),
          count(*) filter (where delivery_state in ('delivered_on_time', 'delivered_late') and n_items > 0),
          count(*) filter (where delivery_state in ('delivered_on_time', 'delivered_late') and n_items > 0 and in_analysis_window),
          count(*) filter (where delivery_state in ('delivered_on_time', 'delivered_late') and n_items > 0 and in_analysis_window and n_parcels = 1),
          count(*) filter (where delivery_state = 'not_delivered'),
          count(*) filter (where delivery_state = 'status_date_conflict'),
          count(*) filter (where n_parcels > 1),
          (select count(*) from metrics.metric_late_rate_orders)
        from marts.fct_orders
    """)
    assert e == judged, (e, judged)
    steps = [
        ("A", "All orders in the source", a, None),
        ("B", "Delivered, with a delivery date (delivery_state on time or late)", b, a - b),
        ("C", "At least one item (n_items above zero)", c, b - c),
        ("D", "Bought in the analysis window (in_analysis_window)", d, c - d),
        ("E", "Single-seller orders only (delivery evidence is not multi-parcel)", e, d - e),
    ]
    removed_e = d - e
    earlier_multi = multi - removed_e
    lines = [
        "The late rate uses a defined set of orders, not every row. The project setting `multi_seller_late_rule` is `exclude_multi_seller`. Each row shows how many orders remain after that filter.",
        "",
        "| Step | Rule | Orders left | Removed |",
        "|---|---|---|---|",
    ]
    for step, rule, left, removed in steps:
        rem = "" if removed is None else ("none" if removed == 0 else _fmt(removed))
        lines.append(f"| {step} | {rule} | {_fmt(left)} | {rem} |")
    lines += [
        "",
        f"The {_fmt(removed_e)} orders removed at the last step are the multi-seller orders that were still left. The source has {_fmt(multi)} such orders. The other {earlier_multi} were already removed by an earlier step. Each seller ships its own parcel, but the data keeps one delivery date for the order, so whether it was late cannot be observed.",
        "",
        f"Not delivered or conflicting: {_fmt(nd)} not delivered, {conf} with a status that disagrees with the delivery date. These orders have no reliable delivery outcome.",
    ]
    return "\n".join(lines)


def late_rules(con, onto=None):
    onto = onto or load()
    late = onto["terms"]["late"]["meaning"]
    handoff = onto["terms"]["late_handoff"]["meaning"]
    judged, have, late_n, none = row(con, """
        select
          count(*),
          count(*) filter (where o.delivered_to_carrier_at is not null),
          count(*) filter (where o.delivered_to_carrier_at is not null and o.delivered_to_carrier_at > o.last_shipping_limit_at),
          count(*) filter (where o.delivered_to_carrier_at is null)
        from metrics.metric_late_rate_orders l
        join marts.fct_orders o using (order_id)
    """)
    return "\n".join([
        f"Late. {late} It is judged only on the late-rate population, after the filters below.",
        "",
        f"Late handoff. {handoff} Among the judged orders, {have:,} have a handoff time and {late_n:,} of them were handed over late. {none} judged order has no handoff time and is in neither group.",
    ])


def case_study_section(con):
    onto = load()
    rules = late_rules(con, onto)
    pop = bridge(con)
    return "\n".join([
        "The ZIP-prefix and product-category columns are drawn as soft links, not keys, because the data does not keep them unique or complete. A review ID can appear on more than one order.",
        "",
        "### What the words mean",
        "",
        "An ontology here is the project's agreed list of business concepts: what each one means, and where it lives in the data. The table and the rules below are generated from [ontology/ontology.yml](../ontology/ontology.yml), and a script checks them against the warehouse.",
        "",
        concepts_table(onto),
        "",
        "### What counts as late",
        "",
        rules,
        "",
        "### Which orders are judged",
        "",
        pop,
    ])


if __name__ == "__main__":
    from common import connect
    print(case_study_section(connect()))
