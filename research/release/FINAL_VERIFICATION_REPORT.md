# Final verification report: Experiment 1 release

Bundle checked: `reproducibility_bundle`. No model was run for this report.

| Check | Result | Detail |
|---|---|---|
| All original logs preserved unchanged (redaction only) | PASS | 32 arms, 2240 records; mismatches: none; interrupted run included: True |
| Every published metric recomputed from the raw records (no replay) | PASS | SUMMARY: 71 checks passed, 0 failed |
| Same check plus replay of recorded model outputs through the loop, policy, world and scorer | PASS | SUMMARY: 74 checks passed, 0 failed |
| Unit tests | PASS | Ran 62 tests; OK |
| Published tables equal tables regenerated from the logs | PASS | original arms: 0 differing diff lines / post-fix arms: 0 differing diff lines |
| Recorded harness hashes match git history | PASS | 16 of 16 arms; dirty-flag exception: ['pilot_persia'] (recorded commit differs from the matching commit by the report script edit; execution modules verified identical) |
| Source needed for reproduction available, or its absence documented | PASS | agent loop preserved only for ['postfix2_persia_stopread_off', 'postfix2_persia_mixed', 'postfix2_gemma12b_stopread_off']; absence for the other 13 arms is stated in README.md and REPRODUCIBILITY.md |
| Original and post-fix results are distinguished | PASS | 774 original, 972 post-fix records, overlap statement present |
| Known limitations included | PASS | README Limits section; memo and page limits sections |
| Partial reproducibility disclosed | PASS | present in README, REPRODUCIBILITY, memo, page |
| No simulated result described as a real-world incident | PASS | flagged phrases: none |
| No unfinished experiment presented as completed | PASS | flagged: none (Experiment 1 documents do not mention Studies 02 or 03) |
| Released files contain only synthetic data; no credentials or personal data patterns | PASS | files with matches: none |
| SHA-256 manifest verifies | PASS | 121 files; mismatches: none |

**14 of 14 checks passed.**

## Unresolved gaps (not corrected, not hidden)

- Earlier versions of Persia's `llm.py` (pilot, follow-ups, first post-fix guard) were never under version control and are unavailable; hashes identify them but do not recover them.
- Recorded model rounds are truncated to 2,000 characters; planner calls and empty-final recovery text were not stored; exact historical replay is not claimed.
- The fine-tuned `persia-f16` weights are not part of the release; only the Gemma arms can be re-run by others.
- The 21 denial-run labels (5 inaccurate completion claims) are from one reader; the independent reading is pending (blind sheet prepared).
- The case set is small and hand-written; no adaptive attacker; condition C is oracle-scoped (an upper bound, not a deployable control).
- No license chosen; until one is added all rights are reserved. Reference audit is not applicable to this study's documents (no literature claims are made in them).
- Git tag for the release is created after the working tree is committed on the research branch.
