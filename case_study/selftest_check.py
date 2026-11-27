"""Prove check_case_study.py and erd.py can fail: the real README.md, docs/CASE_STUDY.md and docs/HOW_I_CHECK_AI_WORK.md pass, and each planted error is caught."""
import pathlib
import shutil
import sys
import tempfile

import check_case_study as C
import erd
import ontology_view
from common import connect

README = C.FULL.read_text()          # the full case study; the cases below plant errors in it
SHORT = C.README.read_text()         # the short README.md
WRITEUP = C.WRITEUP.read_text()      # docs/HOW_I_CHECK_AI_WORK.md
CLAIMS = C.build_claims(connect())
ERD = erd.mermaid()
SECTION = ontology_view.case_study_section(connect())


def caught(text, erd_text=ERD, which="f"):
    return bool(C.problems(text, CLAIMS, which, erd_text if which == "f" else None, SECTION if which == "f" else None))


def sub(old, new, text=None):
    text = README if text is None else text
    assert old in text, f"selftest out of date: {old!r}"
    return text.replace(old, new, 1)


CASES = [
    ("the real docs/CASE_STUDY.md", README, False),
    ("a headline count changed (3,110 to 3,310)", sub("about 3,110 of the 11,635", "about 3,310 of the 11,635"), True),
    ("the late rate changed (6.87% to 6.78%)", sub("6.87% of delivered orders", "6.78% of delivered orders"), True),
    ("a handoff share changed (21.2% to 12.2%)", sub("late 21.2% of the time", "late 12.2% of the time"), True),
    ("a number swapped between two sentences (62.4% and 8.7%)", sub("62.4% of late ones", "8.7% of late ones"), True),
    ("a new number nobody checked", sub("## Question\n", "## Question\n\nThe study covers 12,345 sellers.\n"), True),
    ("a new number word nobody checked", sub("## Question\n", "## Question\n\nThree regions drive it.\n"), True),
    ("the repeat range changed", sub("-0.52 to 0.22", "-0.62 to 0.22"), True),
    ("the 5.49% what-if rate changed (5.49% to 5.94%)", sub("moves the late rate from 6.87% to 5.49%", "moves the late rate from 6.87% to 5.94%"), True),
    ("the goal line changed (4.4% to 4.8%)", sub("The goal, 4.4%,", "The goal, 4.8%,"), True),
    ("the warning line changed (8.4% to 8.9%)", sub("It sits at 8.4%", "It sits at 8.9%"), True),
    ("the stable-month count changed (15 to 17)", sub("of the 15 stable months", "of the 17 stable months"), True),
    ("the old causal wording back in the limits table", sub("Late delivery is estimated to account for about 3,110 bad reviews", "Late delivery caused about 3,110 bad reviews"), True),
    ("the points unit dropped from the repeat range", sub("-0.52 to 0.22 percentage points", "-0.52 to 0.22 points"), True),
    ("the check count changed (51 of 51)", sub("pass 51 of 51", "pass 50 of 51"), True),
    ("the holdout figure changed (1.56 to 1.65)", sub("It was 1.56 stars", "It was 1.65 stars"), True),
    ("the late definition counts same-day arrival as late", sub("Late. Delivered on a later calendar day than the promised date. Same-day delivery is on time.", "Late. Arriving on the promised day counts as late."), True),
    ("the stress-test E-value to explain away changed (8.7 to 9.7)", sub("and 8.7 to explain it away", "and 9.7 to explain it away"), True),
    ("the failed planted-effect coverage shown as passing (16 to 18)", sub("in 20, 16 and 17 of 20 draws", "in 20, 18 and 17 of 20 draws"), True),
    ("the interval coverage changed (53 to 58 of 60)", sub("in 53 of 60 draws", "in 58 of 60 draws"), True),
    ("the six-specification spread coverage changed (10 to 18)", sub("only 16, 10 and 12 of 20", "only 16, 18 and 12 of 20"), True),
    ("the holdout calibration direction changed (64.8% to 35.2%)", sub("64.8% of orders arrived by the date labelled 50%", "35.2% of orders arrived by the date labelled 50%"), True),
    ("the projected delivery-range cut changed (502 to 602)", sub("projected to cut 502 extra", "projected to cut 602 extra"), True),
    ("the late-rate population includes multi-seller orders", sub("Single-seller orders only", "All orders, including those with several sellers"), True),
]

