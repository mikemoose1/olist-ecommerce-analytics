"""Prove check_case_study.py and erd.py can fail: the real README passes, and each planted error is caught."""
import pathlib
import shutil
import sys
import tempfile

import check_case_study as C
import erd
from common import connect

README = C.README.read_text()
CLAIMS = C.build_claims(connect())
ERD = erd.mermaid()
PAGES_OK = None


def caught(text, erd_text=ERD):
    return bool(C.problems(text, CLAIMS, erd_text))


def sub(old, new):
    assert old in README, f"selftest out of date: {old!r}"
    return README.replace(old, new, 1)


CASES = [
    ("the real README", README, False),
    ("a headline count changed (3,110 to 3,310)", sub("about 3,110 of the 11,635", "about 3,310 of the 11,635"), True),
    ("the late rate changed (6.87% to 6.78%)", sub("6.87% of delivered orders", "6.78% of delivered orders"), True),
    ("a handoff share changed (21.2% to 12.2%)", sub("late 21.2% of the time", "late 12.2% of the time"), True),
    ("a number swapped between two sentences (62.4% and 8.7%)", sub("62.4% of late ones", "8.7% of late ones"), True),
    ("a new number nobody checked", sub("## Question\n", "## Question\n\nThe study covers 12,345 sellers.\n"), True),
    ("a new number word nobody checked", sub("## Question\n", "## Question\n\nThree regions drive it.\n"), True),
    ("the repeat range changed", sub("-0.52 to 0.22", "-0.62 to 0.22"), True),
    ("the check count changed (36 of 36)", sub("pass 36 of 36", "pass 35 of 36"), True),
    ("the holdout figure changed (1.56 to 1.65)", sub("It was 1.56 stars", "It was 1.65 stars"), True),
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

total = len(CASES) + len(ERD_CASES) + len(DATA_CASES)
print(f"{'FAIL' if bad else 'PASS'}  case study selftest: {total - bad}/{total} cases behave")
sys.exit(1 if bad else 0)
