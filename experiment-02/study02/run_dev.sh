#!/usr/bin/env bash
# Development preflight (gates G2/G3): 15 dev cases x 4 arms x 2 seeds per model, one model loaded at a time, 30 GB free-memory guard.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
PY="$ROOT/voice-agent/.venv/bin/python3"; export PYTHONPATH="$ROOT/study02/src"
TAG="${1:-dev}"; MODELS="${2:-both}"   # second argument: "gemma" runs only gemma4:12b
unload_except() { for m in $(ollama ps | awk 'NR>1 {print $1}'); do [ "$m" = "$1" ] || ollama stop "$m" >/dev/null 2>&1; done; sleep 3; }
run() { local model="$1" out="$2"; unload_except "$model"
  local avail; avail=$(free -g | awk '/^Mem:/ {print $7}')
  echo "=== $(date -u +%FT%TZ) START $model -> $out (available ${avail} GB)"
  if [ "$avail" -lt 30 ]; then echo "ABORT: only ${avail} GB available"; return 1; fi
  $PY study02/src/run_study.py --cases study02/cases/dev_cases.jsonl --model "$model" --trials 2 --out "$out" 2>&1 | grep -E "^\[[0-9]+/|^wrote|Traceback|Error"
  echo "=== $(date -u +%FT%TZ) DONE $model"; }
run gemma4:12b "study02/results/${TAG}_gemma12b" || exit 1
[ "$MODELS" = "gemma" ] || run persia-f16:latest "study02/results/${TAG}_persia" || exit 1
unload_except ""
echo "=== ALL DONE $(date -u +%FT%TZ)"
