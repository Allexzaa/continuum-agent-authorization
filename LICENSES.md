# Licenses in this release

| Material | License | File |
|---|---|---|
| Code: `research/src/`, `research/tests/`, `research/*.sh`, `research/cases/build_*.py`, `voice-agent/pipeline/llm.py`, `voice-agent/pipeline/*_tools.py` (stubs) | MIT | `LICENSE` |
| Reports, tables, documentation, preregistration, case fixtures (`research/cases/*.jsonl`), run logs (`research/results/`), release metadata, the redacted system prompt (`voice-agent/config/SOUL.md`) | CC BY 4.0 | `LICENSE-DATA.md` |

Not included and not licensed here: the real Gmail, Calendar, Slack, notes, tasks, document and browser integrations (the files under `voice-agent/pipeline/*_tools.py` are empty stubs), and any model weights.
The models used (persia-f16, a fine-tune of Llama 3.1 8B; gemma4:12b) are governed by their own terms; this release contains none of their weights. Run logs contain model outputs.
If you reuse the system prompt or logs with Llama-derived models, check the applicable model license for attribution requirements.

## Experiments 2 and 2 follow-up
`experiment-02/` and `experiment-02-followup/` follow the same split: code (`*/src/`, `*/tests/`, builders, scripts, stubs) is MIT (the `LICENSE` in each folder); reports, cases, oracle files, run logs, tables and documentation are CC BY 4.0 (the `LICENSE-DATA.md` in each folder). Copyright 2026 Lexzium AI. The same exclusions apply: no real integrations, no model weights.

## Logo
`assets/logo.png` is © 2026 Lexzium AI, all rights reserved. It is excluded from the MIT and CC BY 4.0 licenses that cover the rest of this repository.
