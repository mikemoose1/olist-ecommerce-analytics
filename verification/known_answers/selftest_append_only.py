#!/usr/bin/env python3
"""Mutation proof for append_only.py: each way of breaking the append-only rule must fail, and the real files must pass."""
import json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
FILES = ["append_only.py", "questions.yml", "questions_reworded.yml", "answer_key.sql", "questions_baseline.json", "questions_changelog.yml"]


def sandbox():
    d = tempfile.mkdtemp(prefix="appendonly-")
    for f in FILES:
        shutil.copy(os.path.join(HERE, f), d)
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
    ("a new question is added but never adopted", lambda d: (edit(d, "questions.yml", lambda t: t + "- id: q23\n  question: How many sellers are there?\n")), ["q23", "not adopted"], []),
    ("the baseline is edited to match a changed question", None, ["differs from the one at"], ["--against", "HEAD"]),
    ("a changelog entry is deleted from history", lambda d: edit(d, "questions_changelog.yml", lambda t: "[]\n"), ["q09"], ["--against", "HEAD"]),
]


def main():
    bad = []
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
