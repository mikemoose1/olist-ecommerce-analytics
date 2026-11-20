"""The entity-relationship diagram in docs/CASE_STUDY.md, as data.

SPEC is the one source. `mermaid()` draws it, and `check_data()` tests every key and every cardinality
against the raw CSVs in data/raw with DuckDB. A column marked FK must belong to a true foreign-key
relation: the parent key is unique, and no child row is blank or orphaned. check_case_study.py fails
if the case study's diagram differs from `mermaid()`. Run `python case_study/erd.py` to check the data
and print the diagram.

Cardinality marks follow Mermaid: `||` exactly one, `|o` zero or one, `|{` one or many, `o{` zero or many.
"""
import sys

from common import ROOT

RAW = ROOT / "data" / "raw"
FILES = {
    "customers": "olist_customers_dataset.csv",
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}

# table -> (primary key columns, columns drawn as (type, name, mark)). Names are the raw CSV column names.
# Marks: PK, FK, PK,FK, or a token expanded in mermaid(). Zip prefixes and product category are
# soft links, not foreign keys: the parent is not unique, or some child rows have no parent.
TABLES = {
    "customers": (["customer_id"], [("string", "customer_id", "PK"), ("string", "customer_unique_id", "person"), ("string", "customer_zip_code_prefix", "soft_zip")]),
    "orders": (["order_id"], [("string", "order_id", "PK"), ("string", "customer_id", "FK"), ("string", "order_status", ""), ("timestamp", "order_purchase_timestamp", ""),
                              ("timestamp", "order_delivered_customer_date", ""), ("timestamp", "order_estimated_delivery_date", "")]),
    "order_items": (["order_id", "order_item_id"], [("string", "order_id", "PK,FK"), ("int", "order_item_id", "PK"), ("string", "product_id", "FK"), ("string", "seller_id", "FK"),
                                                   ("timestamp", "shipping_limit_date", ""), ("decimal", "price", "")]),
    "sellers": (["seller_id"], [("string", "seller_id", "PK"), ("string", "seller_zip_code_prefix", "soft_zip")]),
    "products": (["product_id"], [("string", "product_id", "PK"), ("string", "product_category_name", "soft_cat")]),
    "category_translation": (["product_category_name"], [("string", "product_category_name", "PK"), ("string", "product_category_name_english", "")]),
    "order_payments": (["order_id", "payment_sequential"], [("string", "order_id", "PK,FK"), ("int", "payment_sequential", "PK"), ("decimal", "payment_value", "")]),
    "order_reviews": (["review_id", "order_id"], [("string", "review_id", "review_pk"), ("string", "order_id", "PK,FK"), ("int", "review_score", "")]),
    "geolocation": ([], [("string", "geolocation_zip_code_prefix", "zip"), ("double", "geolocation_lat", ""), ("double", "geolocation_lng", "")]),
}

# (parent, parent key, parent mark, child mark, child, child column, kind). kind is "fk" for a true
# foreign key, or "soft" for a drawn link that is not a key.
RELATIONS = [
    ("customers", "customer_id", "||", "||", "orders", "customer_id", "fk"),
    ("orders", "order_id", "||", "o{", "order_items", "order_id", "fk"),
    ("products", "product_id", "||", "|{", "order_items", "product_id", "fk"),
    ("sellers", "seller_id", "||", "|{", "order_items", "seller_id", "fk"),
    ("orders", "order_id", "||", "o{", "order_payments", "order_id", "fk"),
    ("orders", "order_id", "||", "o{", "order_reviews", "order_id", "fk"),
    ("category_translation", "product_category_name", "|o", "|{", "products", "product_category_name", "soft"),
]
# Zip prefixes join approximately: geolocation holds many points per zip, and a zip has many customers or sellers.
ZIP_LINKS = [("customers", "customer_zip_code_prefix"), ("sellers", "seller_zip_code_prefix")]

MARKS = {
    "person": '"person id, not unique"',
    "zip": '"zip prefix, not unique"',
    "soft_zip": '"zip prefix, soft link"',
    "soft_cat": '"soft link, some blank or untranslated"',
    "review_pk": 'PK "repeats across orders"',
}


def _fk_mark(mark):
    return "FK" in {p.strip() for p in mark.split(",") if p.strip()}


def _column_marks(table):
    return {name: mark for _, name, mark in TABLES[table][1]}


def check_marks():
    """Mark contracts that can be checked without reading the CSVs."""
    res = []

    def add(desc, ok, detail=""):
        res.append((desc, bool(ok), detail))

    geo_mark = _column_marks("geolocation")["geolocation_zip_code_prefix"]
    add("geolocation.geolocation_zip_code_prefix is not marked as a unique key", geo_mark not in ("PK", "FK") and not _fk_mark(geo_mark), geo_mark)

    drawn_fk = [(t, name) for t, (_, cols) in TABLES.items() for _, name, mark in cols if _fk_mark(mark)]
    rel_fk = [(child, col) for *_, child, col, kind in RELATIONS if kind == "fk"]
    for t, name in drawn_fk:
        add(f"{t}.{name}: marked FK only when it is a true foreign key", (t, name) in rel_fk)
    for child, col in rel_fk:
        add(f"{child}.{col}: a true foreign key is marked FK", (child, col) in drawn_fk, _column_marks(child).get(col, ""))
    for child, col in ZIP_LINKS:
        add(f"{child}.{col}: zip prefix is not marked FK", not _fk_mark(_column_marks(child)[col]), _column_marks(child)[col])
    return res


