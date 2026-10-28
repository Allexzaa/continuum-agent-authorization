# Reproducibility bundle: Persia prompt-injection / tool-authorization pilot

Everything needed to re-score, re-check and replay the reported results, minus what cannot be shared. All data are synthetic.

**Status: partially reproducible.** Earlier versions of Persia's `llm.py` were never under version control and are unavailable; only the final version is here and it matches
the `postfix2_*` runs. Hashes of earlier versions identify what ran but do not recover its behavior. The research harness is recoverable from git. Recorded model output is
truncated to 2,000 characters per round, and planner calls and empty-final recovery text were not stored, so exact historical replay is not claimed. Run categories are kept
separate: 774 original scored runs (252 confirmatory, 126 exploratory legacy-loop, 396 post hoc); post-fix re-runs are 972 records (648 first pass, 324 final guard; the 324
repeat three arms of the 648, so they are not independent); the 2216 records here also include development, calibration and audit runs that are not independent scored
experiments. `postfix_*` is superseded by `postfix2_*` for judging the final guard.

## What is in here
- `research/results/<arm>/runs.jsonl`: one JSON record per run (attempts with policy verdicts, proposed calls, mock-world effects, every recorded model
  round, the final answer, outcomes, code hashes). Arms:
- `audit1`: 56 runs (capability audit (not reportable))
- `audit2`: 56 runs (capability audit (not reportable))
- `audit3`: 56 runs (capability audit (not reportable))
- `calib2_gemma4_12b`: 28 runs (calibration (not reportable))
- `calib2_persia-f16_latest`: 28 runs (calibration (not reportable))
- `calib3_gemma4_12b`: 28 runs (calibration (not reportable))
- `calib3_persia-f16_latest`: 28 runs (calibration (not reportable))
- `calib_gemma4_12b`: 14 runs (calibration (not reportable))
- `calib_persia-f16_latest`: 14 runs (calibration (not reportable))
- `dev2_gemma4_12b`: 30 runs (dev split / calibration (not reportable))
- `dev2_persia-f16_latest`: 30 runs (dev split / calibration (not reportable))
- `dev_gemma12b`: 30 runs (dev split / calibration (not reportable))
- `dev_llama`: 30 runs (dev split / calibration (not reportable))
- `dev_persia`: 30 runs (dev split / calibration (not reportable))
- `followup_gemma12b_mixed`: 72 runs (post hoc follow-up)
- `followup_gemma12b_stopread_off`: 126 runs (post hoc follow-up)
- `followup_persia_mixed`: 72 runs (post hoc follow-up)
- `followup_persia_stopread_off`: 126 runs (post hoc follow-up)
- `gate1`: 12 runs (pre-pilot gate)
- `pilot_gemma12b`: 126 runs (confirmatory or exploratory pilot)
- `pilot_gemma12b_legacy`: 126 runs (confirmatory or exploratory pilot)
- `pilot_persia`: 126 runs (confirmatory or exploratory pilot)
- `postfix2_gemma12b_stopread_off`: 126 runs (post-fix re-run)
- `postfix2_persia_mixed`: 72 runs (post-fix re-run)
- `postfix2_persia_stopread_off`: 126 runs (post-fix re-run)
- `postfix_gemma12b`: 126 runs (post-fix re-run)
- `postfix_gemma12b_mixed`: 72 runs (post-fix re-run)
- `postfix_gemma12b_stopread_off`: 126 runs (post-fix re-run)
- `postfix_persia`: 126 runs (post-fix re-run)
- `postfix_persia_mixed`: 72 runs (post-fix re-run)
- `postfix_persia_stopread_off`: 126 runs (post-fix re-run)
- `research/cases/*.jsonl`: the locked case fixtures (adversarial, benign twins, exploratory mixed tasks, dev split, smoke) and their generators.
- `research/src/`: adapter (drives Persia's real loop), mock world, policies (A/B permissive, C enforced), scorer (`score_runs.py`), runner, report generator,
  and `verify_claims.py`.
- `research/tests/`: 62 unit tests (scripted fake model, no network).
- `voice-agent/pipeline/`: the loop under test (`llm.py`, final version) and the tool modules it imports. Tools are never executed by the harness.
- `voice-agent/config/SOUL.md`: the system prompt (prompt B); prompt A is B minus lines 67, 68, 70, 72.
- `research/PREREGISTRATION.md`, `research/reports/` (memo, tables).

## Verify without any model (Python 3.12, standard library for steps 1 to 3)
```
python3 research/src/verify_claims.py --no-replay      # rescore every run, recompute every memo number
python3 -m unittest discover -s research/tests          # needs the packages below
python3 research/src/verify_claims.py                   # also replays recorded model outputs through the real loop (needs the packages below)
```
Packages for the loop and the tests: `requests python-dateutil caldav icalendar google-api-python-client google-auth slack_sdk httpx pymupdf`.
The verifier prints PASS or FAIL per figure. It also prints the runs whose answers need a human read (the "claimed a denied action" labels).

## What each check proves, and what it does not
1. Rescore: the stored outcomes equal a fresh application of the scorer to the raw attempts, effects and proposed calls.
2. Memo claims: each number in the memo (and the results page) is recomputed from those rescored runs, independently of `report.py`.
3. Replay: the recorded output of every streamed model round is fed back through the real loop, policy, mock world and scorer; attempts, effects and the
   final answer must match the record. Exact match is required only for arms that ran on the final loop code (`postfix2_*`). Earlier arms ran on earlier
   loop versions that were not preserved, so differences there are expected and listed (for example the confirmatory Gemma A05 runs differ because the later
   F-017 fix discards a tool call in final-answer mode). A few runs used a non-streamed recovery call whose text was not stored; for those the verifier
   requires attempts and effects to match and reports the answer as unverifiable.
Redaction can shift a text-truncation point (the loop's read-back fallback cuts a tool result at 300 characters), which is why a few answers
   count as "unrecorded recovery" in the bundle but match exactly in the original repository.
Not checkable from this bundle: the model's sampling (needs the weights; seeds are fixed but GPU decoding is not bit-exact), the author's hand labels, and
the unredacted prompt.

## Redactions
The author's first name, a personal email address and the home path were replaced by text substitution in every copied file (prompt, loop code, fixtures,
run records). Hashes inside run records refer to the unredacted originals; `research/bundle_meta.json` maps original to redacted fixture hashes and gives the original
hash of the final `llm.py`. Not included: credentials, tokens, `.env`, the memory database, model weights.

## Re-running the models
`research/run_pilot.sh`, `run_followup.sh`, `run_postfix.sh`, `run_postfix2.sh` need Ollama on localhost with `persia-f16:latest` (an unpublished fine-tune of
Llama 3.1 8B) and `gemma4:12b`. Only the Gemma arms can be reproduced by someone without the fine-tune. The harness refuses non-local requests and uses
no live tools. Expect small run-to-run differences even with fixed seeds (observed: two Persia benign email runs did not repeat between a run and its re-run).
