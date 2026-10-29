#!/usr/bin/env bash
# DIAGNOSTIC ONLY (not scored evidence): does Persia's plan-then-execute step explain why persia-f16 never reads the private artifacts?
# DA01-DA04, condition B2, seeds 0-3. persia: production vs planner off. gemma: production vs think_off (planner repaired) vs off. One model at a time.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
PY="$ROOT/voice-agent/.venv/bin/python3"; export PYTHONPATH="$ROOT/study02/src"
unload_except() { for m in $(ollama ps | awk 'NR>1 {print $1}'); do [ "$m" = "$1" ] || ollama stop "$m" >/dev/null 2>&1; done; sleep 3; }
run() { local model="$1" mode="$2" out="$3"; unload_except "$model"
  [ -s "$out/runs.jsonl" ] && { echo "=== skip $out (already complete)"; return 0; }
  local avail need=30; avail=$(free -g | awk '/^Mem:/ {print $7}')
  # the guard protects against LOADING a model into too little memory; a model that is already loaded needs no extra headroom (backend issue B8)
  ollama ps | awk 'NR>1 {print $1}' | grep -qx "$model" && need=15
  echo "=== $(date -u +%FT%TZ) START $model planner=$mode (available ${avail} GB, need ${need})"
  if [ "$avail" -lt "$need" ]; then echo "ABORT: only ${avail} GB available (need ${need})"; return 1; fi
  $PY study02/src/run_study.py --cases study02/cases/dev_cases.jsonl --only DA01 DA02 DA03 DA04 --conditions B2 --trials 4 --model "$model" --planner "$mode" --out "$out" 2>&1 | grep -E "^wrote|Traceback|Error"
  echo "=== $(date -u +%FT%TZ) DONE"; }
run persia-f16:latest production study02/results/diag_persia_production || exit 1
run persia-f16:latest off study02/results/diag_persia_off || exit 1
run gemma4:12b production study02/results/diag_gemma_production || exit 1
run gemma4:12b think_off study02/results/diag_gemma_thinkoff || exit 1
run gemma4:12b off study02/results/diag_gemma_off || exit 1
unload_except ""
echo "=== ALL DONE $(date -u +%FT%TZ)"
