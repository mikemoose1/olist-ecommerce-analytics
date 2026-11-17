#!/usr/bin/env bash
# Read-only health check: is this checkout + warehouse worth verifying against?
set -uo pipefail
cd "$(dirname "$0")/.."
ok=1
say(){ printf '%-34s %s\n' "$1" "$2"; }
[ -x .venv/bin/dbt ] && say "venv + dbt" "$(.venv/bin/dbt --version 2>/dev/null | awk '/installed/{print $3; exit}')" || { say "venv + dbt" "MISSING (run make setup)"; ok=0; }
if [ -d data/raw ]; then
  bad=$(tail -n +2 seeds/raw_file_manifest.csv | while IFS=, read -r f s; do [ "$(sha256sum data/raw/$f 2>/dev/null | cut -d' ' -f1)" = "$s" ] || echo "$f"; done)
  [ -z "$bad" ] && say "raw CSV hashes" "9/9 match manifest" || { say "raw CSV hashes" "MISMATCH: $bad"; ok=0; }
else say "raw CSV hashes" "data/raw missing (run make setup)"; ok=0; fi
if [ -f olist.duckdb ]; then
  .venv/bin/python - <<'PY' || ok=0
import duckdb, sys
c = duckdb.connect("olist.duckdb", read_only=True)
try:
    n = c.execute("select count(*) from marts.fct_orders").fetchone()[0]
    h = c.execute("select value_pct, rule from metrics.metrics_headline where is_headline").fetchone()
    print(f"{'warehouse fct_orders rows':34s} {n}"); print(f"{'headline repeat_rate_90d':34s} {h[0]}% ({h[1]})")
    sys.exit(0 if n == 99441 else 1)
except Exception as e:
    print(f"{'warehouse':34s} NOT BUILT ({e.__class__.__name__}); run make build"); sys.exit(1)
PY
else say "warehouse" "olist.duckdb missing (run make build)"; ok=0; fi
lsof olist.duckdb >/dev/null 2>&1 && { say "warehouse lock" "IN USE by another process"; ok=0; } || say "warehouse lock" "free"
[ $ok = 1 ] && echo "DOCTOR: OK" || { echo "DOCTOR: NOT READY"; exit 1; }
