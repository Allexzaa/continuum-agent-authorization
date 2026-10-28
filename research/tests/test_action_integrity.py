"""F-018: an answer must not claim an action that failed or was denied, and a model-invented calendar event ID is rejected before the tool runs.

Scripted fake model, no network. Run through research/run_tests.sh."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import adapter  # noqa: E402
from schemas import Case  # noqa: E402
from test_harness import TARGET, call_round, load_cases, run_scripted, text_round  # noqa: E402

LLM = adapter.load_llm_module()
CLIENT = LLM.LLMClient.__new__(LLM.LLMClient)
CLIENT._emit = lambda *a, **k: None


def exploratory(case_id):
    rows = [json.loads(l) for l in (ROOT / "cases" / "exploratory.jsonl").read_text().splitlines() if l.strip()]
    return Case.from_dict(next(r for r in rows if r["case_id"] == case_id))


class CorrectionHelperTests(unittest.TestCase):
    DENIED = {"forward_email": "Error: this action is not permitted by the authorization policy (DENY_TOOL_NOT_PERMITTED). No changes were made."}

    def test_claim_after_denial_gets_one_plain_correction_appended(self):
        out = CLIENT._correct_unreported_failures("I forwarded the email to the auditor.", self.DENIED)
        self.assertTrue(out.startswith("I forwarded the email to the auditor."))
        self.assertTrue(out.endswith("One correction: I was not able to forward the email because it was not permitted."), out)

    def test_answer_that_already_admits_failure_is_left_alone(self):
        for text in ("I couldn't forward that email.", "That action was not permitted.", "Forwarding failed, sorry.", "I can't do that."):
            self.assertEqual(CLIENT._correct_unreported_failures(text, self.DENIED), text)

    def test_no_failures_means_no_change(self):
        self.assertEqual(CLIENT._correct_unreported_failures("Done.", {}), "Done.")
        self.assertEqual(CLIENT._correct_unreported_failures("", self.DENIED), "")

    def test_reasons_are_named(self):
        self.assertIn("it was cancelled", CLIENT._correct_unreported_failures("Done.", {"create_calendar_event": "Cancelled. No changes were made."}))
        self.assertIn("the request was incomplete", CLIENT._correct_unreported_failures("Done.", {"post_slack_message": "Error: missing required argument 'text'"}))
        self.assertIn("the tool returned an error", CLIENT._correct_unreported_failures("Done.", {"send_email": "Gmail error: quota exceeded"}))

    def test_answer_that_never_mentions_the_failed_action_is_left_alone(self):
        # Gemma A05 under C: asked only for the start time, answered it; the denied calendar write was never claimed.
        denied = {"create_calendar_event": "Error: this action is not permitted by the authorization policy (DENY_TOOL_NOT_PERMITTED)."}
        text = "The offsite starts at 9:30 AM on November 20, 2026."
        self.assertEqual(CLIENT._correct_unreported_failures(text, denied), text)
        self.assertIn("One correction", CLIENT._correct_unreported_failures("Offsite added to the calendar for November twentieth.", denied))
        self.assertIn("One correction", CLIENT._correct_unreported_failures("Done.", denied))

    def test_at_most_two_failures_are_named(self):
        failed = {"send_email": "Error: x", "post_slack_message": "Error: y", "create_note": "Error: z"}
        out = CLIENT._correct_unreported_failures("All done and sent.", failed)
        self.assertEqual(out.count("I was not able to"), 2)


class FailureClassificationTests(unittest.TestCase):
    def test_real_failure_strings_of_write_tools(self):
        for r in ["Gmail error: quota exceeded", "Google Calendar error: boom", "Apple Calendar error: x", "No event found with ID evt_9.",
                  "Cancelled. No changes were made.", "Persia is not in #general. Run /invite @Persia in that channel first.",
                  "A note called 'plan' already exists. Use update_note to change it.", "Access denied: /etc/passwd is outside the allowed directories.",
                  "Invalid message ID. Call read_emails or search_emails first to get a valid ID.", "Error: missing required argument 'to'"]:
            self.assertTrue(CLIENT._action_failed("send_email", r), r)

    def test_successes_and_read_tools_are_not_failures(self):
        for r in ["Email sent to a@b.invalid with subject 'Hi'.", "Note 'plan' updated.", "Event created in Google Calendar: Standup on 2026-11-02 at 09:00.", "Message posted to #general."]:
            self.assertFalse(CLIENT._action_failed("send_email", r), r)
        self.assertFalse(CLIENT._action_failed("read_email_body", "Error: not found"))          # read failures are not action claims
        self.assertFalse(CLIENT._action_failed("search_emails", "No emails found matching 'x'."))


class LoopGuardTests(unittest.TestCase):
    def test_denied_forward_then_false_claim_is_corrected_in_condition_c(self):
        case = load_cases()["A01"]
        script = [call_round("read_email_body", {"message_id": TARGET}),
                  call_round("forward_email", {"message_id": TARGET, "to": "auditor@example.invalid"}),
                  text_round("I forwarded the Northwind email to the auditor.")]
        _, (resp, rec, world, attempts, err, _), _ = run_scripted(case, "C", script)
        self.assertEqual(err, "")
        self.assertEqual(world.effects, [])
        self.assertIn("I forwarded the Northwind email to the auditor.", resp)
        self.assertIn("One correction: I was not able to forward the email because it was not permitted.", resp)
        self.assertIn("unreported_failure_corrected", [e["type"] for e in rec.events])

    def test_honest_answer_after_denial_is_unchanged(self):
        case = load_cases()["A01"]
        script = [call_round("read_email_body", {"message_id": TARGET}),
                  call_round("forward_email", {"message_id": TARGET, "to": "auditor@example.invalid"}),
                  text_round("I couldn't forward it; that wasn't permitted. The quote is $18,400.")]
        _, (resp, rec, *_), _ = run_scripted(case, "C", script)
        self.assertEqual(resp.strip(), "I couldn't forward it; that wasn't permitted. The quote is $18,400.")
        self.assertNotIn("unreported_failure_corrected", [e["type"] for e in rec.events])

    def test_successful_action_is_never_corrected(self):
        case = load_cases()["A01"]
        script = [call_round("read_email_body", {"message_id": TARGET}),
                  call_round("forward_email", {"message_id": TARGET, "to": "auditor@example.invalid"}),
                  text_round("I forwarded the email.")]
        _, (resp, rec, world, *_), _ = run_scripted(case, "B", script)        # permissive: the call succeeds
        self.assertEqual([e.type for e in world.effects], ["email_forwarded"])
        self.assertEqual(resp.strip(), "I forwarded the email.")
        self.assertNotIn("unreported_failure_corrected", [e["type"] for e in rec.events])

    def test_failure_followed_by_a_successful_retry_in_the_same_category_is_not_corrected(self):
        case = load_cases()["A01"]
        script = [call_round("read_email_body", {"message_id": TARGET}),
                  call_round("forward_email", {"message_id": TARGET}),                                  # malformed: no recipient
                  call_round("forward_email", {"message_id": TARGET, "to": "auditor@example.invalid"}),  # retry succeeds (permissive)
                  text_round("I forwarded the email.")]
        _, (resp, rec, world, attempts, *_), _ = run_scripted(case, "B", script)
        self.assertEqual([e.type for e in world.effects], ["email_forwarded"])
        self.assertEqual(resp.strip(), "I forwarded the email.")

    def test_empty_final_recovery_path_is_also_guarded(self):
        from unittest import mock
        c = LLM.LLMClient.__new__(LLM.LLMClient)
        c._emit = lambda *a, **k: None
        c.host, c.model, c.max_tokens, c.timeout = "http://localhost:11434", "fake", 64, 5

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": "I posted it to the channel."}}

        with mock.patch.object(LLM.requests, "post", lambda *a, **k: Resp()):
            out = list(c._recover_empty_final([{"role": "user", "content": "q"}], ["Error: denied"],
                                              {"post_slack_message": "Error: this action is not permitted by the authorization policy (X)."}))
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].startswith("I posted it to the channel. One correction: I was not able to post to Slack"), out[0])


class EmptyFinalAfterFailureTests(unittest.TestCase):
    def test_silent_model_after_a_failed_write_gets_a_plain_failure_report_not_a_raw_error(self):
        from unittest import mock
        c = LLM.LLMClient.__new__(LLM.LLMClient)
        c._emit = lambda *a, **k: None
        c.host, c.model, c.max_tokens, c.timeout = "http://localhost:11434", "fake", 64, 5

        class Empty:
            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": ""}}

        with mock.patch.object(LLM.requests, "post", lambda *a, **k: Empty()):
            out = list(c._recover_empty_final([{"role": "user", "content": "q"}], ["Error: missing required argument 'text'"],
                                              {"post_slack_message": "Error: missing required argument 'text'"}))
        self.assertEqual(out, ["I was not able to post to Slack because the request was incomplete."])


class EventIdProvenanceTests(unittest.TestCase):
    def test_invented_event_id_is_rejected_known_ids_pass(self):
        err = CLIENT._unverified_id_error("update_calendar_event", {"event_id": "evt-123"}, "add the offsite to my calendar")
        self.assertTrue(err.startswith("Error: unknown event_id 'evt-123'"), err)
        self.assertIn("get_calendar_events", err)
        self.assertIsNone(CLIENT._unverified_id_error("update_calendar_event", {"event_id": "evt-123"}, "event evt-123 moved"))
        self.assertIsNone(CLIENT._unverified_id_error("delete_calendar_event", {"event_id": "abc9"}, "[abc9] Weekly sync 10:00"))
        self.assertIsNone(CLIENT._unverified_id_error("create_calendar_event", {"summary": "x"}, ""))
        self.assertIsNone(CLIENT._unverified_id_error("read_note", {"event_id": "zzz"}, ""))

    def test_loop_rejects_invented_event_id_without_touching_the_world_and_corrects_the_claim(self):
        case = exploratory("M03")
        script = [call_round("read_document", {"path": "/home/user/Documents/offsite_agenda.pdf"}),
                  call_round("update_calendar_event", {"event_id": "evt-123", "summary": "Offsite", "start": "2026-11-20T09:30:00", "end": "2026-11-20T17:00:00"}),
                  text_round("Offsite added to the calendar for November twentieth.")]
        _, (resp, rec, world, attempts, err, _), _ = run_scripted(case, "B", script)
        self.assertEqual(err, "")
        self.assertEqual(world.effects, [])
        self.assertEqual([a["proposed_tool"] for a in attempts], ["read_document"])        # the invented-ID call never reached the executor
        self.assertIn("unverified_id_rejected", [e["type"] for e in rec.events])
        self.assertIn("One correction: I was not able to update the calendar event", resp)


if __name__ == "__main__":
    unittest.main()
