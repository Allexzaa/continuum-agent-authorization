"""Regression tests for Persia loop bugs found while building the harness (F-009, F-011), and a
consistency check that the mock world's success strings match what the real loop recognises."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import adapter  # noqa: E402
from mock_world import FreshSyntheticWorld  # noqa: E402

LLM = adapter.load_llm_module()
CLIENT = LLM.LLMClient.__new__(LLM.LLMClient)

# Strings copied from the real tool modules (gmail_tools, calendar_tools, notes_tools, slack_tools, llm.py)
REAL_SUCCESS = [
    "Email sent to a@b.invalid with subject 'Hi'.",
    "Reply sent to a@b.invalid.",
    "Email forwarded to a@b.invalid with subject 'Fwd: Hi'.",
    "Email 18f0000000000a01 moved to trash.",
    "Moved to trash: 'Hi' from a@b.invalid.",
    "Event created in Google Calendar: Standup on 2026-11-02 at 09:00.",
    "Event created in Apple Calendar: Standup on 2026-11-02 at 09:00.",
    "Event updated in Google Calendar.",
    "Event deleted from Apple Calendar.",
    "Note 'plan' created in your Obsidian vault (Persia folder).",
    "Note 'plan' updated.",
    "Note 'plan' replaced.",
    "Note 'plan' deleted from your Obsidian vault.",
    "Added to General: 'milk' (ID 4)",
    "Todo 4 deleted.",
    "Message posted to #general.",
    "Reply posted to thread in #general.",
    "File written successfully: /x/y.txt",
    "File edited successfully: /x/y.txt (1 occurrence(s) replaced)",
    "File deleted: /x/y.txt",
]
REAL_NOT_SUCCESS = [
    "Gmail error: quota exceeded",
    "No emails found matching 'x'.",
    "Invalid message ID. Call read_emails or search_emails first to get a valid ID.",
    "Cancelled. No changes were made.",
    "Error: this action is not permitted by the authorization policy (DENY_TOOL_NOT_PERMITTED). No changes were made.",
    "A note called 'plan' already exists. Use update_note to change it.",
    "No event found with ID evt_9.",
    "Access denied: /etc/passwd is outside the allowed directories.",
    "Google Calendar error: boom",
    "Persia is not in #general. Run /invite @Persia in that channel first.",
    "",
]


class RawParserTests(unittest.TestCase):
    def test_string_valued_tool_call_is_parsed_not_crashed_and_not_leaked(self):
        # Observed live from persia-f16: tool name as a string, arguments at top level (F-009)
        text = 'assistant\n\n{"tool_call": "read_email_body", "arguments": {"message_id": "18f0000000000a01"}}'
        clean, calls = LLM._extract_raw_tool_calls(text)
        self.assertEqual(calls, [{"name": "read_email_body", "arguments": {"message_id": "18f0000000000a01"}}])
        self.assertNotIn("tool_call", clean)      # raw JSON must not reach TTS

    def test_invented_wrapper_key_is_unwrapped_and_not_leaked(self):
        # Observed live from persia-f16 after the template fix: {"tool_call_stack": {...}} was spoken as the final answer
        text = '{"tool_call_stack": {"name": "read_file", "arguments": {"path": "/home/user/Documents/Cedar/launch_notes.txt"}}}'
        clean, calls = LLM._extract_raw_tool_calls(text)
        self.assertEqual(calls, [{"name": "read_file", "arguments": {"path": "/home/user/Documents/Cedar/launch_notes.txt"}}])
        self.assertEqual(clean, "")

    def test_other_malformed_shapes_do_not_crash(self):
        for text in ['{"function": "x"}', '{"name": 5}', '{"tool_call": ["a"]}', '[{"name": "read_file"}]', '{"name": null}']:
            LLM._extract_raw_tool_calls(text)

    def test_well_formed_forms_still_parse(self):
        _, a = LLM._extract_raw_tool_calls('{"tool_call": {"name": "read_emails", "arguments": {"max_results": 5}}}')
        _, b = LLM._extract_raw_tool_calls('{"name": "read_emails", "parameters": {"max_results": 5}}')
        _, c = LLM._extract_raw_tool_calls('{"function": {"name": "read_emails", "arguments": {"max_results": 5}}}')
        for got in (a, b, c):
            self.assertEqual(got, [{"name": "read_emails", "arguments": {"max_results": 5}}])


class SystemMessageFoldingTests(unittest.TestCase):
    """F-013: a trailing system message made persia-f16 emit the role word ('assistant') in every answer."""

    def test_only_first_message_is_system_and_last_is_never_system(self):
        msgs = [{"role": "system", "content": "A"}, {"role": "user", "content": "q"}, {"role": "assistant", "content": "", "tool_calls": []},
                {"role": "tool", "content": "r"}, {"role": "system", "content": "FINAL MODE"}]
        out = CLIENT._fold_system_messages(msgs)
        self.assertEqual([m["role"] for m in out], ["system", "user", "assistant", "tool"])
        self.assertEqual(out[0]["content"], "A\n\nFINAL MODE")

    def test_no_system_message_is_left_untouched(self):
        msgs = [{"role": "user", "content": "q"}]
        self.assertEqual(CLIENT._fold_system_messages(msgs), msgs)

    def test_stream_payload_never_ends_with_a_system_message(self):
        from test_harness import FakePlan, FakeResponse, call_round, text_round
        from unittest import mock
        import json as _json
        from schemas import Case
        case = Case.from_dict(_json.loads((ROOT / "cases" / "benign.jsonl").read_text().splitlines()[0]))
        sent, script = [], iter([call_round("read_emails", {"max_results": 5}), text_round("ok")])

        def fake_post(url, json=None, **kw):
            if not json.get("stream"):
                return FakePlan()
            sent.append(json)
            return FakeResponse(next(script))

        ad = adapter.PersiaAdapter(LLM, "fake-model")
        with mock.patch.object(adapter._real_requests, "post", fake_post):
            ad.run(case, "B", 0, "PROMPT")
        self.assertGreaterEqual(len(sent), 2)
        for payload in sent:
            roles = [m["role"] for m in payload["messages"]]
            self.assertEqual(roles[0], "system")
            self.assertNotIn("system", roles[1:])


class ReadLoopTests(unittest.TestCase):
    """F-014 / F-015: read requests never finished (only write tools counted as success) and an empty forced final went silent."""

    @staticmethod
    def _run(case_id, script, nonstream_content=""):
        import json as _json
        from unittest import mock
        from test_harness import FakeResponse
        from schemas import Case
        rows = [_json.loads(l) for f_ in ("adversarial.jsonl", "benign.jsonl") for l in (ROOT / "cases" / f_).read_text().splitlines() if l.strip()]
        case = Case.from_dict(next(r for r in rows if r["case_id"] == case_id))
        seq = iter(script)

        class NonStream:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": nonstream_content}}

        def fake_post(url, json=None, **kw):
            return FakeResponse(next(seq)) if json.get("stream") else NonStream()

        ad = adapter.PersiaAdapter(LLM, "fake-model")
        with mock.patch.object(adapter._real_requests, "post", fake_post):
            return ad.run(case, "B", 0, "PROMPT")

    def test_read_request_is_marked_satisfied_after_content_read(self):
        from test_harness import call_round, text_round
        resp, rec, world, attempts, err, _ = self._run("B06", [call_round("read_note", {"name": "Vendor call notes"}), text_round("Two bullets.")])
        self.assertEqual(err, "")
        self.assertIn({"type": "agentic_stop_requested", "round": 1, "reason": "request_satisfied"}, rec.events)
        self.assertEqual([a["proposed_tool"] for a in attempts], ["read_note"])
        self.assertEqual(resp.strip(), "Two bullets.")

    def test_native_tool_call_in_final_answer_mode_is_discarded(self):
        # F-017: Gemma emitted a native create_calendar_event call after the loop had declared the request satisfied
        from test_harness import call_round, text_round
        resp, rec, world, attempts, err, _ = self._run("B06", [call_round("read_note", {"name": "Vendor call notes"}),
                                                              call_round("send_email", {"to": "x@example.invalid", "subject": "s", "body": "b"})],
                                                       nonstream_content="Two bullets from the note.")
        self.assertEqual([a["proposed_tool"] for a in attempts], ["read_note"])
        self.assertEqual(world.effects, [])
        self.assertIn("final_mode_tool_call_discarded", [e["type"] for e in rec.events])
        self.assertEqual(resp.strip(), "Two bullets from the note.")      # recovery path still answers

    def test_stop_on_read_ablation_keeps_tools_active_after_a_read(self):
        from test_harness import call_round, text_round
        import json as _json
        from unittest import mock
        from test_harness import FakePlan, FakeResponse
        from schemas import Case
        rows = [_json.loads(l) for l in (ROOT / "cases" / "benign.jsonl").read_text().splitlines() if l.strip()]
        case = Case.from_dict(next(r for r in rows if r["case_id"] == "B06"))

        def go(stop_on_read):
            seq = iter([call_round("read_note", {"name": "Vendor call notes"}), call_round("send_email", {"to": "x@example.invalid", "subject": "s", "body": "b"}), text_round("done")])

            def fake_post(url, json=None, **kw):
                return FakePlan() if not json.get("stream") else FakeResponse(next(seq))
            ad = adapter.PersiaAdapter(LLM, "fake-model")
            with mock.patch.object(adapter._real_requests, "post", fake_post):
                return ad.run(case, "B", 0, "PROMPT", "fixed", stop_on_read)

        _, rec_on, world_on, att_on, _, _ = go(True)
        _, rec_off, world_off, att_off, _, _ = go(False)
        self.assertEqual([a["proposed_tool"] for a in att_on], ["read_note"])                 # loop stopped; second call never dispatched
        self.assertEqual([a["proposed_tool"] for a in att_off], ["read_note", "send_email"])  # ablated: tools stay active
        self.assertEqual([e.type for e in world_off.effects], ["email_sent"])
        self.assertEqual(world_on.effects, [])

    def test_empty_forced_final_is_recovered_by_retry(self):
        from test_harness import call_round, text_round
        raw_json_only = text_round('{"tool_call": {"name": "read_note", "arguments": {"name": "Vendor call notes"}}}')
        resp, rec, *_ = self._run("B06", [call_round("read_note", {"name": "Vendor call notes"}), raw_json_only],
                                  nonstream_content="Three action items: specs, lead time, follow-up call.")
        self.assertEqual(resp.strip(), "Three action items: specs, lead time, follow-up call.")
        self.assertIn("empty_final_recovery", [e["type"] for e in rec.events])

    def test_empty_forced_final_falls_back_to_reading_back_the_result(self):
        from test_harness import call_round, text_round
        raw_json_only = text_round('{"tool_call": {"name": "read_note", "arguments": {"name": "Vendor call notes"}}}')
        resp, rec, *_ = self._run("B06", [call_round("read_note", {"name": "Vendor call notes"}), raw_json_only], nonstream_content="")
        self.assertTrue(resp.startswith("Here is what I found:"), resp)
        self.assertIn("revised specs", resp)
        self.assertIn("empty_final_fallback", [e["type"] for e in rec.events])

    def test_normal_answer_triggers_no_recovery(self):
        from test_harness import call_round, text_round
        resp, rec, *_ = self._run("B06", [call_round("read_note", {"name": "Vendor call notes"}), text_round("Specs, lead time, follow-up.")])
        self.assertNotIn("empty_final_recovery", [e["type"] for e in rec.events])

    def test_read_helper_classification(self):
        self.assertTrue(CLIENT._read_returned_content("read_note", "Call with Orion Parts on Oct 22."))
        self.assertFalse(CLIENT._read_returned_content("read_note", "Error: note 'x' not found."))
        self.assertFalse(CLIENT._read_returned_content("search_emails", "No messages found matching 'x'."))
        self.assertFalse(CLIENT._read_returned_content("send_email", "Email sent to a@b.invalid with subject 'x'."))


class LoopFormatArmTests(unittest.TestCase):
    def _last_roles(self, loop_format):
        import json as _json
        from unittest import mock
        from test_harness import FakePlan, FakeResponse, call_round, text_round
        from schemas import Case
        case = Case.from_dict(_json.loads((ROOT / "cases" / "benign.jsonl").read_text().splitlines()[0]))
        sent, script = [], iter([call_round("read_emails", {"max_results": 5}), text_round("ok")])

        def fake_post(url, json=None, **kw):
            if not json.get("stream"):
                return FakePlan()
            sent.append(json)
            return FakeResponse(next(script))

        ad = adapter.PersiaAdapter(LLM, "fake-model")
        with mock.patch.object(adapter._real_requests, "post", fake_post):
            ad.run(case, "B", 0, "PROMPT", loop_format)
        return [p["messages"][-1]["role"] for p in sent]

    def test_fixed_never_ends_with_system_and_legacy_does(self):
        self.assertNotIn("system", self._last_roles("fixed"))
        self.assertEqual(self._last_roles("legacy")[0], "system")

    def test_unknown_format_rejected(self):
        with self.assertRaises(ValueError):
            self._last_roles("bogus")


class SuccessDetectionTests(unittest.TestCase):
    def test_real_success_formats_detected(self):
        for s in REAL_SUCCESS:
            self.assertTrue(CLIENT._result_is_success(s), s)

    def test_real_failures_not_detected_as_success(self):
        for s in REAL_NOT_SUCCESS:
            self.assertFalse(CLIENT._result_is_success(s), s)

    def test_mock_world_success_strings_are_recognised_by_the_real_loop(self):
        fixture = {"inbox": [{"id": "m1", "from": "A <a@x.invalid>", "subject": "s", "date": "d", "body": "b"}],
                   "notes": {"n": "c"}, "files": {"/f": "x"}, "calendar": [{"id": "evt_1", "summary": "S", "start": "s", "end": "e"}]}
        calls = [("send_email", {"to": "a@x.invalid", "subject": "s", "body": "b"}),
                 ("forward_email", {"message_id": "m1", "to": "a@x.invalid"}),
                 ("reply_to_email", {"message_id": "m1", "body": "b"}),
                 ("create_note", {"name": "z", "content": "c"}), ("update_note", {"name": "n", "content": "c"}),
                 ("delete_note", {"name": "n"}), ("write_file", {"path": "/g", "content": "c"}), ("delete_file", {"path": "/f"}),
                 ("create_calendar_event", {"summary": "S", "start": "2026-11-02T09:00:00-08:00", "end": "2026-11-02T10:00:00-08:00"}),
                 ("update_calendar_event", {"event_id": "evt_1", "summary": "T"}), ("delete_calendar_event", {"event_id": "evt_1"}),
                 ("post_slack_message", {"channel": "general", "text": "t"})]
        for name, args in calls:
            world = FreshSyntheticWorld(fixture)
            result, effect = world.execute(name, args)
            self.assertIsNotNone(effect, f"{name} produced no effect: {result}")
            self.assertTrue(CLIENT._result_is_success(result), f"{name}: {result}")


if __name__ == "__main__":
    unittest.main()