def mermaid():
    out = ["erDiagram"]
    for parent, key, pm, cm, child, col, _ in RELATIONS:
        out.append(f'    {parent} {pm}--{cm} {child} : "{col}"')
    for child, col in ZIP_LINKS:
        out.append(f'    geolocation }}o--o{{ {child} : "zip prefix (approximate)"')
    for t, (_, cols) in TABLES.items():
        out.append(f"    {t} {{")
        for typ, name, mark in cols:
            m = MARKS.get(mark, mark)
            out.append(f"        {typ} {name} {m}".rstrip())
        out.append("    }")
    return "\n".join(out)


def check_data():
    """Return (list of (description, ok, detail), ...). Reads the raw CSVs, not the dbt models."""
    import duckdb

    con = duckdb.connect()
    for t, f in FILES.items():
        con.sql(f"create view {t} as select * from read_csv_auto('{RAW / f}', header=true, all_varchar=true)")
    one = lambda q: con.sql(q).fetchall()[0][0]
    res = []

    def add(desc, ok, detail=""):
        res.append((desc, bool(ok), detail))

    for t, (pk, _) in TABLES.items():
        if pk:
            cols = ", ".join(pk)
            n, d = one(f"select count(*) from {t}"), one(f"select count(*) from (select distinct {cols} from {t})")
            add(f"{t}: ({cols}) is unique", n == d, f"{n} rows, {d} distinct")
    n = one("select count(*) from order_reviews")
    add("order_reviews: review_id alone is NOT unique", one("select count(distinct review_id) from order_reviews") < n)
    add("geolocation: zip prefix is not unique", one("select count(*) from geolocation") > one("select count(distinct geolocation_zip_code_prefix) from geolocation"))
    add("customers: one person owns several customer_ids", one("select count(distinct customer_unique_id) from customers") < one("select count(*) from customers"))

    res.extend(check_marks())

    for parent, key, pm, cm, child, col, kind in RELATIONS:
        tag = f"{parent}.{key} -> {child}.{col}"
        orphans = one(f"select count(*) from {child} c where c.{col} is not null and c.{col} not in (select {key} from {parent})")
        nulls = one(f"select count(*) from {child} where {col} is null")
        p_unique = one(f"select count(*) from {parent}") == one(f"select count(*) from (select distinct {key} from {parent})")
        if kind == "fk":
            add(f"{tag}: FK parent key is unique, and no child row is blank or orphaned",
                p_unique and orphans == 0 and nulls == 0,
                f"parent unique {p_unique}, {orphans} orphans, {nulls} nulls")
        if pm == "|o":   # the parent is optional: some child rows must really lack one
            add(f"{tag}: a child may lack a parent (|o is earned)", orphans + nulls > 0, f"{orphans} child rows name a missing parent, {nulls} are blank")
        elif kind != "fk":
            add(f"{tag}: every child row has a parent", orphans == 0 and nulls == 0, f"{orphans} orphans, {nulls} nulls")
        per_parent = f"select p.{key} k, count(c.{col}) n from {parent} p left join {child} c on c.{col} = p.{key} group by 1"
        zero = one(f"select count(*) from ({per_parent}) where n = 0")
        many = one(f"select count(*) from ({per_parent}) where n > 1")
        detail = f"{zero} with none, {many} with several"
        if cm == "||":
            add(f"{tag}: each parent has exactly one child", zero == 0 and many == 0, detail)
        elif cm == "|{":
            add(f"{tag}: each parent has at least one child, some have several", zero == 0 and many > 0, detail)
        else:
            add(f"{tag}: some parents have no child and some have several (o{{ is earned)", zero > 0 and many > 0, detail)
    for child, col in ZIP_LINKS:
        no_geo = one(f"select count(distinct {col}) from {child} where {col} not in (select geolocation_zip_code_prefix from geolocation)")
        no_cust = one(f"select count(distinct geolocation_zip_code_prefix) from geolocation where geolocation_zip_code_prefix not in (select {col} from {child})")
        multi = one(f"select max(n) from (select count(*) n from {child} group by {col})")
        add(f"geolocation ~ {child}.{col}: zips join on both sides, with misses on both (o is earned)", no_geo > 0 and no_cust > 0 and multi > 1,
            f"{no_geo} {child} zips with no geolocation row, {no_cust} geolocation zips with no {child}, up to {multi} {child} per zip")
    # drawn columns exist in the CSVs
    for t, (_, cols) in TABLES.items():
        have = {r[0] for r in con.sql(f"describe {t}").fetchall()}
        missing = [c[1] for c in cols if c[1] not in have]
        add(f"{t}: every drawn column exists in the CSV", not missing, ", ".join(missing))
    return res


if __name__ == "__main__":
    results = check_data()
    for desc, ok, detail in results:
        print(("PASS " if ok else "FAIL ") + desc + (f"  [{detail}]" if detail else ""))
    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} ERD checks pass\n")
    print(mermaid())
    sys.exit(1 if bad else 0)
