# Study 02 reproducibility bundle: provenance-aware authorization (held-out run)

Status: held-out run complete; preliminary; author-labeled (independent validation deferred). Preregistration `study02/STUDY02_PREREGISTRATION.md`, lock record `study02/LOCK_RECORD.md`, results `study02/RESULTS.md`.
Licenses: code MIT (`LICENSE`); reports, cases, oracle, run logs, tables CC BY 4.0 (`LICENSE-DATA.md`). The real Gmail, Calendar, Slack, notes, tasks, document and browser integrations are not included (stubs).
Model weights are not included (gemma4:12b via Ollama; persia-f16 is an unpublished fine-tune).

## Recompute the reported numbers from the raw records (no model needed; needs numpy)
```
python3 study02/src/score_study.py --cases study02/cases/heldout_cases.jsonl --oracle study02/oracle/heldout_oracle.jsonl --runs study02/results/heldout_gemma12b/runs.jsonl --out /tmp/gemma_scored.jsonl
python3 study02/src/score_study.py --cases study02/cases/heldout_cases.jsonl --oracle study02/oracle/heldout_oracle.jsonl --runs study02/results/heldout_persia/runs.jsonl --out /tmp/persia_scored.jsonl
python3 study02/analysis/analyze_heldout.py     # expects the scored files at study02/results/heldout_{gemma,persia}_scored.jsonl (shipped here; copy yours over them to compare)
PYTHONPATH=study02/src python3 -m unittest discover -s study02/tests    # 35 tests, needs `requests`
```
The scorer reads the oracle in a separate process from the runner; the policy code cannot reach the oracle (unit-tested).
## What is and is not reproducible
Run records are untruncated (every model round, planner call and request). Re-running the models needs the weights; sampling is not bit-exact across runs. Code hashes in the records refer to the unstubbed source; this bundle has stubs, so its file hashes differ.
Harness issues found during development are in `study02/BACKEND_ISSUES.md`; development rounds in `study02/DEV_CHANGELOG.md`.
