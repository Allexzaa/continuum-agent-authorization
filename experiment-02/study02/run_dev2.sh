#!/usr/bin/env bash
# Dev round 2 (declared loop mode think_off): gemma4:12b gates re-run, then the persia-f16 payload-form probe. One model at a time.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
PY="$ROOT/voice-agent/.venv/bin/python3"; export PYTHONPATH="$ROOT/study02/src"
unload_except() { for m in $(ollama ps | awk 'NR>1 {print $1}'); do [ "$m" = "$1" ] || ollama stop "$m" >/dev/null 2>&1; done; sleep 3; }
run() { local model="$1" cases="$2" out="$3" trials="$4" conds="$5"; unload_except "$model"
  local avail need=30; avail=$(free -g | awk '/^Mem:/ {print $7}')
  ollama ps | awk 'NR>1 {print $1}' | grep -qx "$model" && need=15
  echo "=== $(date -u +%FT%TZ) START $model -> $out (available ${avail} GB, need ${need})"
  if [ "$avail" -lt "$need" ]; then echo "ABORT: only ${avail} GB available (need ${need})"; return 1; fi
  $PY study02/src/run_study.py --cases "$cases" --model "$model" --trials "$trials" --conditions $conds --out "$out" 2>&1 | grep -E "^wrote|Traceback|Error"
  echo "=== $(date -u +%FT%TZ) DONE"; }
run gemma4:12b study02/cases/dev_cases.jsonl study02/results/dev2_gemma12b 2 "B2 BPLUS C2 C2COARSE" || exit 1
run persia-f16:latest study02/cases/probe_cases.jsonl study02/results/probe_persia 4 "B2" || exit 1
unload_except ""
echo "=== ALL DONE $(date -u +%FT%TZ)"
