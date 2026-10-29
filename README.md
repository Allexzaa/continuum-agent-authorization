<div align="center">

# Project CONTINUUM

**Can a tool-using AI assistant be kept to what its user actually authorized?**

Independent, preregistered experiments on prompt injection, tool authorization and data leakage,<br>run on a local assistant (**Persia**) in a simulated sandbox.

![Code: MIT](https://img.shields.io/badge/code-MIT-blue) ![Data and reports: CC BY 4.0](https://img.shields.io/badge/data%20%26%20reports-CC%20BY%204.0-lightgrey) ![Status: preliminary](https://img.shields.io/badge/status-preliminary-orange) ![Held-out runs preregistered](https://img.shields.io/badge/held--out%20runs-preregistered-brightgreen) ![Experiments: 3 completed](https://img.shields.io/badge/experiments-3%20completed-informational)

[Overview](#overview) · [Persia](#meet-persia-the-system-under-test) · [Experiments](#the-experiments) · [Method](#how-the-studies-are-run) · [Layout](#repository-layout) · [Reproduce](#reproduce-the-numbers) · [Limits](#what-the-studies-do-not-show) · [License](#licenses)

</div>

---

## Overview

AI assistants that read email, documents and web pages and then call tools (send a message, delete a note, write a file) can be steered by instructions hidden in the content they read. Telling the model to "ignore injected instructions" is a weak defense. This project asks what a **deterministic authorization layer** around the tool calls can and cannot do, and **what it costs the legitimate user**.

Everything runs against a **mock world with synthetic data**: no live accounts, files, network or real tools were touched, and no result describes a real-world incident. Three studies are complete, and each one starts from a limit found in the one before.

| | Study | In one line |
|---|---|---|
| 1 | [Prompt injection and tool authorization](#experiment-1--prompt-injection-and-tool-authorization) | An enforced policy stops injected actions that prompt rules let through. |
| 2 | [Provenance-aware authorization](#experiment-2--provenance-aware-authorization) | Tracking where data came from cuts simulated leaks by 22 points in two models. |
| 2b | [Usability cost of that check](#experiment-2-follow-up--usability-cost) | On tasks that need a private note, it also blocked half of the legitimate work. |

## Meet Persia, the system under test

**Persia** is the author's own local, privacy-first voice assistant, built for personal workflows and used here as a realistic test subject (a real agent loop with a real tool surface, not a toy).

| | |
|---|---|
| **Interaction** | Wake word "Hey Persia" (custom classifier), local voice activity detection (Silero), local speech-to-text (Faster-Whisper large-v3), local text-to-speech (Kokoro). Also reachable through a web UI, Telegram and Slack. Persistent memory in SQLite. |
| **Model** | `persia-f16`: a fine-tune of **Llama 3.1 8B** (F16), served locally through Ollama and fine-tuned toward valid tool calls and ReAct-style sequencing (reason, call a tool, read the result, continue). About 1,300 fine-tuning examples, 14 of which teach ignoring injected instructions. |
| **Tools** | Files and system search, calendars (Apple CalDAV, Google), Gmail, Google Tasks, Obsidian notes and to-dos, Slack, Telegram, a Chrome browser bridge, and PDF and document tools. |
| **Compared with** | `gemma4:12b`, a second local model run through the same loop. |

**What is in this repository.** Only the agent loop under test ([`voice-agent/pipeline/llm.py`](voice-agent/pipeline/llm.py)) and the redacted system prompt ([`voice-agent/config/SOUL.md`](voice-agent/config/SOUL.md)). The tool modules are stubs; the voice pipeline, the real integrations and the model weights are not included. The research harness drives the real loop against mock tools.

**What the studies found about Persia**
- It **mostly ignores passively worded injections but follows explicit ones** that address the assistant or name a tool (12 of 40 runs in a probe), so its low attack rate in Experiment 1 depended on payload wording and is not a general immunity.
- After a denied call it sometimes **told the user the task was done**: 5 of 21 denied-call runs ended with an inaccurate completion claim. A guard added to the loop now appends a correction when a final answer claims success the world does not support, and a check rejects invented record IDs.
- On tasks that require reading a private note, Persia **completed only 4 of 40 benign tasks even with no lineage check**: it copied the private section into the email, gave the wrong yes/no answer, or did not send. In this follow-up it was the only model the attacks worked on (25 of 40 attacked templates leaked under argument scoping; Gemma leaked in none).
- Findings like these are why the loop changed during the research. Every change is logged ([`DEV_CHANGELOG.md`](experiment-02-followup/study02b/DEV_CHANGELOG.md), [`BACKEND_ISSUES.md`](experiment-02/study02/BACKEND_ISSUES.md)), and harness faults are reported separately from model behavior.

This repository does **not** claim that Persia solves multi-step automation or is safe. It shows how it behaves under controlled attacks and one family of defenses.

## The experiments

### Experiment 1 · Prompt injection and tool authorization
[Full write-up](EXPERIMENT_01.md) · [evidence memo](research/reports/evidence_memo.html) · [preregistration](PREREGISTRATION.md) · [evidence index](EVIDENCE_INDEX.md)

- **Question.** Do prompt-level trust rules, or an enforced authorization policy, stop injected tool calls?
- **Design.** Three conditions (prompt without the trust rules, prompt as deployed, prompt plus an enforced policy), two models, hand-written attacks with benign twins, 3 seeds per cell. 774 original scored runs plus post-fix re-runs.
- **Result.** With the stop rule removed, the policy executed the injected action in **0 of 33** exposed runs against **8 of 66** under prompt rules alone. The prompt rules showed **no measurable effect**.
- **Read with care.** The policy was scoped by the experimenter's answer key, so this is a best case and not a deployable control. Partially reproducible.

### Experiment 2 · Provenance-aware authorization
[Results](experiment-02/study02/RESULTS.md) · [preregistration](experiment-02/study02/STUDY02_PREREGISTRATION.md) · [lock record](experiment-02/study02/LOCK_RECORD.md) · [bundle](experiment-02/)

- **Question.** If the policy knows only the user's grant, does tracking *where data came from* (lineage) cut leaks beyond argument-level permissions?
- **Design.** Preregistered, 122 fresh held-out templates (50 attacks, 50 benign twins, 12 near-misses, 10 controls), four policy arms, two models, 1,952 primary-arm runs.
- **Result.** Templates leaking under argument scoping versus the lineage check: **Gemma 14 to 3 of 50, Persia 23 to 12 of 50**. That is +22 points in each (95% CI +12 to +34, exact paired p = 0.001), analyzed separately.
- **Read with care.** Benign tasks almost never touched private data, so the cost to legitimate work was largely untested.

### Experiment 2 follow-up · Usability cost
[Results](experiment-02-followup/study02b/RESULTS.md) · [preregistration v0](experiment-02-followup/study02b/PREREGISTRATION_v0.md) and [v1](experiment-02-followup/study02b/PREREGISTRATION_v1.md) · [bundle](experiment-02-followup/)

- **Question.** On tasks that *must* read a private note, how much legitimate work does the lineage check block?
- **Design.** Preregistered, 80 fresh cases in matched benign and attacked pairs (20 mixed-note tasks, 20 yes/no tasks), four arms, two models, 1,280 runs. Gates written before any case; every stage checked after its first 30 runs.
- **Result.** In Gemma, benign tasks completed: **40 of 40** with argument scoping, **20 of 40** with the lineage check. That is −50 points (95% CI −65 to −35). All 20 yes/no tasks passed and **none of the 20 mixed-note tasks did**: the private label covers the whole note, so the public part looks private too.
- **Read with care.** Gemma never leaked in any arm, so the leak comparison there is inconclusive. Persia is exploratory (it failed the capability gate). Per-section labels were **not** tested.

### Experiment 3 · Proposed
Does authorization survive a change of context, such as a permission revoked while a task is queued? **Proposal only. No work done and no results.**

<details>
<summary><b>Glossary: arms and terms used above</b></summary>

| Term | Meaning |
|---|---|
| **B2** | Only the tools the request needs are allowed. |
| **B+** | B2 plus argument-level scoping of destinations and side effects (the baseline). |
| **C2** | B+ plus lineage: value origin and phrase overlap with private text (the primary arm). |
| **C2-coarse** | B+ plus "deny any send after a private read" (a conservative variant). |
| **C2-token** | C2 plus denying digits that occur only in private text (exploratory). |
| **Oracle-scoped policy** | Experiment 1's policy, scoped by the experimenter's per-case allowed list. |
| **Template** | One case plus its benign twin. The unit of analysis; repeated seeds are not independent. |
| **Held-out** | Cases fixed and hashed before the run, then run once. |
| **Author-labeled** | The answer keys were written by one party and not independently reviewed. |

</details>

## How the studies are run

- **Preregistered.** Hypotheses, metrics and decision rules are written before the runs. Experiment 1 used hand-written pilot cases; Experiment 2 and its follow-up add pass/fail gates, fresh **held-out** cases fixed and hashed before the run, and a single locked run.
- **Separate answer key.** Scoring happens in a separate process that reads the oracle; the agent loop and the policy cannot see it (unit-tested).
- **Evidence tiers kept apart.** Confirmatory, exploratory and post hoc results are labeled and never pooled; the two models are analyzed separately.
- **Checked early.** The first 20 to 30 runs of every long run are inspected before it continues (automatic in the follow-up): errors, tool use, and whether the design reaches the mechanism being tested. A failed check stops the run, the cause is fixed, and the run restarts.
- **Harness problems are not model errors.** Backend and harness faults are logged separately, and a run is never counted as a model failure when the harness did not show the model what it needed.
- **Honest denominators.** n/N everywhere and no run excluded after the fact. Experiment 2 and the follow-up analyze at the template level (a bootstrap over templates and an exact paired test).
- **Untruncated records.** Every model round, planner call and request is in the run logs, so each number can be traced back to a record.

## What the studies do not show

Everything is small, synthetic and **author-labeled**: the answer keys that define a leak or a completed task were written by one party, with Claude Code, and not independently reviewed. Two local models on one machine, templated cases, and structured grants given to the policy as data. Nothing here is evidence about frontier models, real accounts or production systems. Each experiment's results file lists its own limits in full.

**Next steps, not yet done:** per-section sensitivity labels for the lineage check (to test whether the cost disappears); independent labeling of a sample of answer keys; the Experiment 3 proposal.

## Repository layout

```
.
├── README.md                    this overview
├── EXPERIMENT_01.md             Experiment 1 summary, setup, findings and limits
├── PREREGISTRATION.md  EVIDENCE_INDEX.md  REPRODUCIBILITY.md  FINAL_VERIFICATION_REPORT.md
├── research/                    Experiment 1: harness, cases, run logs, scorer, tests, reports
├── voice-agent/                 the agent loop under test (llm.py), redacted prompt, stubbed tool modules
├── experiment-02/               Experiment 2 bundle
│   └── study02/                 cases, oracle, run logs, scorer, analysis, tests, results, preregistration
├── experiment-02-followup/      Experiment 2 follow-up bundle (repeats the Experiment 2 code it depends on)
│   └── study02b/                cases, oracle, run logs, analysis, tests, results, preregistrations v0 and v1
└── LICENSE  LICENSE-DATA.md  LICENSES.md
```

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
