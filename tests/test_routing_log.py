"""Acceptance tests for the section 17 routing decision log.

Spec: docs/research/2026-09-19-jev-risk-routed-hybrid-core.md, section 17.

Section 17 requires an append-only local JSONL log, and forbids writing source,
secrets, credentials, hidden tests, raw sensitive prompts, or full tool output.
That is enforced structurally here: the log is written through an allow-list, so
an unapproved key is dropped rather than serialized. A blocklist would fail open
on the first key nobody thought of.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.routing_log import APPROVED_FIELDS, append_entry, build_entry, read_entries  # noqa: E402


class ProjectionTest(unittest.TestCase):
    """Only approved metadata may reach disk."""

    def test_approved_fields_survive(self) -> None:
        raw = {
            "task_id": "C01",
            "language": "en",
            "static_decision": "fast_deepseek",
            "predicted_route": "fast_deepseek",
            "confidence": 0.91,
            "jev_latency_ms": 240,
        }
        self.assertEqual(build_entry(raw), raw)

    def test_source_content_is_dropped(self) -> None:
        raw = {
            "task_id": "C01",
            "source_code": "def secret_impl(): ...",
            "diff": "--- a/x\n+++ b/x",
            "stdout": "full tool output",
            "transcript": "raw conversation",
        }
        entry = build_entry(raw)
        self.assertEqual(set(entry), {"task_id"})

    def test_credential_like_keys_are_dropped(self) -> None:
        raw = {
            "task_id": "C01",
            "api_key": "sk-live-xxx",
            "TYPESAFE_API_KEY": "xxx",
            "authorization": "Bearer xxx",
            "hidden_tests": ["def test_hidden(): ..."],
        }
        self.assertEqual(set(build_entry(raw)), {"task_id"})

    def test_unapproved_key_is_dropped_even_when_innocent(self) -> None:
        """Fail-closed: a key nobody approved is not written by default."""
        self.assertNotIn("notes", build_entry({"task_id": "C01", "notes": "hello"}))

    def test_build_entry_does_not_mutate_input(self) -> None:
        raw = {"task_id": "C01", "source_code": "x"}
        snapshot = dict(raw)
        build_entry(raw)
        self.assertEqual(raw, snapshot)

    def test_approved_fields_are_documented(self) -> None:
        self.assertIn("static_decision", APPROVED_FIELDS)
        self.assertIn("predicted_route", APPROVED_FIELDS)
        self.assertIn("risk_signals", APPROVED_FIELDS)
        self.assertNotIn("source_code", APPROVED_FIELDS)


class AppendOnlyTest(unittest.TestCase):
    """The log is append-only JSONL and survives a round trip."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "routing.jsonl"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_append_never_truncates(self) -> None:
        append_entry(self.path, build_entry({"task_id": "C01", "static_decision": "fast_deepseek"}))
        append_entry(self.path, build_entry({"task_id": "C02", "static_decision": "expert_gpt"}))
        lines = self.path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 2)

    def test_every_line_is_valid_json(self) -> None:
        append_entry(self.path, build_entry({"task_id": "C01", "static_rules": ["static_fast"]}))
        for line in self.path.read_text(encoding="utf-8").strip().splitlines():
            json.loads(line)

    def test_round_trip_preserves_values(self) -> None:
        entry = build_entry({"task_id": "C05", "static_decision": "uncertain", "confidence": None})
        append_entry(self.path, entry)
        self.assertEqual(read_entries(self.path), [entry])

    def test_read_missing_log_returns_empty(self) -> None:
        self.assertEqual(read_entries(self.path), [])

    def test_append_rejects_unapproved_entry(self) -> None:
        """Defence in depth: append itself must not be a bypass."""
        with self.assertRaises(ValueError):
            append_entry(self.path, {"task_id": "C01", "source_code": "leak"})
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
