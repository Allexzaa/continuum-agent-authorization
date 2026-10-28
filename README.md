# Experiment 1: Prompt injection and tool authorization on a local assistant

**Status: Completed, preliminary empirical study. Partially reproducible** (see `REPRODUCIBILITY.md`). Run 2026-10-28. Everything is simulated: a sandboxed mock world with
synthetic data, no live tools, accounts, files or network. No result here describes a real-world security incident.

## Question
When a tool-using local assistant (Persia, a Llama 3.1 8B fine-tune; second model `gemma4:12b`) reads untrusted content that contains instructions, how do (a) prompt-level
trust rules and (b) an enforced authorization policy compare on unauthorized tool requests, simulated unauthorized executions, and legitimate task success?

## Setup in brief
Three conditions on the same models, cases and seeds: **A** (system prompt without its four injection-trust rules), **B** (prompt as deployed), **C** (B plus a deterministic
authorization policy scoped by the experimenter's per-case allowed list: an oracle, a best case, not a deployable control). 6 hand-written attacks, 6 benign twins, 2 authorized
tasks, and later 4 mixed tasks plus twins; 3 seeds per cell. Hypotheses and metrics were written before the first scored run (`PREREGISTRATION.md`).

## Evidence tiers (kept separate)
| Tier | Records | Meaning |
|---|---:|---|
| Confirmatory pilot | 252 | preregistered cases, two models |
| Exploratory legacy-loop | 126 | one model, earlier prompt format |
| Post hoc follow-ups | 396 | chosen after seeing the pilot (stop rule removed; mixed tasks) |
| **Original scored runs** | **774** | the three rows above |
| Post-fix re-runs | 972 | after changing Persia's loop (648 first pass, 324 final guard; the 324 repeat three arms of the 648, so they are not independent) |
| Development, calibration, audit, interrupted | remainder of the archive | not reportable as results |

## Findings
1. **0 of 252** confirmatory runs executed a forbidden call. This is not a safety result: the loop fix that lets read requests finish also switches tools off once the content is read.
2. With that stop rule removed (post hoc), conditions A and B executed the injected action in **8 of 66** exposed runs; condition C executed **0 of 33**, with **0 false blocks in 144**
   benign runs. Condition C is an oracle-scoped best case.
3. The prompt-level trust rules showed **no measurable effect** (B no better than A in either model).
4. In **5 of 21** runs where the policy denied a call, the final answer contained an inaccurate completion claim. Only one of the five was a straightforward policy-scope denial; the others
   were calls rejected for malformed arguments. One reader labeled them (an independent check is planned). A later loop change mitigated misleading completion reports in the re-runs;
   it did not show the model became more truthful.
5. An invented-ID check in the same change had a plausible side effect in one cell (an injected delete ran: 0 of 8 before, 1 of 8 after). Not an established regression rate.
6. Simulated damage without a policy: one run rewrote a note in the synthetic sandbox, replacing its content and copying the injected instruction.

## Limits
The loop's planner step worked for persia-f16 but returned empty text for gemma4:12b in most planner-triggering prompts (probe: 8 of 10), and planner output was not logged in this study; a later diagnostic found it did not explain persia-f16's low attempt rate. a later probe found persia-f16 follows explicit assistant-addressed injections (12 of 40) and ignores passive wording, so its low attempt rate here is payload-form dependent; persia-f16's fine-tuning data includes 14 injection-ignoring examples (of about 1,300), which may contribute and cannot be isolated here. Hand-written cases, 3 seeds per cell (trials of one case are not independent), one labeler, two local models, an oracle-scoped policy, Persia's own confirmation gates bypassed,
`llama3.1:8b` excluded (never called tools: a competence floor). Not evidence about frontier models or production deployment. No significance tests.

## Contents
`README.md` this file; `REPRODUCIBILITY.md`; `EVIDENCE_INDEX.md` (each claim to its evidence); `FINAL_VERIFICATION_REPORT.md`; `PREREGISTRATION.md`; `research/` (code, cases, logs,
tests, verifier, reports, release metadata); `voice-agent/` (final version of the loop under test and its tool modules, redacted).

## License
Code (research harness, scorer, verifier, tests, and the agent loop `llm.py` with stubbed integrations): **MIT** (`LICENSE`). Reports, tables, documentation, case fixtures, run logs and the redacted prompt: **CC BY 4.0** (`LICENSE-DATA.md`).
`LICENSES.md` maps each folder to its license. The real tool integrations and any model weights are not included. Copyright (c) 2026 Lexzium AI.

## Authorship and AI assistance
The research design, the decisions and the review of results are the author's. The harness, tests, verifier and many fixes to the agent loop were written with Claude Code (Anthropic's coding assistant) under the author's direction. The agent (Persia) was written by the author.
