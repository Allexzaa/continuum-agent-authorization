#!/usr/bin/env bash
# Dev round 2 addition: the promoted probe cases (explicit payload forms) across all four arms, both models, 2 seeds. One model at a time.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
PY="$ROOT/voice-agent/.venv/bin/python3"; export PYTHONPATH="$ROOT/study02/src"
unload_except() { for m in $(ollama ps | awk 'NR>1 {print $1}'); do [ "$m" = "$1" ] || ollama stop "$m" >/dev/null 2>&1; done; sleep 3; }
run() { local model="$1" out="$2"; unload_except "$model"
  local avail need=30; avail=$(free -g | awk '/^Mem:/ {print $7}')
  ollama ps | awk 'NR>1 {print $1}' | grep -qx "$model" && need=15
  echo "=== $(date -u +%FT%TZ) START $model -> $out (available ${avail} GB, need ${need})"
  if [ "$avail" -lt "$need" ]; then echo "ABORT: only ${avail} GB available (need ${need})"; return 1; fi
  $PY study02/src/run_study.py --cases study02/cases/probe_cases.jsonl --model "$model" --trials 2 --out "$out" 2>&1 | grep -E "^wrote|Traceback|Error"
  echo "=== $(date -u +%FT%TZ) DONE"; }
run persia-f16:latest study02/results/dev2b_persia || exit 1
run gemma4:12b study02/results/dev2b_gemma12b || exit 1
unload_except ""
echo "=== ALL DONE $(date -u +%FT%TZ)"
