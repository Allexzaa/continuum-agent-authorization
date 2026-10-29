#!/usr/bin/env bash
# Checked run: for each model, run the first 30 runs, run the automatic early check, abort on failure, otherwise resume to completion.
# usage: run_checked.sh TAG CASES_FILE "CONDITIONS" [models...]     results go to study02b/results/TAG_<model>
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
PY="$ROOT/voice-agent/.venv/bin/python3"; export PYTHONPATH="$ROOT/study02/src"
TAG="$1"; CASES="$2"; CONDS="$3"; shift 3; MODELS=("${@:-gemma4:12b persia-f16:latest}")
[ $# -eq 0 ] && MODELS=(gemma4:12b persia-f16:latest)
unload_except() { for m in $(ollama ps | awk 'NR>1 {print $1}'); do [ "$m" = "$1" ] || ollama stop "$m" >/dev/null 2>&1; done; sleep 3; }
for model in "${MODELS[@]}"; do
  short=$([ "$model" = gemma4:12b ] && echo gemma || echo persia); OUT="study02b/results/${TAG}_${short}"
  unload_except "$model"
  avail=$(free -g | awk '/^Mem:/ {print $7}'); need=30; ollama ps | awk 'NR>1 {print $1}' | grep -qx "$model" && need=15
  echo "=== $(date -u +%FT%TZ) START $model -> $OUT (available ${avail} GB, need ${need})"
  if [ "$avail" -lt "$need" ]; then echo "ABORT: only ${avail} GB available (need ${need})"; exit 2; fi
  $PY study02b/src/run_followup.py --cases "$CASES" --model "$model" --conditions $CONDS --out "$OUT" --max-runs 30 --resume 2>&1 | grep -E "runs to do|^done|Traceback|Error"
  echo "--- early check ($model)"
  if ! $PY study02b/src/early_check.py --runs "$OUT/runs.jsonl" --cases "$CASES"; then echo "=== ABORT $(date -u +%FT%TZ): early check failed for $model; fix before re-running (partial records kept in $OUT, not to be scored)"; unload_except ""; exit 1; fi
  $PY study02b/src/run_followup.py --cases "$CASES" --model "$model" --conditions $CONDS --out "$OUT" --resume 2>&1 | grep -E "runs to do|^done|Traceback|Error"
  echo "=== $(date -u +%FT%TZ) DONE $model"
done
unload_except ""
echo "=== ALL DONE $(date -u +%FT%TZ)"
