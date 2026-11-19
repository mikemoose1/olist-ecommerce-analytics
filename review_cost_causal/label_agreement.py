#!/usr/bin/env python3
"""Reproduce the agreement between the two AI labelers on the 200-review sample (Cohen's kappa), from committed data.

evidence/review_text_labels_sample200.csv holds one row per sampled review: sid, the Olist order_id (the review text is
public Kaggle data keyed by it; it is not copied here) and the label each model gave it from the review text alone
(delivery / product / other). Two AI labelers, labeling independently with the same codebook.

Cohen's kappa = (observed agreement - agreement expected by chance) / (1 - agreement expected by chance).
This measures how much two AIs agree. It is NOT accuracy against ground truth: nobody hand-labeled these reviews.

  python review_cost_causal/label_agreement.py            prints the numbers and fails if they differ from the committed ones
  python review_cost_causal/label_agreement.py --selftest  proves the kappa formula on cases with known answers
"""
import csv, os, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE = os.path.join(ROOT, "evidence", "review_text_labels_sample200.csv")
EXPECTED = {"n": 200, "agree": 187, "raw_agreement": 0.935, "kappa_3class": 0.8908, "kappa_delivery_vs_not": 0.9100}


def kappa(a, b):
    assert len(a) == len(b) and a, "need two equal-length, non-empty label lists"
    n = len(a); po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def selftest():
    ok = True
    def expect(name, got, want, tol=1e-9):
        nonlocal ok
        good = abs(got - want) <= tol; ok &= good
        print(("PASS " if good else "FAIL ") + f"{name}: got {got:.6f}, want {want:.6f}")
    expect("identical labels -> 1", kappa(list("aabb"), list("aabb")), 1.0)
    expect("all disagree on 2 balanced labels -> -1", kappa(list("abab"), list("baba")), -1.0)
    # textbook 2x2 table: 20 yes/yes, 5 yes/no, 10 no/yes, 15 no/no -> po 0.7, pe 0.5, kappa 0.4
    a = ["y"] * 20 + ["y"] * 5 + ["n"] * 10 + ["n"] * 15; b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    expect("textbook table -> 0.4", kappa(a, b), 0.4)
    expect("one labeler says the same thing for everything -> 0", kappa(list("aabb"), list("aaaa")), 0.0)
    return ok


def main():
    if "--selftest" in sys.argv:
        sys.exit(0 if selftest() else 1)
    if not selftest():
        sys.exit(1)
    rows = list(csv.DictReader(open(FILE)))
    s = [r["labeler_a_label"] for r in rows]; h = [r["labeler_b_label"] for r in rows]
    got = {"n": len(rows), "agree": sum(x == y for x, y in zip(s, h)), "kappa_3class": round(kappa(s, h), 4),
           "kappa_delivery_vs_not": round(kappa([x == "delivery" for x in s], [x == "delivery" for x in h]), 4)}
    got["raw_agreement"] = round(got["agree"] / got["n"], 3)
    print(got)
    bad = {k: (got[k], EXPECTED[k]) for k in got if got[k] != EXPECTED[k]}
    print("MATCHES the committed numbers" if not bad else f"DIFFERS: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
