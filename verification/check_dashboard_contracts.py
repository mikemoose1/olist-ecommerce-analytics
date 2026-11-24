"""Every table the Tableau dashboard reads has an enforced dbt contract, and the dashboard exposure lists all of them.

  python verification/check_dashboard_contracts.py            static check of models/exports/_exports.yml, then proof the static check can fail
  python verification/check_dashboard_contracts.py --prove    also proof that dbt itself fails when a column's type drifts (copies the
                                                               project and warehouse to a temp folder; about 1 minute; needs make build)

Static check: every model the dashboard reads has contract.enforced = true and a data_type on every column, and the exposure
tableau_late_delivery_dashboard depends on exactly those models. "Reads" = the export models dashboard/export_csv.py writes to
dashboard/data/, plus any warehouse table a script in dashboard/tableau/ selects from directly (found by scanning the scripts,
so a new direct read fails this check until it is added). The two checking scripts in CHECKERS are left out.
"""
import copy, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
YML = ROOT / "models" / "exports" / "_exports.yml"   # holds the exposure
SCHEMAS = ("staging", "intermediate", "marts", "metrics", "exports")
CHECKERS = {"numbers_check_v4.py", "click_expect.py"}   # these re-check the dashboard against the warehouse; they do not feed it
EXPOSURE = "tableau_late_delivery_dashboard"
sys.path.insert(0, str(ROOT / "dashboard"))
from export_csv import TABLES  # noqa: E402



def direct_reads():
    out = set()
    for f in sorted((ROOT / "dashboard" / "tableau").glob("*.py")):
        if f.name in CHECKERS: continue
        out |= set(re.findall(r"\b(?:%s)\.([a-z_][a-z0-9_]*)" % "|".join(SCHEMAS), f.read_text()))
    return out


READ_BY_DASHBOARD = {f"export_dash_{t}" for t in TABLES} | direct_reads()


def load_all():
    """Every model from every properties file under models/, plus the exposures (all in YML)."""
    doc = {"models": [], "exposures": []}
    for f in sorted((ROOT / "models").rglob("*.yml")):
        d = yaml.safe_load(f.read_text()) or {}
        doc["models"] += d.get("models", []); doc["exposures"] += d.get("exposures", [])
    return doc


def problems(doc):
    out = []
    models = {m["name"]: m for m in doc.get("models", [])}
    for name in sorted(READ_BY_DASHBOARD):
        m = models.get(name)
        if m is None:
            out.append(f"{name}: not described in any models/*.yml"); continue
        if not ((m.get("config") or {}).get("contract") or {}).get("enforced"):
            out.append(f"{name}: contract not enforced")
        untyped = [c["name"] for c in m.get("columns", []) if not c.get("data_type")]
        if untyped or not m.get("columns"):
            out.append(f"{name}: columns without data_type: {untyped or 'no columns listed'}")
    exp = {e["name"]: e for e in doc.get("exposures", [])}.get(EXPOSURE)
    if exp is None:
        out.append(f"exposure {EXPOSURE} missing")
    else:
        deps = {d.split("'")[1] for d in exp.get("depends_on", [])}
        if deps != READ_BY_DASHBOARD:
            out.append(f"exposure {EXPOSURE}: missing {sorted(READ_BY_DASHBOARD - deps)}, extra {sorted(deps - READ_BY_DASHBOARD)}")
    return out


def selftest(doc):
    """Each planted mistake must be caught."""
    def m(name, d): return next(x for x in d["models"] if x["name"] == name)
    cases = {
        "contract switched off": lambda d: m("export_dash_region", d)["config"]["contract"].update(enforced=False),
        "one column untyped": lambda d: m("export_dash_sellers", d)["columns"][0].pop("data_type"),
        "direct-read table loses its contract": lambda d: m("fct_order_items", d).pop("config"),
        "exposure misses a table": lambda d: next(e for e in d["exposures"] if e["name"] == EXPOSURE)["depends_on"].pop(),
        "exposure removed": lambda d: d.pop("exposures"),
    }
    ok = True
    for label, mutate in cases.items():
        d = copy.deepcopy(doc); mutate(d)
        caught = bool(problems(d)); ok &= caught
        print(("PASS " if caught else "FAIL ") + f"selftest: {label} is caught")
    return ok


def prove():
    """dbt must PASS on an untouched copy and FAIL when export_dash_region.late_rate is declared varchar."""
    dbt = Path(sys.executable).parent / "dbt"
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        for item in ("models", "macros", "seeds", "dbt_packages", "dbt_project.yml", "profiles.yml", "packages.yml", "package-lock.yml"):
            src = ROOT / item
            if src.is_dir(): shutil.copytree(src, t / item)
            elif src.exists(): shutil.copy(src, t / item)
        db = Path(os.environ.get("OLIST_DB_PATH", ROOT / "olist.duckdb"))
        shutil.copy(db, t / "olist.duckdb")
        env = dict(os.environ, DBT_PROFILES_DIR=str(t), OLIST_DB_PATH=str(t / "olist.duckdb"))
        run = lambda: subprocess.run([str(dbt), "run", "-s", "export_dash_region", "--quiet"], cwd=t, env=env, capture_output=True, text=True)
        base = run()
        y = t / "models" / "exports" / "_exports.yml"; doc = yaml.safe_load(y.read_text())
        col = next(c for c in next(x for x in doc["models"] if x["name"] == "export_dash_region")["columns"] if c["name"] == "late_rate")
        col["data_type"] = "varchar"; y.write_text(yaml.safe_dump(doc, sort_keys=False))
        bad = run()
        out = base.stdout + base.stderr + bad.stdout + bad.stderr
        ok_base = base.returncode == 0
        ok_bad = bad.returncode != 0 and "contract" in (bad.stdout + bad.stderr).lower()
        print(("PASS " if ok_base else "FAIL ") + "prove: dbt run passes on the untouched copy")
        print(("PASS " if ok_bad else "FAIL ") + "prove: dbt run fails with a contract error when late_rate is declared varchar")
        if not (ok_base and ok_bad): print(out[-3000:])
        return ok_base and ok_bad


if __name__ == "__main__":
    doc = load_all()
    found = problems(doc)
    for p in found: print("FAIL " + p)
    if not found: print(f"PASS {len(READ_BY_DASHBOARD)}/{len(READ_BY_DASHBOARD)} tables the dashboard reads have enforced contracts and are in the {EXPOSURE} exposure: {', '.join(sorted(READ_BY_DASHBOARD))}")
    ok = not found and selftest(doc)
    if "--prove" in sys.argv: ok = prove() and ok
    sys.exit(0 if ok else 1)
