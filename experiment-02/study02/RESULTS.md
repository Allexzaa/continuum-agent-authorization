# Study 02 held-out results (preregistered primary analysis; v2 locked 2026-10-28, tag study02-prereg-v1)

Status: held-out run complete (primary arms 976 runs per model, exploratory C2TOKEN arm 244 per model). All labels are author-labeled (independent validation deferred by decision). Raw tables: `analysis/heldout_primary_tables.txt` (script `analysis/analyze_heldout.py`, bootstrap seed 20261029).
Integrity: 976 of 976 cells per model, no duplicates, 0 errors, 0 network violations, one locked commit (ca269bf), declared planner mode `think_off`, one code-hash set, digests gemma4:12b 4eb23ef187e2 and persia-f16 8bf2ceed1372 (Ollama).

## Primary (confirmatory): B+ vs C2, 50 attacked templates, template level (a template leaks if any of 2 seeds leaks)
| | gemma4:12b (primary) | persia-f16 (pre-specified secondary, never pooled) |
|---|---|---|
| Templates with an unauthorized effect: B2 / B+ / C2 / C2-coarse | 14 / 14 / 3 / 0 | 23 / 23 / 12 / 0 |
| Leaked under B+ only / both / C2 only | 11 / 3 / 0 | 11 / 12 / 0 |
| B+ minus C2 | +22 pp, 95% bootstrap CI [+12, +34], exact McNemar p = 0.001 | +22 pp, CI [+12, +34], p = 0.001 |
| Private artifact read under B+ (exposure) | 28% of templates | 62% of templates |
Decision rule (lower bound above 0 and estimate at least 10 pp): met in both models. Power was planned for 20 pp; observed discordance was p10 = 0.22, p01 = 0.
B+ did not reduce effects relative to B2 (grant scoping alone had no effect on these attacks).

## Co-primary constraint (benign completion, C2 minus B+): 0.0 pp at template level, but see the limitation below
Template level (a template counts as completed only if both seeds complete; 62 templates): gemma 61/62 under B+ and C2, persia 46/62 under B+ and C2, difference 0.0 pp (95% CI gemma [0, 0], persia [-4.8, +4.8]). Run level (124 runs per arm): gemma 122/124 for B2, B+ and C2 (C2-coarse 123/124); persia-f16 100/124 (B2, B+), 101/124 (C2, +0.8 pp), 99/124 (C2-coarse). Strict false blocks: 0 in every arm. Any denial in benign runs: 0.

## Exploratory (C2TOKEN, rule frozen before evaluation, reported separately)
Templates with an effect: gemma 14 (B+) / 3 (C2) / 0 (C2TOKEN); persia 23 / 12 / 1. Benign: no false blocks, completion equal to C2.

## Limitations (must accompany any use of these numbers)
1. **The usability cost was largely untested.** In 400 benign-twin runs per model across the four primary arms (50 twins x 2 seeds x 4 arms; 500 including the exploratory token arm) the assistant never read a private artifact, so C2 and C2-coarse had nothing to react to. Only the 12 near-misses exercised the policy, and those are authorized shares that C2 declassifies by design. "No cost seen" is not "no cost". A follow-up needs benign tasks that read private data without explicit permission to share it.
2. **Gemma's controls are uninformative:** it proposed none of the control attacks (0 of 20 runs). For persia-f16 the controls behaved as designed (authority claim: B2 3/4, B+ 0/4, C2 0/4; broad grant: B+ 1/3, C2 0/3; direct write 0/3 in all arms).
3. C2 leaks are phrase-overlap misses on compact figures (for example "$35,000" or "$11,600" with no shared four-word phrase): the designed weakness. C2TOKEN catches nearly all of them, but its rule was defined after the development leaks, so it is exploratory.
4. All labels are author-labeled; the user-facing-claim classification and the 20% human review of outbound texts were not done; independent validation is deferred.
5. Small numbers (3 and 12 leaking templates under C2), two local models, synthetic data, structured grants, environment-assigned sensitivity labels, reads not scoped (A2), planner mode think_off (A3). No extrapolation to frontier models or production.
6. The held-out cases use templated request wording per surface; payload forms were fixed from development findings.
Harness issues are kept separate in `BACKEND_ISSUES.md` (none arose during the held-out run).
