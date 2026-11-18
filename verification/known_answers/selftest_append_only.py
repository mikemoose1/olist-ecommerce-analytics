#!/usr/bin/env python3
"""Mutation proof for append_only.py: each way of breaking the append-only rule must fail, and the real files must pass."""
import json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
FILES = ["append_only.py", "questions.yml", "questions_reworded.yml", "answer_key.sql", "questions_baseline.json", "questions_changelog.yml"]


def sandbox(pre=None):
    d = tempfile.mkdtemp(prefix="appendonly-")
    for f in FILES:
        shutil.copy(os.path.join(HERE, f), d)
    if pre:
        pre(d)
    for c in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"]):
        subprocess.run(c, cwd=d, check=True, capture_output=True)
    return d


def run(d, *args):
    p = subprocess.run([PY, os.path.join(d, "append_only.py"), *args], cwd=d, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def edit(d, name, fn):
    p = os.path.join(d, name)
    text = fn(open(p).read())
    open(p, "w").write(text)


def drop_block(text, qid):
    return re.sub(rf"- id: {qid}\n(?:  .*\n)+", "", text)


CASES = [
    ("a question is removed from the original file", lambda d: edit(d, "questions.yml", lambda t: drop_block(t, "q05")), ["q05"], []),
    ("a reworded twin is removed", lambda d: edit(d, "questions_reworded.yml", lambda t: drop_block(t, "q05")), ["q05"], []),
    ("a question's wording changes with no changelog entry", lambda d: edit(d, "questions.yml", lambda t: t.replace("late-delivery rate, as a percentage", "late-delivery rate, as a ratio")), ["q01", "without a changelog"], []),
    ("a forbidden_tables rule is dropped", lambda d: edit(d, "questions_reworded.yml", lambda t: t.replace('  forbidden_tables: ["metrics.*"]\n', "", 1)), ["without a changelog"], []),
    ("a key's SQL changes with no changelog entry", lambda d: edit(d, "answer_key.sql", lambda t: t.replace("select count(*) from marts.fct_orders\nwhere order_status = 'delivered'", "select count(*) + 1 from marts.fct_orders\nwhere order_status = 'delivered'", 1)), ["q02", "key"], []),
    ("a key's SQL is deleted", lambda d: edit(d, "answer_key.sql", lambda t: re.sub(r"-- q10\n.*?(?=\n-- q11)", "-- q10", t, flags=re.S)), ["q10"], []),
    ("a changelog entry's reason is emptied", lambda d: edit(d, "questions_changelog.yml", lambda t: re.sub(r"reason: >-\n(?:    .*\n)+", "reason: ok\n", t)), ["no real reason"], []),
    ("a note on a question has no reason", lambda d: open(os.path.join(d, "questions_changelog.yml"), "a").write("- id: q03\n  field: note\n  date: 2026-11-17\n  reason: ok\n"), ["no real reason"], []),
    ("a new question is added but never adopted", lambda d: (edit(d, "questions.yml", lambda t: t + "- id: q97\n  question: How many sellers are there?\n")), ["q97", "not adopted"], []),
    ("the baseline is edited to match a changed question", None, ["differs from the one at"], ["--against", "HEAD"]),
    ("a changelog note is deleted from history", lambda d: edit(d, "questions_changelog.yml", lambda t: re.sub(r"- id: q12\n  field: note\n(?:  .*\n)+?(?=- id|\Z)", "", t)), ["q12", "removed"], ["--against", "HEAD"]),
    ("a changelog entry is deleted from history", lambda d: edit(d, "questions_changelog.yml", lambda t: "[]\n"), ["q09"], ["--against", "HEAD"]),
]


def note(qid, n):
    return f"- id: {qid}\n  field: note\n  date: 2026-11-17\n  reason: note number {n} for {qid}, long enough to count as a real reason\n"


def two_notes(d):
    with open(os.path.join(d, "questions_changelog.yml"), "a") as f:
        f.write(note("q05", 1) + note("q05", 2))


def commit(d, msg):
    subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", msg], cwd=d, capture_output=True)


def delete_everywhere(d, qid):
    for f in ("questions.yml", "questions_reworded.yml"):
        edit(d, f, lambda t: drop_block(t, qid))
    edit(d, "answer_key.sql", lambda t: re.sub(rf"-- {qid}\n.*?(?=\n-- q\d+\n|\Z)", "", t, flags=re.S))
    p = os.path.join(d, "questions_baseline.json")
    b = json.load(open(p))
    del b[qid]
    json.dump(b, open(p, "w"), indent=1, sort_keys=True)


# (name, setup before the base commit, mutation after it, must pass?, expected text if it must fail). All compare against HEAD.
HISTORY_CASES = [
    ("a commit compared with itself passes", None, lambda d: None, True, []),
    ("two notes on one id, compared with itself, pass", two_notes, lambda d: None, True, []),
    ("two notes on one id: one is edited", two_notes, lambda d: edit(d, "questions_changelog.yml", lambda t: t.replace("note number 2 for q05", "note number 2 for q05, quietly reworded")), False, ["q05", "edited or removed"]),
    ("two notes on one id: one is deleted", two_notes, lambda d: edit(d, "questions_changelog.yml", lambda t: t.replace(note("q05", 2), "")), False, ["q05", "edited or removed"]),
    ("two identical notes on one id: one is deleted", lambda d: open(os.path.join(d, "questions_changelog.yml"), "a").write(note("q05", 1) * 2), lambda d: edit(d, "questions_changelog.yml", lambda t: t.replace(note("q05", 1), "", 1)), False, ["q05", "edited or removed"]),
    ("a question is deleted from both files, the key AND the baseline", None, lambda d: delete_everywhere(d, "q10"), False, ["q10", "existed at HEAD but is gone"]),
    ("two notes on one id: a third is appended", two_notes, lambda d: open(os.path.join(d, "questions_changelog.yml"), "a").write(note("q05", 3)), True, []),
]


def main():
    bad = []
    for name, pre, mutate, should_pass, expect in HISTORY_CASES:
        d = sandbox(pre)
        mutate(d)
        rc, out = run(d, "--against", "HEAD")
        good = (rc == 0 and "PASS" in out) if should_pass else (rc != 0 and all(e in out for e in expect) and (out.count("was edited or removed") == 1 or "but is gone" in out))  # exactly the one entry we touched
        print(("PASS  " if good else "FAIL  ") + f"{name}: {'accepted' if rc == 0 else 'rejected'}")
        if not good:
            bad.append(name)
            print(out)
        shutil.rmtree(d)
    d = sandbox()
    rc, out = run(d)
    ok = rc == 0 and "PASS" in out
    print(("PASS  " if ok else "FAIL  ") + f"real files pass: {out.strip()}")
    if not ok:
        bad.append("baseline")
    shutil.rmtree(d)
    for name, mutate, expect, extra in CASES:
        d = sandbox()
        if mutate:
            mutate(d)
        else:                                    # hide a change by rewriting the baseline too
            edit(d, "questions.yml", lambda t: t.replace("late-delivery rate, as a percentage", "late-delivery rate, as a ratio"))
            subprocess.run(["git", "add", "-A"], cwd=d, capture_output=True)
            subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "wording"], cwd=d, capture_output=True)
            base = json.load(open(os.path.join(d, "questions_baseline.json")))
            new = json.loads(subprocess.run([PY, "-c", "import append_only,json;print(json.dumps(append_only.current()))"], cwd=d, capture_output=True, text=True).stdout)
            base["q01"] = new["q01"]
            json.dump(base, open(os.path.join(d, "questions_baseline.json"), "w"), indent=1)
            extra = ["--against", "HEAD~1"]
        rc, out = run(d, *extra)
        good = rc != 0 and all(e in out for e in expect)
        print(("PASS  " if good else "FAIL  ") + f"{name}: {'caught' if rc else 'NOT caught'}")
        if not good:
            bad.append(name)
            print(out)
        shutil.rmtree(d)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