SHORT_CASES = [
    ("the real README.md", SHORT, False),
    ("README.md: a headline count changed (3,110 to 3,310)", sub("about 3,110 of the 11,635", "about 3,310 of the 11,635", SHORT), True),
    ("README.md: the late rate changed (6.87% to 6.78%)", sub("6.87% of delivered orders", "6.78% of delivered orders", SHORT), True),
    ("README.md: the dashboard what-if changed (3.4% to 3.9%)", sub("The what-if rate of 3.4%", "The what-if rate of 3.9%", SHORT), True),
    ("README.md: the warning line changed (8.4% to 8.9%)", sub("the warning line, 8.4%,", "the warning line, 8.9%,", SHORT), True),
    ("README.md: the E-value changed (5.1 to 5.9)", sub("an E-value of 5.1", "an E-value of 5.9", SHORT), True),
    ("README.md: the failed planted-effect row shown as passing (16 to 18 of 20)", sub("in 16 of 20 draws", "in 18 of 20 draws", SHORT), True),
    ("README.md: the calibration error changed in the table (14.8 to 4.8)", sub("| 14.8 points (rule", "| 4.8 points (rule", SHORT), True),
    ("README.md: a new number nobody checked", sub("## The short version\n", "## The short version\n\nThe study covers 12,345 sellers.\n", SHORT), True),
]
CARD = C.MODEL_CARD.read_text()
WRITEUP_CASES = [
    ("the real docs/HOW_I_CHECK_AI_WORK.md", WRITEUP, False),
    ("write-up: the mutation count changed (248 to 284)", sub("All 248 rules", "All 284 rules", WRITEUP), True),
    ("write-up: the planted-answer miss shown as a pass (16 to 18 of 20)", sub("covered it in 16 of 20 draws", "covered it in 18 of 20 draws", WRITEUP), True),
    ("write-up: the stress-test outcome changed (two missed to one missed)", sub("Two met every rule. Two missed one rule each.", "Three met every rule. One missed one rule.", WRITEUP), True),
    ("write-up: the overall coverage changed (53 to 58 of 60)", sub("in 53 of 60", "in 58 of 60", WRITEUP), True),
    ("write-up: the pre-registered limit changed (17 to 16 of 20)", sub("at least 17 of 20 draws", "at least 16 of 20 draws", WRITEUP), True),
    ("write-up: the interval changed (3,025 to 3,195 to 3,000 to 3,200)", sub("quote 3,025 to 3,195", "quote 3,000 to 3,200", WRITEUP), True),
    ("write-up: a new number nobody checked", sub("## The checks that can fail\n", "## The checks that can fail\n\nThe agents wrote 12,345 lines.\n", WRITEUP), True),
]

CARD_CASES = [
    ("the real delivery-range model card", CARD, False),
    ("model card: the calibration error changed (14.8 to 4.8)", sub("a calibration error of 14.8 points", "a calibration error of 4.8 points", CARD), True),
    ("model card: the holdout CRPS changed (3.601 to 3.501)", sub("Holdout CRPS 3.601 days", "Holdout CRPS 3.501 days", CARD), True),
    ("model card: a new number nobody checked", sub("## Model card\n", "## Model card\n\nIt was trained on 12,345 orders.\n", CARD), True),
]
ERD_CASES = [
    ("the ERD drawn with a wrong cardinality", README, ERD.replace("customers ||--|| orders", "customers ||--o{ orders")),
    ("the ERD with a key dropped", README, ERD.replace("int order_item_id PK", "int order_item_id")),
]

bad = 0
for name, text, want in CASES:
    ok = caught(text) == want
    bad += not ok
    print(("PASS " if ok else "FAIL ") + name)
