#!/usr/bin/env bash
# THE HELD-OUT RUN (primary arms, both models, one at a time), then the exploratory C2TOKEN arm. Run only from the locked commit (tag study02-prereg-v1).
# Resumable: re-running skips cells already written. Memory guard: 30 GB available to load a model, 15 GB if it is already loaded.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
PY="$ROOT/voice-agent/.venv/bin/python3"; export PYTHONPATH="$ROOT/study02/src"
CASES=study02/cases/heldout_cases.jsonl
unload_except() { for m in $(ollama ps | awk 'NR>1 {print $1}'); do [ "$m" = "$1" ] || ollama stop "$m" >/dev/null 2>&1; done; sleep 3; }
run() { local model="$1" out="$2" conds="$3"; unload_except "$model"
  local avail need=30; avail=$(free -g | awk '/^Mem:/ {print $7}')
  ollama ps | awk 'NR>1 {print $1}' | grep -qx "$model" && need=15
  echo "=== $(date -u +%FT%TZ) START $model -> $out [$conds] (available ${avail} GB, need ${need})"
  if [ "$avail" -lt "$need" ]; then echo "ABORT: only ${avail} GB available (need ${need}); re-run this script to resume"; return 1; fi
  $PY study02/src/run_study.py --cases "$CASES" --model "$model" --trials 2 --conditions $conds --resume --out "$out" 2>&1 | grep -E "^resume|^wrote|Traceback|Error"
  echo "=== $(date -u +%FT%TZ) DONE $model [$conds]"; }
run gemma4:12b study02/results/heldout_gemma12b "B2 BPLUS C2 C2COARSE" || exit 1
run persia-f16:latest study02/results/heldout_persia "B2 BPLUS C2 C2COARSE" || exit 1
echo "=== PRIMARY ARMS DONE $(date -u +%FT%TZ)"
run gemma4:12b study02/results/heldout_gemma12b_c2token "C2TOKEN" || exit 1
run persia-f16:latest study02/results/heldout_persia_c2token "C2TOKEN" || exit 1
unload_except ""
echo "=== ALL DONE $(date -u +%FT%TZ)"
