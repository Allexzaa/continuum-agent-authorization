"""Study 02 adapter: drives the frozen Persia loop (agent_snapshot/) inside the mock boundary.

Boundary guarantees (tests/test_gates.py, gate G0):
  * every tool execution goes through the arm's policy and the mock world; the real _run_tool is replaced by a function that raises;
  * llm.requests is replaced by a guard that permits only localhost model endpoints and records every request, including the
    planner call and the empty-final recovery call (non-streamed), untruncated;
  * a system message is always sent; the production-equivalent loop is used (fixed format, stop-on-read on) unless an ablation is declared.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests as _real_requests

from lineage import Ledger
from policies import DENIAL_RESULT, INTERNAL_TEXT_ARGS, OVERLAP_THRESHOLD, Ctx, policy_for
from schemas import Case2
from world import World

STUDY = Path(__file__).resolve().parents[1]
SNAPSHOT = STUDY / "agent_snapshot"
SOUL_PATH = SNAPSHOT / "config" / "SOUL.md"
PINNED_OPTIONS = {"temperature": 0.6, "top_p": 0.9, "top_k": 40, "num_ctx": 8192}
SEED_BASE = 2000
MAX_TOKENS = 512
SANDBOX_ALLOWED_DIRS = "/research-sandbox"
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_llm_module():
    sys.path.insert(0, str(SNAPSHOT))
    spec = importlib.util.spec_from_file_location("persia_llm_study02", SNAPSHOT / "pipeline" / "llm.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def system_prompt() -> str:
    return SOUL_PATH.read_text(encoding="utf-8")


class NetworkViolation(RuntimeError):
    pass


class Recorder:
    def __init__(self):
        self.requests: list[dict] = []
        self.model_rounds: list[dict] = []       # streamed rounds, untruncated
        self.nonstream: list[dict] = []          # planner and recovery calls, untruncated
        self.events: list[dict] = []
        self.blocked_network: list[str] = []

    def emit(self, type: str, data: dict):      # doubles as the LLMClient event bus
        self.events.append({"type": type, **{k: v for k, v in (data or {}).items() if k in ("round", "tools", "reason")}})


class TeeResponse:
    def __init__(self, resp, recorder: Recorder, request_index: int):
        self._resp, self._rec, self._idx = resp, recorder, request_index

    status_code = property(lambda self: self._resp.status_code)

    def raise_for_status(self):
        return self._resp.raise_for_status()

    def __enter__(self):
        self._resp.__enter__()
        return self

    def __exit__(self, *exc):
        return self._resp.__exit__(*exc)

    def __getattr__(self, name):
        return getattr(self._resp, name)

    def iter_lines(self, *a, **kw):
        content, calls = [], []
        for line in self._resp.iter_lines(*a, **kw):
            if line:
                try:
                    d = json.loads(line)
                except ValueError:
                    d = None
                if d:
                    msg = d.get("message", {})
                    if msg.get("tool_calls"):
                        calls = msg["tool_calls"]
                    if msg.get("content"):
                        content.append(msg["content"])
                    if d.get("done"):
                        self._rec.model_rounds.append({
                            "request_index": self._idx, "content": "".join(content), "native_tool_calls": calls,
                            "prompt_eval_count": d.get("prompt_eval_count"), "eval_count": d.get("eval_count"),
                            "done_reason": d.get("done_reason")})
            yield line


class RecordedResponse:
    """Non-streamed response; stores what the caller reads."""

    def __init__(self, resp, recorder: Recorder, request_index: int):
        self._resp, self._rec, self._idx = resp, recorder, request_index

    def json(self, *a, **kw):
        data = self._resp.json(*a, **kw)
        self._rec.nonstream.append({"request_index": self._idx, "response": data})
        return data

    def __getattr__(self, name):
        return getattr(self._resp, name)


class GuardedRequests:
    def __init__(self, recorder: Recorder, options: dict, nonstream_think_off: bool = False):
        self._rec, self._options, self._think_off = recorder, options, nonstream_think_off

    def _check(self, url: str):
        if urlparse(url).hostname not in ALLOWED_HOSTS:
            self._rec.blocked_network.append(url)
            raise NetworkViolation(f"blocked non-local request: {url}")

    def post(self, url, json=None, **kw):
        self._check(url)
        stream = False
        if json is not None:
            opts = dict(json.get("options", {}))
            opts.update(self._options)
            json = {**json, "options": opts}
            stream = bool(json.get("stream"))
            if self._think_off and not stream:
                json = {**json, "think": False}                  # diagnostic planner mode only (planner=think_off)
            self._rec.requests.append({"url": url, "messages": json.get("messages", []), "n_tools": len(json.get("tools", [])),
                                       "options": opts, "stream": stream})
        resp = _real_requests.post(url, json=json, **kw)
        idx = len(self._rec.requests) - 1
        return TeeResponse(resp, self._rec, idx) if stream else RecordedResponse(resp, self._rec, idx)

    def get(self, url, *a, **kw):
        self._check(url)
        return _real_requests.get(url, *a, **kw)

    def __getattr__(self, name):
        return getattr(_real_requests, name)


def _coerce_args(args):
    if isinstance(args, str):
        try:
            return json.loads(args)
        except ValueError:
            return {"_raw": args}
    return args if isinstance(args, dict) else {}


class Study2Adapter:
    def __init__(self, llm_module, model: str, host: str = "http://127.0.0.1:11434"):
        self.llm = llm_module
        self.model, self.host = model, host
        self.schemas = {t["function"]["name"]: t["function"].get("parameters", {}) for t in llm_module.TOOLS}
        self.required = {n: s.get("required", []) for n, s in self.schemas.items()}
        os.environ["ALLOWED_DIRS"] = SANDBOX_ALLOWED_DIRS
        os.environ["THINK_MODE"] = "false"

    def run(self, case: Case2, condition: str, trial: int, prompt: str, stop_on_read: bool = True, planner: str = "production"):
        """Returns (final_response, recorder, world, attempts, error, latency_ms)."""
        if not prompt:
            raise ValueError("a system prompt is mandatory")
        llm = self.llm
        rec = Recorder()
        if planner not in ("production", "off", "think_off"):
            raise ValueError(f"unknown planner mode {planner!r}")
        llm.requests = GuardedRequests(rec, dict(PINNED_OPTIONS, seed=SEED_BASE + trial), nonstream_think_off=(planner == "think_off"))
        world = World(case.resolved_fixture())
        ledger = Ledger(case.user_request, case.user_grants)
        ctx = Ctx(world=world, ledger=ledger, grants=case.user_grants, required=self.required)
        policy = policy_for(condition)
        available = set(case.available_tools)
        attempts: list[dict] = []

        client = llm.LLMClient(host=self.host, model=self.model, max_tokens=MAX_TOKENS, timeout=180,
                               confirm_fn=lambda p: True, event_bus=rec)
        if not stop_on_read:
            client._read_returned_content = lambda name, result: False      # declared ablation only
        if planner == "off":
            client._is_multistep = lambda text: False                  # diagnostic: no plan-then-execute step
        client._tools_for_request = lambda text: [t for t in llm.TOOLS if t["function"]["name"] in available]

        def _forbidden(*a, **k):
            raise AssertionError("real _run_tool must never run inside the research harness")
        client._run_tool = _forbidden

        def dispatch(name, args):
            args = _coerce_args(args)
            dest = world.destination_of(name, args)
            origin = ledger.origin(dest) if dest else None
            before = ledger.summary()
            verdict = policy.check(name, args, ctx)
            effect, reads = None, []
            if verdict.decision == "allow":
                result, eff = world.execute(name, args)
                effect = None if eff is None else eff.__dict__
                reads = [{k: r[k] for k in ("artifact", "trust", "sensitivity")} for r in world.last_reads]
                ledger.observe_reads(world.last_reads)
                if eff is not None and name in INTERNAL_TEXT_ARGS:
                    ledger.observe_write(" ".join(str(args.get(k, "")) for k in INTERNAL_TEXT_ARGS[name]), OVERLAP_THRESHOLD)
            else:
                result = DENIAL_RESULT.format(code=verdict.reason_code)
            attempts.append({"round_index": client._current_round, "tool": name, "args": args,
                             "validated_args": all(args.get(r) not in (None, "") for r in self.required.get(name, [])),
                             "destination": dest, "destination_origin": origin, "ledger_before": before,
                             "verdict": verdict.__dict__, "effect": effect, "reads": reads, "result": result})
            return result
        client._execute_tool = dispatch

        messages = [{"role": "system", "content": prompt}, {"role": "user", "content": case.user_request}]
        t0, error, chunks = time.perf_counter(), "", []
        try:
            chunks = list(client.stream(messages))
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        if rec.blocked_network:
            error = (error + " | " if error else "") + f"NETWORK_VIOLATION {rec.blocked_network}"
        return " ".join(chunks), rec, world, attempts, error, round((time.perf_counter() - t0) * 1000)

    def proposed_calls(self, rec: Recorder, available: set[str]) -> list[dict]:
        llm, out = self.llm, []
        for r in rec.model_rounds:
            if r["native_tool_calls"]:
                for tc in r["native_tool_calls"]:
                    fn = tc.get("function", {})
                    out.append({"request_index": r["request_index"], "tool": fn.get("name", ""),
                                "args": _coerce_args(fn.get("arguments", {})), "source": "native"})
            elif r["content"]:
                try:
                    _, raw = llm._extract_raw_tool_calls(llm._strip_think_blocks(r["content"]))
                except Exception as exc:
                    out.append({"request_index": r["request_index"], "tool": "", "args": {}, "source": "parse_error",
                                "parse_error": f"{type(exc).__name__}: {exc}"})
                    continue
                for c in raw:
                    out.append({"request_index": r["request_index"], "tool": c["name"], "args": _coerce_args(c["arguments"]), "source": "raw_text"})
        return out
