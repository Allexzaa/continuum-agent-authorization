"""Gate G1: freeze the executable state before any run. Writes freeze/manifest.json (full SHA-256, git, interpreter, packages, model identity)
and freeze/ollama_<model>.json (full `show` output without the baked-in system prompt). Makes no model call."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import requests

from run_study import REPO, STUDY, full_hashes, git_state, ollama_identity

MODELS = ["persia-f16:latest", "gemma4:12b"]
HOST = "http://127.0.0.1:11434"


def main() -> int:
    commit, dirty = git_state()
    pip = subprocess.run([str(REPO / "voice-agent" / ".venv" / "bin" / "python3"), "-m", "pip", "freeze"], capture_output=True, text=True).stdout.splitlines()
    files = {}
    for sub in ("cases", "oracle"):
        for p in sorted((STUDY / sub).glob("*.jsonl")):
            files[f"{sub}/{p.name}"] = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {"git_commit": commit, "git_dirty": dirty, "python": sys.version, "platform": platform.platform(), "pip_freeze": pip,
                "code_sha256": full_hashes(), "case_and_oracle_sha256": files, "models": {m: ollama_identity(HOST, m) for m in MODELS}}
    out = STUDY / "freeze"
    out.mkdir(exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    for m in MODELS:
        try:
            show = requests.post(f"{HOST}/api/show", json={"model": m}, timeout=30).json()
            show.pop("system", None)
            show["modelfile"] = "\n".join(l for l in show.get("modelfile", "").splitlines() if not l.startswith("SYSTEM"))[:20000]
            (out / f"ollama_{m.replace(':', '_').replace('/', '_')}.json").write_text(json.dumps(show, indent=1)[:200000], encoding="utf-8")
        except Exception as exc:
            print("show failed", m, exc)
    print("freeze manifest written;", {m: manifest["models"][m].get("digest", "?") for m in MODELS})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
