# Project CONTINUUM

**Can a tool-using AI assistant be kept to what its user actually authorized?**
Independent, preregistered experiments on prompt injection, tool authorization and data leakage, run on a local assistant in a simulated sandbox.

![License: MIT code](https://img.shields.io/badge/code-MIT-blue) ![License: CC BY 4.0 data](https://img.shields.io/badge/data%20%26%20reports-CC%20BY%204.0-lightgrey) ![Status](https://img.shields.io/badge/status-preliminary-orange) ![Preregistered](https://img.shields.io/badge/held--out%20runs-preregistered-brightgreen)

---

## Overview

AI assistants that read email, documents and web pages and then call tools (send a message, delete a note, write a file) can be steered by instructions hidden in the content they read. Telling the model to "ignore injected instructions" is a weak defense. This project asks what a *deterministic authorization layer* around the tool calls can and cannot do, and what it costs the legitimate user.

The system under test is **Persia**, the author's local, privacy-first voice assistant (a Llama 3.1 8B fine-tune, `persia-f16`), compared with a second local model, `gemma4:12b`. Both run through the real agent loop. Every tool is replaced by a **mock world with synthetic data**: no live accounts, files, network or real tools were touched, and no result describes a real-world incident.

Three studies have been completed. Each one starts from a limit found in the one before.

## The experiments at a glance

| | Question | Design | Headline result | Evidence |
|---|---|---|---|---|
| **[Experiment 1](EXPERIMENT_01.md)**<br>Prompt injection and tool authorization | Do prompt-level trust rules or an enforced authorization policy stop injected tool calls? | 3 conditions, 2 models, 774 original scored runs (plus post-fix re-runs) | The policy executed **0 of 33** injected actions vs **8 of 66** under prompt rules alone. The prompt rules showed **no measurable effect**. | Preliminary. The policy was scoped by the experimenter's answer key, so this is a best case, not a deployable control. |
| **[Experiment 2](experiment-02/)**<br>Provenance-aware authorization | If the policy knows only the user's grant, can tracking *where data came from* (lineage) cut leaks beyond argument-level permissions? | Preregistered, 122 fresh held-out templates, 4 arms, 2 models, 1,952 primary-arm runs | Templates leaking, argument scoping to lineage check: Gemma **14 to 3 of 50**, Persia **23 to 12 of 50** (+22 points, 95% CI +12 to +34, in each). | Preliminary. Confirmatory on the held-out set. Cost to legitimate tasks was largely untested here. |
| **[Experiment 2 follow-up](experiment-02-followup/)**<br>Usability cost of the lineage check | On tasks that *must* read a private note, how much legitimate work does the lineage check block? | Preregistered, 80 fresh cases (matched benign and attacked twins), 4 arms, 2 models, 1,280 runs | Gemma completed **40 of 40** tasks with argument scoping and **20 of 40** with the lineage check: all 20 yes/no tasks, **none of the 20 mixed-note** tasks (-50 points, 95% CI -65 to -35). | Preliminary. Cost confirmed as substantial for mixed notes. The leak comparison in Gemma is inconclusive (its attacks never worked). |
| *Experiment 3* | Does authorization survive a change of context? | Proposal only | None | No work done, no results. |

### What the three studies show, together
- An **enforced** authorization policy stops injected actions that prompt-level rules let through (Experiment 1).
- Tracking where data came from **reduces simulated leaks** beyond permissions alone, in both models (Experiment 2).
- That protection is **not free**: when a private label covers a whole note, the lineage check also blocks the public part of it, so every mixed-note task failed in Gemma (follow-up). Per-section labels are the obvious next test and have **not** been run.

### What they do not show
Everything is small, synthetic and **author-labeled** (the answer keys that define a leak or a completed task were written by one party, with Claude Code, and not independently reviewed). Two local models, one machine, templated cases, structured grants given to the policy as data. Not evidence about frontier models, real accounts or production systems. Each experiment's `RESULTS.md` and report list its own limits in full.

## How the studies are run

- **Preregistered.** Hypotheses, metrics and decision rules are written before the runs. Experiment 1 used hand-written pilot cases; Experiment 2 and its follow-up add pass/fail gates, fresh **held-out** cases fixed and hashed before the run, and a single locked run.
- **Separate answer key.** Scoring happens in a separate process that reads the oracle; the agent loop and the policy cannot see it (unit-tested).
- **Evidence tiers kept apart.** Confirmatory, exploratory and post hoc results are labeled and never pooled; the two models are analyzed separately.
- **Checked early.** The first 20 to 30 runs of every long run are inspected before it continues (automatic in the follow-up): errors, tool use, and whether the design actually reaches the mechanism being tested. A failed check stops the run, the cause is fixed, and the run restarts.
- **Harness problems are not model errors.** Backend and harness faults are logged separately (`BACKEND_ISSUES.md`, `DEV_CHANGELOG.md`), and a run is never counted as a model failure when the harness did not show the model what it needed.
- **Honest denominators.** n/N everywhere and no run excluded after the fact. Experiments 2 and the follow-up analyze at the template level (a bootstrap over templates and an exact paired test), because repeated seeds of one case are not independent.
- **Untruncated records.** Every model round, planner call and request is in the run logs, so each number can be traced back to a record.

## Repository layout

```
.
├── README.md                    this overview
├── EXPERIMENT_01.md             Experiment 1 summary, setup, findings and limits
├── PREREGISTRATION.md  EVIDENCE_INDEX.md  REPRODUCIBILITY.md  FINAL_VERIFICATION_REPORT.md
├── research/                    Experiment 1: harness, cases, run logs, scorer, tests, reports
├── voice-agent/                 the agent loop under test (llm.py) and stubbed tool modules
├── experiment-02/               Experiment 2 bundle
│   └── study02/                 cases, oracle, run logs, scorer, analysis, tests, RESULTS.md, preregistration
├── experiment-02-followup/      Experiment 2 follow-up bundle (repeats the Experiment 2 code it depends on)
│   └── study02b/                cases, oracle, run logs, analysis, tests, RESULTS.md, preregistrations v0 and v1
└── LICENSE  LICENSE-DATA.md  LICENSES.md
```

Start here:

| To see | Open |
|---|---|
| Experiment 1 results and evidence memo | [`EXPERIMENT_01.md`](EXPERIMENT_01.md), [`research/reports/evidence_memo.html`](research/reports/evidence_memo.html) |
| Experiment 2 results, limits and preregistration | [`study02/RESULTS.md`](experiment-02/study02/RESULTS.md), [`STUDY02_PREREGISTRATION.md`](experiment-02/study02/STUDY02_PREREGISTRATION.md) |
| Follow-up results, limits and preregistrations | [`study02b/RESULTS.md`](experiment-02-followup/study02b/RESULTS.md), [`PREREGISTRATION_v0.md`](experiment-02-followup/study02b/PREREGISTRATION_v0.md), [`PREREGISTRATION_v1.md`](experiment-02-followup/study02b/PREREGISTRATION_v1.md) |
| What went wrong along the way | [`BACKEND_ISSUES.md`](experiment-02/study02/BACKEND_ISSUES.md), [`DEV_CHANGELOG.md`](experiment-02-followup/study02b/DEV_CHANGELOG.md) |

## Reproduce the numbers

You do not need the models to recompute the reported tables: re-score the released run records. Each bundle has its own README with the full commands. For example, for the follow-up (needs Python 3 and `numpy`):

```bash
cd experiment-02-followup
sha256sum -c BUNDLE_MANIFEST.sha256          # verify every file
python3 study02/src/score_study.py \
  --cases study02b/cases/heldout_cases.jsonl \
  --oracle study02b/oracle/heldout_oracle.jsonl \
  --runs study02b/results/held1_gemma/runs.jsonl \
  --out /tmp/held1_gemma_scored.jsonl
python3 study02b/analysis/analyze_followup.py   # prints the preregistered tables
```

**What is and is not reproducible.** The model weights are not included (`gemma4:12b` is available through Ollama; `persia-f16` is an unpublished fine-tune), and sampling is not bit-exact across runs, so re-running the models gives similar but not identical records. The real Gmail, Calendar, Slack, notes, tasks and browser integrations are replaced by stubs; code hashes inside the run records refer to the unredacted source. Experiment 1 is **partially reproducible** (see [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md)).

## Licenses

- **Code** (harness, scorer, analysis, verifier, tests, and the agent loop `llm.py` with stubbed integrations): **MIT**, see [`LICENSE`](LICENSE).
- **Reports, tables, documentation, preregistrations, case fixtures, oracle files, run logs and the redacted prompt:** **CC BY 4.0**, see [`LICENSE-DATA.md`](LICENSE-DATA.md).
- [`LICENSES.md`](LICENSES.md) maps each folder to its license. Run logs contain model outputs; if you reuse them with Llama-derived models, check the applicable model license.

Copyright 2026 Lexzium AI.

## Authorship and AI assistance

The research design, the decisions and the review of results are the author's. The harness, tests, scorers, case library and many fixes to the agent loop were written with Claude Code (Anthropic's coding assistant) under the author's direction; the agent under test (Persia) was written by the author. The answer keys were authored by one party and not independently reviewed; independent labeling is deferred.

## Citing

> Lexzium AI. *Project CONTINUUM: authorization and control for a tool-using local assistant (Experiments 1, 2 and the Experiment 2 follow-up).* October 2026. https://github.com/Allexzaa/persia-injection-pilot-bundle. Licensed CC BY 4.0 (data and reports), MIT (code). Status: preliminary, author-labeled.

**Author:** Alex Zare, [LexZium](https://lexzium.com). Applied AI engineering, model evaluation, AI control.
