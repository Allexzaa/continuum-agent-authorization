# Study 02b reproducibility bundle: usability cost of lineage-aware authorization (held-out run)

Status: held-out run complete; preliminary; author-labeled (independent validation deferred). Preregistration `study02b/PREREGISTRATION_v0.md` + `PREREGISTRATION_v1.md`, lock record `study02b/LOCK_RECORD.md`, results `study02b/RESULTS.md`.
Licenses: code MIT (`LICENSE`); reports, cases, oracle, run logs, tables CC BY 4.0 (`LICENSE-DATA.md`). The real Gmail, Calendar, Slack, notes, tasks, document and browser integrations are not included (stubs).
Model weights are not included (gemma4:12b via Ollama; persia-f16 is an unpublished fine-tune).

## Recompute the reported numbers from the raw records (no model needed; needs numpy)
```
for t in held1_gemma heldtok_gemma held1_persia heldtok_persia; do
  python3 study02/src/score_study.py --cases study02b/cases/heldout_cases.jsonl --oracle study02b/oracle/heldout_oracle.jsonl --runs study02b/results/$t/runs.jsonl --out /tmp/${t}_scored.jsonl
done
python3 study02b/analysis/analyze_followup.py    # reads study02b/results/*_scored.jsonl (shipped here; copy yours over them to compare)
python3 study02b/analysis/supplement.py
PYTHONPATH=study02/src:study02b/src python3 -m unittest discover -s study02b/tests      # case-builder tests
PYTHONPATH=study02/src python3 -m unittest discover -s study02/tests                      # harness tests, needs `requests`
```
The scorer reads the oracle in a separate process from the runner; the policy code cannot reach the oracle (unit-tested).
## What is and is not reproducible
Run records are untruncated (every model round, planner call and request). Re-running the models needs the weights; sampling is not bit-exact across runs. Code hashes in the records refer to the unstubbed source; this bundle has stubs, so its file hashes differ.
Development rounds and case-wording fixes are in `study02b/DEV_CHANGELOG.md`.
