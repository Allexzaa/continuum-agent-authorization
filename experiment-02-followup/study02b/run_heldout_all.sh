#!/usr/bin/env bash
# Held-out run for Study 02b, in the pre-stated order. Each stage begins with the automatic 30-run early check (run_checked.sh) and aborts on failure.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
C=study02b/cases/heldout_cases.jsonl
study02b/run_checked.sh held1 $C "BPLUS C2 C2COARSE" gemma4:12b || { echo "=== ABORT stage 1"; exit 1; }
study02b/run_checked.sh heldtok $C "C2TOKEN" gemma4:12b || { echo "=== ABORT stage 2"; exit 1; }
study02b/run_checked.sh held1 $C "BPLUS C2 C2COARSE" persia-f16:latest || { echo "=== ABORT stage 3"; exit 1; }
study02b/run_checked.sh heldtok $C "C2TOKEN" persia-f16:latest || { echo "=== ABORT stage 4"; exit 1; }
echo "=== ALL STAGES DONE $(date -u +%FT%TZ)"
