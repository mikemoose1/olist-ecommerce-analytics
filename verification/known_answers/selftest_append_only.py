#!/usr/bin/env python3
"""Mutation proof for append_only.py: each way of breaking the append-only rule must fail, and the real files must pass."""
import json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
FILES = ["append_only.py", "key_file.py", "questions.yml", "questions_reworded.yml", "answer_key.sql", "questions_baseline.json", "questions_changelog.yml"]


def sandbox(pre=None):
    d = tempfile.mkdtemp(prefix="appendonly-")
    for f in FILES:
        if os.path.exists(os.path.join(HERE, f)):      # key_file.py does not exist before the M1 fix; the proof runs there too
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
    # M1: score.py and append_only.py read answer_key.sql with one parser, so a header only one of them sees cannot exist
    ("a malformed key header '--q25' is appended", lambda d: open(os.path.join(d, "answer_key.sql"), "a").write("\n--q25\nselect 'XX';\n"), ["looks like a header"], ["--against", "HEAD"]),
    ("a key block for an id no question has is appended", lambda d: open(os.path.join(d, "answer_key.sql"), "a").write("\n-- q25\nselect 'XX';\n"), ["q25", "no question file has"], []),
    ("a second key block for q05 is appended", lambda d: open(os.path.join(d, "answer_key.sql"), "a").write("\n-- q05\nselect 1;\n"), ["second header for q05"], []),
    ("an indented key header is added", lambda d: edit(d, "answer_key.sql", lambda t: t.replace("-- q07\n", "-- q07\n  -- q07\n", 1)), ["looks like a header"], []),
    # L4: a decoy question with a real id placed before the real one (last-wins parsing used to hide it)
    ("a decoy q05 is placed before the real q05", lambda d: edit(d, "questions.yml", lambda t: t.replace("- id: q05\n", "- id: q05\n  question: decoy wording\n- id: q05\n", 1)), ["q05", "appears twice"], []),
    # M2: --against fails closed
    ("--against a rev that does not resolve", lambda d: None, ["does not resolve"], ["--against", "nosuchrev"]),
    # an empty --against (an unset CI variable) used to skip the history comparison
    ("--against an empty rev fails closed", lambda d: None, ["does not resolve"], ["--against", ""]),
    # 4b: a duplicate YAML key inside one question (the last one wins in a plain loader, hiding the first)
    ("a question entry with two 'question:' keys", lambda d: edit(d, "questions.yml", lambda t: t.replace("- id: q05\n", "- id: q05\n  question: decoy wording\n", 1)), ["duplicate key", "question"], []),
    ("a reworded entry with two 'forbidden_tables:' keys", lambda d: edit(d, "questions_reworded.yml", lambda t: t.replace('  forbidden_tables: ["metrics.*"]\n', '  forbidden_tables: ["metrics.*"]\n  forbidden_tables: []\n', 1)), ["duplicate key", "forbidden_tables"], []),
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


def pre_baseline_repo(after=None):
    """history: commit 1 has the questions but no baseline/changelog, commit 2 adds them (the true first-baseline case)"""
    d = sandbox()
    for c in (["git", "rm", "-q", "--cached", "questions_baseline.json", "questions_changelog.yml"],):
        subprocess.run(c, cwd=d, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "no baseline"], cwd=d, check=True, capture_output=True)
    subprocess.run(["git", "reset", "-q", "--soft", "HEAD~1"], cwd=d, check=True, capture_output=True)   # squash: root has no baseline
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "root without baseline"], cwd=d, check=True, capture_output=True)
    commit(d, "add baseline")
    if after:
        after(d)
    return d


def non_ancestor_repo():
    d = sandbox()
    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=d, check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "side"], cwd=d, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-q", "-"], cwd=d, check=True, capture_output=True)
    return d


def baseline_edit(d):
    p = os.path.join(d, "questions_baseline.json")
    b = json.load(open(p))
    b["q01"]["original"] = "0" * 16
    json.dump(b, open(p, "w"), indent=1, sort_keys=True)


# (name, repo builder, --against value, must pass?, expected text)
REV_CASES = [
    ("--against a commit that is not an ancestor of HEAD fails (force-push)", non_ancestor_repo, "side", False, ["not an ancestor"]),
    ("--against a commit from before the baseline existed compares with the first baseline commit and passes", lambda: pre_baseline_repo(), "HEAD~1", True, ["first added it"]),
    ("--against a pre-baseline commit still catches an edited baseline", lambda: pre_baseline_repo(baseline_edit), "HEAD~1", False, ["q01", "differs from the one at"]),
]


def main():
    bad = []
    for name, build, rev, should_pass, expect in REV_CASES:
        d = build()
        rc, out = run(d, "--against", rev)
        good = (rc == 0) == should_pass and all(e in out for e in expect)
        print(("PASS  " if good else "FAIL  ") + f"{name}: {'accepted' if rc == 0 else 'rejected'}")
        if not good:
            bad.append(name)
            print(out)
        shutil.rmtree(d)
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
    # the revision reproduce.sh hands the guard. An empty APPEND_ONLY_BASE (CI's first push of a new branch)
    # must not quietly become HEAD (which undid the fail-closed --against ""): it means origin/main, or "" when there is none
    repro = os.path.join(HERE, "..", "..", "scripts", "reproduce.sh")
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "scripts"))
    shutil.copy(repro, os.path.join(d, "scripts"))
    for c in (["git", "init", "-q"], ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x"]):
        subprocess.run(c, cwd=d, check=True, capture_output=True)
    def base(value, origin_main):
        if origin_main:
            subprocess.run(["git", "update-ref", "refs/remotes/origin/main", "HEAD"], cwd=d, check=True)
        env = {k: v for k, v in os.environ.items() if k != "APPEND_ONLY_BASE"}
        if value is not None:
            env["APPEND_ONLY_BASE"] = value
        p = subprocess.run(["bash", os.path.join(d, "scripts", "reproduce.sh"), "append_base"], cwd=d, env=env, capture_output=True, text=True)
        return p.stdout.strip() if p.returncode == 0 else f"error {p.returncode}: {p.stderr.strip()[-80:]}"
    for name, value, origin_main, want in (("unset (a local run) compares with HEAD", None, False, "HEAD"),
                                           ("a CI base commit is used as given", "abc123", False, "abc123"),
                                           ("empty with no origin/main gives '' (the guard fails closed)", "", False, ""),
                                           ("empty with origin/main compares with origin/main", "", True, "origin/main")):
        got = base(value, origin_main)
        print(("PASS  " if got == want else "FAIL  ") + f"reproduce.sh append_base: {name}: got {got!r}")
        if got != want:
            bad.append(name)
    shutil.rmtree(d)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