for name, text, want in SHORT_CASES:
    ok = caught(text, which="s") == want
    bad += not ok
    print(("PASS " if ok else "FAIL ") + name)
for name, text, want in WRITEUP_CASES:
    ok = caught(text, which="w") == want
    bad += not ok
    print(("PASS " if ok else "FAIL ") + name)
for name, text, want in CARD_CASES:
    ok = bool(C.problems(C.model_card(text), CLAIMS, "d")) == want
    bad += not ok
    print(("PASS " if ok else "FAIL ") + name)
for name, text, erd_text in ERD_CASES:
    ok = caught(text, erd_text)   # README block now differs from the erd_text it is compared with
    bad += not ok
    print(("PASS " if ok else "FAIL ") + name)

# Planted bad data: each change must make an ERD data check fail. The real CSVs are linked, not copied.
def planted(file, edit):
    tmp = pathlib.Path(tempfile.mkdtemp())
    for f in pathlib.Path(erd.RAW).iterdir():
        (tmp / f.name).symlink_to(f)
    target = tmp / file
    target.unlink()
    shutil.copy(erd.RAW / file, target)
    lines = (erd.RAW / file).read_text(encoding="utf-8-sig").splitlines()
    target.write_text("\n".join(edit(lines)) + "\n")
    return tmp


DATA_CASES = [
    ("an order item that names no order", "olist_order_items_dataset.csv", lambda L: L + ['"ffffffffffffffffffffffffffffffff","1","x","y","2018-01-01 00:00:00","1.0","1.0"']),
    ("a duplicate customer_id", "olist_customers_dataset.csv", lambda L: L + [L[1]]),
    ("a second customer for one order", "olist_orders_dataset.csv", lambda L: [L[0]] + [L[1].replace(L[1].split(",")[1], L[2].split(",")[1], 1)] + L[2:]),
]
real_raw = erd.RAW
for name, file, edit in DATA_CASES:
    erd.RAW = planted(file, edit)
    try:
        ok = any(not r[1] for r in erd.check_data())
    finally:
        erd.RAW = real_raw
    bad += not ok
    print(("PASS " if ok else "FAIL ") + "ERD data check catches " + name)


import copy
MARK_CASES = [
    ("a customer zip prefix marked FK", "customers", "customer_zip_code_prefix", "FK"),
    ("a seller zip prefix marked FK", "sellers", "seller_zip_code_prefix", "FK"),
    ("a product category marked FK", "products", "product_category_name", "FK"),
    ("geolocation zip marked as a unique key", "geolocation", "geolocation_zip_code_prefix", "PK"),
]
TABLE_BAK = copy.deepcopy(erd.TABLES)
REL_BAK = copy.deepcopy(erd.RELATIONS)
for name, table, col, mark in MARK_CASES:
    pk, cols = erd.TABLES[table]
    erd.TABLES[table] = (pk, [(a, b, mark if b == col else c) for a, b, c in cols])
    ok = any(not r[1] for r in erd.check_marks())
    erd.TABLES.clear()
    erd.TABLES.update(copy.deepcopy(TABLE_BAK))
    bad += not ok
    print(("PASS " if ok else "FAIL ") + "ERD mark check catches " + name)

# Wrong cardinality: orders ||--|| order_items. Needs the CSV checks.
erd.RELATIONS[:] = [
    (r[0], r[1], r[2], "||", r[4], r[5], r[6]) if r[0] == "orders" and r[4] == "order_items" else r
    for r in erd.RELATIONS
]
ok = any(not r[1] for r in erd.check_data())
erd.RELATIONS[:] = copy.deepcopy(REL_BAK)
bad += not ok
print(("PASS " if ok else "FAIL ") + "ERD data check catches a wrong orders-to-items cardinality")

total = len(CASES) + len(SHORT_CASES) + len(CARD_CASES) + len(ERD_CASES) + len(DATA_CASES) + len(MARK_CASES) + 1
print(f"{'FAIL' if bad else 'PASS'}  case study selftest: {total - bad}/{total} cases behave")
sys.exit(1 if bad else 0)
