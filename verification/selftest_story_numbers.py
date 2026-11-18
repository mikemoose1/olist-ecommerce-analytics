"""Prove Part C (verification/story_numbers.py) can fail: plant one wrong chart number per case in a copy of story/data,
or one wrong rule in the raw recomputation, and require compare() to flag that number. The untouched data must pass first."""
import csv, json, os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import story_numbers as S

RAW = os.environ.get("OLIST_RAW_DIR", os.path.join(ROOT, "data", "raw"))
DATA = os.path.join(ROOT, "story", "data")


def edit_csv(table, segment, col, fn):
    def f(d):
        p = os.path.join(d, f"{table}.csv")
        rows = list(csv.DictReader(open(p)))
        for r in rows:
            if r["segment"] == segment:
                r[col] = fn(r[col])
        w = csv.DictWriter(open(p, "w"), fieldnames=list(rows[0]), lineterminator="\n"); w.writeheader(); w.writerows(rows)
    return f


def drop_row(table, segment):
    def f(d):
        p = os.path.join(d, f"{table}.csv")
        rows = [r for r in csv.DictReader(open(p)) if r["segment"] != segment]
        w = csv.DictWriter(open(p, "w"), fieldnames=list(rows[0]), lineterminator="\n"); w.writeheader(); w.writerows(rows)
    return f


def edit_fact(key, fn):
    def f(d):
        p = os.path.join(d, "facts.json"); x = json.load(open(p)); x[key] = fn(x[key]); json.dump(x, open(p, "w"))
    return f


CASES = [
    ("one state's late count off by one", "late_by_state:RJ", edit_csv("late_by_state", "RJ", "late", lambda v: str(int(v) + 1))),
    ("a month's rate that its counts do not give", "late_by_month:2018-03", edit_csv("late_by_month", "2018-03", "late_rate", lambda v: str(float(v) + 0.01))),
    ("a month dropped from the chart", "late_by_month:2018-08", drop_row("late_by_month", "2018-08")),
    ("handoff orders swapped between groups", "late_by_handoff:Handed over on time", edit_csv("late_by_handoff", "Handed over on time", "orders", lambda v: str(int(v) - 5))),
    ("comment share rounded the wrong way", "comment_delay_share", edit_fact("comment_delay_share", lambda v: v + 0.001)),
    ("late sales off by R$1", "late_sales_window", edit_fact("late_sales_window", lambda v: v + 1)),
    ("last-12-month late sales off by R$1", "late_sales_last12", edit_fact("late_sales_last12", lambda v: v + 1)),
    ("last-12-month total sales off by R$1", "late_sales_last12", edit_fact("total_sales_last12", lambda v: v + 1)),
    ("last-12-month late first orders off by one", "late_first_last12", edit_fact("late_first_last12", lambda v: v + 1)),
]


def main():
    raw = S.from_raw(RAW)
    base = [r for r in S.compare(S.from_story(DATA), raw) if not r[1]]
    print(f"{'PASS' if not base else 'FAIL'}  untouched story data matches the raw CSVs" + (f": {base[:3]}" if base else ""))
    fails = bool(base)
    for name, target, mutate in CASES:
        d = tempfile.mkdtemp(prefix="story-data-")
        try:
            for f in os.listdir(DATA):
                shutil.copy(os.path.join(DATA, f), d)
            mutate(d)
            hit = [r for r in S.compare(S.from_story(d), raw) if not r[1] and r[0] == target]
        finally:
            shutil.rmtree(d, ignore_errors=True)
        fails |= not hit
        print(f"{'PASS' if hit else 'FAIL'}  {name}: {target} " + (f"flagged ({hit[0][2]})" if hit else "NOT flagged"))
    # a wrong rule on the raw side: count multi-seller orders too (decision C1 excludes them)
    src = open(S.__file__).read().replace("and ia.n_sellers = 1", "")
    ns = {}; exec(compile(src, S.__file__, "exec"), ns)
    hit = [r for r in S.compare(S.from_story(DATA), ns["from_raw"](RAW)) if not r[1] and r[0] == "late_orders"]
    fails |= not hit
    print(f"{'PASS' if hit else 'FAIL'}  raw side counts multi-seller orders: late_orders " + (f"flagged ({hit[0][2]})" if hit else "NOT flagged"))
    print("SELFTEST FAILED" if fails else f"{len(CASES) + 2}/{len(CASES) + 2} Part C selftest cases PASS")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
