# Study 02 lock record

Locked: 2026-10-28T20:46:04Z
Approval: the user (investigator), in writing in the project conversation, covering STUDY02_PREREGISTRATION.md (v2), the held-out registry v1, the declared loop (planner think_off) and the deferral of independent validation.

| Item | Value |
|---|---|
| Locked code, cases, oracle and preregistration commit (C1) | `1fa63877a58154bdff68a18d185cb34737249988` |
| SHA-256 of `STUDY02_PREREGISTRATION.md` | `593f8321e558cedd832d01f1e0e6d42f750162680fa2c271055efd4a3284c7cb` |
| SHA-256 of `review/HELDOUT_MANIFEST_LOCKED.json` | `95990708fece077e1fdc9e764fbc561fc6e1c111a12d63ce689452882cabb00a` |
| SHA-256 of `freeze/manifest.json` (generated at C1, clean tree) | `786464d4665b71cd947ad338f7be852a1402ec56034da995cde3f1f01e4ed059` |
| SHA-256 of `cases/heldout_cases.jsonl` | `8c72e27cc6f63c4988f81f8e1af825b3908845a0efe7a8d6e07ccf999c15d9af` |
| SHA-256 of `oracle/heldout_oracle.jsonl` | `ee864bdec1689c64c07ecd0eecfecdbae4e399501eabd5fb18ba520a59122c41` |
| Models | gemma4:12b digest 4eb23ef187e2, persia-f16:latest digest 8bf2ceed1372 (full digests in the freeze manifest) |
| Tag | `study02-prereg-v1` (on the commit that adds this record and the freeze manifest; code and cases are identical to C1) |

Any change after this point is a dated amendment labeled post hoc. The held-out run is started from this tag with `study02/run_heldout.sh`.
