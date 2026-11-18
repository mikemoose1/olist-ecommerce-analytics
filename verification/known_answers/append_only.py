#!/usr/bin/env python3
"""Questions are append-only. An existing question may not disappear or change without a written reason.

What is guarded, per question id: the original wording, the reworded wording (with forbidden_tables), and the key SQL.
  questions_baseline.json   fingerprint (sha256 of normalized content) of every adopted question. Grows only.
  questions_changelog.yml   every change: id, field (original | reworded | key), old_sha, new_sha, date, gap, reason.

Rules (all checked on every run, and in CI):
  1. every baselined id still exists in both question files and in answer_key.sql
  2. each fingerprint equals the baseline, or the changelog chains baseline -> current (old_sha -> new_sha, each with a reason)
  3. an id that is not in the baseline fails: finish the key by hand, then run `append_only.py --adopt`
     (adopt refuses ids with no key, no reworded twin, or a null key)
  4. with --against REV (CI passes the base commit): every baseline entry and changelog entry at REV is still present, unchanged.
     This stops anyone editing the baseline or deleting history to hide a change.

Usage:  python append_only.py [--against REV] [--adopt] [--print-sha ID FIELD]
"""
import argparse, hashlib, json, os, re, subprocess, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
_top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=HERE, capture_output=True, text=True).stdout.strip()
REL = os.path.relpath(HERE, _top) if _top else "."
FILES = {"original": "questions.yml", "reworded": "questions_reworded.yml"}
BASELINE, CHANGELOG, KEY = "questions_baseline.json", "questions_changelog.yml", "answer_key.sql"
FIELDS = ("original", "reworded", "key")


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def norm(text):
    return re.sub(r"\s+", " ", text).strip()


def load_questions(read):
    out = {}
    for field, f in FILES.items():
        for q in yaml.safe_load(read(f)) or []:
            out.setdefault(q["id"], {})[field] = sha({"question": norm(q["question"]), "forbidden_tables": q.get("forbidden_tables", [])})
    return out


def load_keys(read):
    keys, cur = {}, None
    for line in read(KEY).splitlines():
        m = re.match(r"--\s*(q\d+)\s*$", line.strip())
        if m:
            cur = m.group(1)
            keys[cur] = []
        elif cur and not line.strip().startswith("--"):
            keys[cur].append(line)
    return {k: sha(norm("\n".join(v))) for k, v in keys.items() if norm("\n".join(v))}


def current(read=None):
    read = read or (lambda f: open(os.path.join(HERE, f)).read())
    qs, keys = load_questions(read), load_keys(read)
    for qid in qs:
        if qid in keys:
            qs[qid]["key"] = keys[qid]
    return qs


def git_show(rev, name):
    p = subprocess.run(["git", "show", f"{rev}:{REL}/{name}"], cwd=HERE, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def chain(start, qid, field, log):
    """Follow the changelog from the baseline fingerprint. Returns (final_sha, problems)."""
    cur, seen, problems = start, {start}, []
    while True:
        nxt = [e for e in log if e["id"] == qid and e["field"] == field and e["old_sha"] == cur]
        if not nxt:
            return cur, problems
        if len(nxt) > 1:
            return cur, [f"{qid} {field}: two changelog entries start from {cur}"]
        e = nxt[0]
        if len(str(e.get("reason", "")).strip()) < 15:
            problems.append(f"{qid} {field}: changelog entry {cur}->{e['new_sha']} has no real reason")
        cur = e["new_sha"]
        if cur in seen:
            return cur, problems + [f"{qid} {field}: changelog loops"]
        seen.add(cur)


def check(against=None):
    base = json.load(open(os.path.join(HERE, BASELINE)))
    log = yaml.safe_load(open(os.path.join(HERE, CHANGELOG))) or []
    cur = current()
    problems = []
    for e in log:
        for k in ("id", "field", "old_sha", "new_sha", "date", "reason"):
            if not e.get(k):
                problems.append(f"changelog entry {e} is missing '{k}'")
    for qid, fields in base.items():
        if qid not in cur:
            problems.append(f"{qid}: removed (questions are append-only)")
            continue
        for field, start in fields.items():
            if field not in cur[qid]:
                problems.append(f"{qid}: {field} is gone")
                continue
            end, pr = chain(start, qid, field, log)
            problems += pr
            if end != cur[qid][field]:
                problems.append(f"{qid} {field}: changed ({start} -> {cur[qid][field]}) without a changelog entry that reaches it")
    for qid in sorted(set(cur) - set(base)):
        problems.append(f"{qid}: not adopted. Hand-compute its key, then run: python append_only.py --adopt")
    if against:
        old_base = git_show(against, BASELINE)
        old_log = git_show(against, CHANGELOG)
        if old_base is None:
            print(f"note: {against} has no baseline yet, history comparison skipped")
        else:
            for qid, fields in json.loads(old_base).items():
                if base.get(qid) != fields:
                    problems.append(f"{qid}: baseline entry differs from the one at {against}")
            now = [json.dumps(e, sort_keys=True, default=str) for e in log]
            for e in yaml.safe_load(old_log) or []:
                if json.dumps(e, sort_keys=True, default=str) not in now:
                    problems.append(f"changelog entry {e['id']} {e['field']} {e['old_sha']}->{e['new_sha']} was edited or removed")
    return base, cur, problems


def adopt():
    base = json.load(open(os.path.join(HERE, BASELINE)))
    cur = current()
    problems = []
    for qid in sorted(set(cur) - set(base)):
        if set(cur[qid]) != set(FIELDS):
            problems.append(f"{qid}: needs both wordings and a key (has {sorted(cur[qid])})")
            continue
        base[qid] = cur[qid]
        print(f"adopted {qid}")
    if problems:
        sys.exit("\n".join(problems))
    json.dump(base, open(os.path.join(HERE, BASELINE), "w"), indent=1, sort_keys=True)
    open(os.path.join(HERE, BASELINE), "a").write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--against")
    ap.add_argument("--adopt", action="store_true")
    ap.add_argument("--print-sha", nargs=2, metavar=("ID", "FIELD"))
    a = ap.parse_args()
    if a.print_sha:
        print(current()[a.print_sha[0]][a.print_sha[1]])
        return
    if a.adopt:
        adopt()
    base, cur, problems = check(a.against)
    if problems:
        print("QUESTIONS APPEND-ONLY: FAIL")
        print("\n".join("  - " + p for p in problems))
        sys.exit(1)
    print(f"questions append-only: PASS ({len(base)} questions fingerprinted, {sum(1 for _ in yaml.safe_load(open(os.path.join(HERE, CHANGELOG))) or [])} recorded changes)")


if __name__ == "__main__":
    main()
