#!/usr/bin/env bash
# Download the nine raw Olist CSVs from the Hugging Face mirror and verify their sha256
# against seeds/raw_file_manifest.csv. Idempotent: files already present are only re-verified.
set -euo pipefail
cd "$(dirname "$0")/.."
RAW="${OLIST_RAW_DIR:-data/raw}"
BASE="https://huggingface.co/datasets/bulutttt/olist-raw-data/resolve/main"
mkdir -p "$RAW"
tail -n +2 seeds/raw_file_manifest.csv | while IFS=, read -r f sha; do
  if [ ! -s "$RAW/$f" ]; then
    echo "downloading $f"
    curl -fsSL --retry 3 -o "$RAW/$f.part" "$BASE/$f" && mv "$RAW/$f.part" "$RAW/$f"
  fi
  got=$(sha256sum "$RAW/$f" | cut -d' ' -f1)
  if [ "$got" != "$sha" ]; then echo "HASH MISMATCH $f: got $got want $sha" >&2; exit 1; fi
  echo "ok $f"
done
