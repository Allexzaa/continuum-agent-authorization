#!/usr/bin/env bash
# Second post-fix run (guard refined to speak only when the answer touches the failed action; plain failure report on an empty final):
# the three arms that contain failed writes, written to results/postfix2_*. Exploratory.
# Same memory safeguards as run_pilot.sh: one model loaded at a time, 30 GB free-memory guard, unload at the end.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/voice-agent/.venv/bin/python3"
export PYTHONPATH="$ROOT/research/src"
MIN_AVAILABLE_GB=30

unload_except() {
  for m in $(ollama ps | awk 'NR>1 {print $1}'); do
    [ "$m" = "$1" ] || ollama stop "$m" >/dev/null 2>&1
  done
  sleep 3
}

run() { # model out_dir "case files" [extra args]
  local model="$1" out="$2" cases="$3"; shift 3
  unload_except "$model"
  local avail; avail=$(free -g | awk '/^Mem:/ {print $7}')
  echo "=== $(date -u +%FT%TZ) START $model -> $out $* (available memory ${avail} GB)"
  if [ "$avail" -lt "$MIN_AVAILABLE_GB" ]; then echo "ABORT: only ${avail} GB available (< ${MIN_AVAILABLE_GB} GB)."; return 1; fi
  $PY research/src/run_eval.py --cases $cases --conditions A B C --trials 3 --model "$model" --out "$out" "$@" 2>&1 | grep -E "^\[[0-9]+/|^wrote|Traceback|Error"
  echo "=== $(date -u +%FT%TZ) DONE  $model (available memory $(free -g | awk '/^Mem:/ {print $7}') GB)"
}

PILOT="research/cases/adversarial.jsonl research/cases/benign.jsonl"
EXPL="research/cases/exploratory.jsonl"
run persia-f16:latest research/results/postfix2_persia_stopread_off "$PILOT" --stop-on-read off || exit 1
run persia-f16:latest research/results/postfix2_persia_mixed "$EXPL" || exit 1
run gemma4:12b research/results/postfix2_gemma12b_stopread_off "$PILOT" --stop-on-read off || exit 1
unload_except ""
echo "=== ALL DONE $(date -u +%FT%TZ)"
