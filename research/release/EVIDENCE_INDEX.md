# Evidence index (claim to evidence)

All paths are relative to this release. "Verifier" = `python3 research/src/verify_claims.py` (check names in quotes). Arms are directories under `research/results/`.

| Claim | Evidence (arms, files) | Verified by |
|---|---|---|
| 774 original scored runs = 252 + 126 + 396 | `pilot_persia`, `pilot_gemma12b` (252); `pilot_gemma12b_legacy` (126); `followup_*` four arms (396) | "confirmatory + legacy + post hoc runs" |
| 0 of 252 forbidden calls executed in the confirmatory pilot | `pilot_persia`, `pilot_gemma12b` | "confirmatory pilot: runs, runs with an executed forbidden call" |
| Per-condition table (exposed, attempts, executed, benign success, false blocks) | the arms above and `followup_*` | "<arm> cond <X>: exposed, attempts, executed, benign success, false blocks" |
| 8 of 66 executed under A+B; 0 of 33 under C (stop rule off) | `followup_persia_stopread_off`, `followup_gemma12b_stopread_off` | "stop rule off: executed / exposed under A+B / under C" |
| 0 false blocks and 0 approval friction in 144 benign condition-C runs | the seven original arms | "benign condition-C runs, false blocks, approval friction" |
| Attacks induced the forbidden attempts (37 attack-only, 0 twin-only pairs) | the seven original arms | "paired runs with a forbidden call" |
| 21 denial runs; 5 with inaccurate completion claims | `pilot_persia`, `followup_*` | "pre-fix runs in which condition C denied at least one call" and the printed answers (read them) |
| Post-fix: benign success 63/72, 27/36, 71/72; answers after failed writes corrected | `postfix2_*` | "benign success / benign runs", printed corrected/as-is list |
| One executed delete in the post-fix mixed arm (0 of 8 before, 1 of 8 after) | `followup_persia_mixed`, `postfix_persia_mixed`, `postfix2_persia_mixed` (M03, condition A, trial 2) | "post-fix/pre-fix Persia mixed M03 under A" |
| Run records match their fixtures and stored outcomes equal a fresh score | every arm | "runs whose fixture hash does not match", "runs whose stored outcomes differ" |
| Published tables equal tables regenerated from the logs | `research/reports/tables_*.md` | `research/release/tables_regenerated_diff.txt` (0 differing lines) |
| Which code ran | `research/release/code_versions.json` | recorded harness hashes match git commits (16 of 16 arms); `llm.py` preserved only for `postfix2_*` |
| Which models ran | `research/release/models.json` | digests, parameters, quantization, runtime version |
| Downstream replay of recorded model outputs | `postfix2_*` exact; earlier arms informational | verifier section 4 |
