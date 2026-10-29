"""Gate G1 for Study 02b: freeze manifest (tree hashes, case and oracle hashes, model identity, git). No model call."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_followup as rf
ROOT = rf.ROOT
files = {}
for sub in ("cases", "oracle"):
    for p in sorted((ROOT / "study02b" / sub).glob("*.jsonl")): files[f"study02b/{sub}/{p.name}"] = hashlib.sha256(p.read_bytes()).hexdigest()
commit, dirty = rf.git_state()
m = {"git_commit": commit, "git_dirty": dirty, "code_sha256": rf.tree_hashes(), "case_and_oracle_sha256": files,
     "models": {x: rf.rs.ollama_identity("http://127.0.0.1:11434", x) for x in ("gemma4:12b", "persia-f16:latest")}}
(ROOT / "study02b" / "freeze" / "manifest.json").write_text(json.dumps(m, indent=1), encoding="utf-8")
print("freeze:", commit[:8], "dirty", dirty, len(m["code_sha256"]), "code files,", len(files), "case/oracle files")
