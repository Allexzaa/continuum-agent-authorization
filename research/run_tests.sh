#!/usr/bin/env bash
# Run the research harness tests with the project's venv (no GPU, no network, no live tools).
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHONPATH="$ROOT/research/src" "$ROOT/voice-agent/.venv/bin/python3" -m unittest discover -s research/tests -v 2>&1 | grep -v '^\[TOOL\]\|^\[LLM\]\|^\[PLAN\]'
