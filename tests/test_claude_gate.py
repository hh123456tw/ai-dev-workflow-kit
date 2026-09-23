"""Acceptance tests for the Claude lane completion gate.

Every test drives the real hook script the way Claude Code does: a JSON event on
stdin, a subprocess per hook, a real git repository on disk. Nothing inside the
gate is mocked, because the property under test is end to end: a session that
changed files cannot stop on a receipt the recorded evidence contradicts.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "modes" / "claude" / "core" / "plugin" / "hooks" / "kit_gate.py"

RISK_FLAGS = (
    "demo_path",
    "cross_module",
    "concurrency",
    "shared_state",
    "external_api",
    "external_integration",
    "demo_blocking_cross_module_crash",
)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@unittest.skipUnless(shutil.which("git"), "git is required")
class GateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.session = f"sess-{uuid.uuid4().hex}"
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        git(self.repo, "config", "core.autocrlf", "false")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "src" / "util.py").write_text("y = 1\n", encoding="utf-8")
        (self.repo / "tests").mkdir()
        (self.repo / "tests" / "test_app.py").write_text("", encoding="utf-8")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "init")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ---------------------------------------------------------------- drivers

    def hook(self, command: str, _env: dict = None, **event) -> subprocess.CompletedProcess:
        payload = {"session_id": self.session, "cwd": str(self.repo), **event}
        # A neutral non-git working directory: the gate must find the repository
        # from the event, never from wherever the hook process happens to run.
        neutral = Path(self._tmp.name) / "neutral"
        neutral.mkdir(exist_ok=True)
        return subprocess.run(
            [sys.executable, str(GATE), command],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=60,
            cwd=neutral,
            env=_env,
        )

    def start(self) -> None:
        self.assertEqual(self.hook("session-start", hook_event_name="SessionStart").returncode, 0)

    def ran(self, command: str, exit_code: int = 0) -> None:
        if exit_code == 0:
            result = self.hook("record", hook_event_name="PostToolUse", tool_name="Bash",
                               tool_input={"command": command}, tool_response={"stdout": ""})
        else:
            result = self.hook("record", hook_event_name="PostToolUseFailure", tool_name="Bash",
                               tool_input={"command": command}, error=f"Exit code {exit_code}\nboom")
        self.assertEqual(result.returncode, 0, result.stderr)

    def reviewed(self, agent: str = "kit-core:reviewer") -> None:
        result = self.hook("record", hook_event_name="PostToolUse", tool_name="Agent",
                           tool_input={"subagent_type": agent, "prompt": "review"})
        self.assertEqual(result.returncode, 0, result.stderr)

    def stop(self, active: bool = False) -> dict:
        result = self.hook("stop", hook_event_name="Stop", stop_hook_active=active,
                           last_assistant_message="done")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else {}

    def edit(self, rel: str, text: str = "changed\n") -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def receipt(self, **overrides) -> dict:
        base = {
            "status": "complete",
            "deadline_mode": "build",
            "changed_files": [
                {"path": "src/app.py", "class": "production", "reason": "runtime code"},
            ],
            "risk_flags": {name: {"value": False, "paths": []} for name in RISK_FLAGS},
            "review": {"required": False, "status": "not_required", "findings": []},
            "commands": [{"command": "python -m pytest -q", "exit_code": 0}],
            "acceptance": [{"criterion": "app returns 2", "status": "pass"}],
            "scope": "changed src/app.py only",
            "blocked": None,
        }
        base.update(overrides)
        path = self.repo / ".claude-kit" / "receipt.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(base), encoding="utf-8")
        return base

    def assertBlocked(self, output: dict, fragment: str) -> None:
        self.assertEqual(output.get("decision"), "block", output)
        self.assertIn(fragment, output.get("reason", ""))

    def assertAllowed(self, output: dict) -> None:
        self.assertNotEqual(output.get("decision"), "block", output)


class NoChangeTest(GateTestCase):
    def test_outside_a_git_repository_the_gate_is_silent(self) -> None:
        outside = Path(self._tmp.name) / "plain"
        outside.mkdir()
        result = subprocess.run(
            [sys.executable, str(GATE), "stop"],
            input=json.dumps({"session_id": self.session, "cwd": str(outside), "stop_hook_active": False}),
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_a_turn_without_changes_stops_freely(self) -> None:
        self.start()
        self.assertEqual(self.stop(), {})

    def test_files_already_dirty_at_session_start_do_not_count(self) -> None:
        self.edit("src/util.py", "pre-existing work\n")
        self.start()
        self.assertEqual(self.stop(), {})

    def test_touching_a_pre_existing_dirty_file_does_count(self) -> None:
        self.edit("src/util.py", "pre-existing work\n")
        self.start()
        self.edit("src/util.py", "agent edit\n")
        self.assertBlocked(self.stop(), "no receipt")


class ReceiptRequiredTest(GateTestCase):
    def test_changes_without_a_receipt_block(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.assertBlocked(self.stop(), "no receipt at .claude-kit/receipt.json")

    def test_committed_changes_still_need_a_receipt(self) -> None:
        self.start()
        self.edit("src/app.py")
        git(self.repo, "commit", "-qam", "agent commit")
        self.assertBlocked(self.stop(), "src/app.py")

    def test_invalid_json_blocks(self) -> None:
        self.start()
        self.edit("src/app.py")
        (self.repo / ".claude-kit").mkdir()
        (self.repo / ".claude-kit" / "receipt.json").write_text("{nope", encoding="utf-8")
        self.assertBlocked(self.stop(), "not valid JSON")

    def test_receipt_directory_is_excluded_from_git_status(self) -> None:
        self.start()
        exclude = (self.repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
        self.assertIn("/.claude-kit/", exclude.splitlines())
        self.receipt()
        status = subprocess.run(["git", "-C", str(self.repo), "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        self.assertNotIn(".claude-kit", status)


class CompleteReceiptTest(GateTestCase):
    def test_a_truthful_complete_receipt_is_accepted(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q")
        self.receipt()
        output = self.stop()
        self.assertAllowed(output)
        self.assertIn("receipt verified (status=complete", output.get("systemMessage", ""))

    def test_claimed_pass_contradicted_by_real_exit_code_blocks(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q", exit_code=1)
        self.receipt()
        self.assertBlocked(self.stop(), "claims exit 0 but its last run exited 1")

    def test_a_command_that_never_ran_blocks(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.receipt()
        self.assertBlocked(self.stop(), "never run in this session")

    def test_the_last_run_wins(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q", exit_code=1)
        self.ran("python -m pytest -q")
        self.receipt()
        self.assertAllowed(self.stop())

    def test_evidence_older_than_the_latest_edit_blocks(self) -> None:
        self.start()
        self.edit("src/app.py", "first\n")
        self.ran("python -m pytest -q")
        time.sleep(0.05)
        self.edit("src/app.py", "second\n")
        self.receipt()
        self.assertBlocked(self.stop(), "ran before the latest change")

    def test_a_receipt_older_than_the_latest_edit_blocks(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q")
        self.receipt()
        past = time.time() - 60
        os.utime(self.repo / ".claude-kit" / "receipt.json", (past, past))
        self.assertBlocked(self.stop(), "receipt is older than the latest change")

    def test_failing_acceptance_cannot_be_complete(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q")
        self.receipt(acceptance=[{"criterion": "x", "status": "not_run"}])
        self.assertBlocked(self.stop(), "every acceptance check to pass")

    def test_unresolved_important_finding_blocks(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q")
        self.receipt(review={"required": False, "status": "not_required", "findings": [
            {"severity": "important", "summary": "race", "resolved": False}]})
        self.assertBlocked(self.stop(), "unresolved")


class ChangedFilesTest(GateTestCase):
    def test_an_omitted_changed_file_blocks(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.edit("src/new_module.py")
        self.ran("python -m pytest -q")
        self.receipt()
        self.assertBlocked(self.stop(), "omits files git shows as changed: src/new_module.py")

    def test_a_listed_file_that_did_not_change_blocks(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q")
        self.receipt(changed_files=[
            {"path": "src/app.py", "class": "production", "reason": "code"},
            {"path": "src/util.py", "class": "production", "reason": "code"},
        ])
        self.assertBlocked(self.stop(), "did not change: src/util.py")

    def test_downgrading_production_code_blocks(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q")
        self.receipt(changed_files=[{"path": "src/app.py", "class": "non_production", "reason": "tiny"}])
        self.assertBlocked(self.stop(), "classified non_production")

    def test_generated_output_may_be_downgraded(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q")
        self.receipt(changed_files=[{"path": "src/app.py", "class": "non_production",
                                     "reason": "generated by codegen"}])
        self.assertAllowed(self.stop())

    def test_dotted_directories_keep_their_names(self) -> None:
        self.start()
        self.edit(".github/workflows/ci.yml")
        self.ran("python -m pytest -q")
        self.receipt(changed_files=[{"path": "./.github/workflows/ci.yml", "class": "production",
                                     "reason": "ci config"}])
        self.assertAllowed(self.stop())

    def test_true_risk_flag_needs_paths(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q")
        flags = {name: {"value": False, "paths": []} for name in RISK_FLAGS}
        flags["concurrency"] = {"value": True, "paths": []}
        self.receipt(risk_flags=flags)
        self.assertBlocked(self.stop(), "risk_flags.concurrency is true but names no affected paths")

    def test_every_risk_flag_must_be_recorded(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q")
        self.receipt(risk_flags={"demo_path": {"value": False, "paths": []}})
        self.assertBlocked(self.stop(), "risk_flags.shared_state")


class ReviewTriggerTest(GateTestCase):
    TWO_PRODUCTION = [
        {"path": "src/app.py", "class": "production", "reason": "code"},
        {"path": "src/util.py", "class": "production", "reason": "code"},
    ]

    def two_file_change(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.edit("src/util.py")
        self.ran("python -m pytest -q")

    def test_build_with_two_production_files_cannot_skip_review(self) -> None:
        self.two_file_change()
        self.receipt(changed_files=self.TWO_PRODUCTION)
        output = self.stop()
        self.assertBlocked(output, "review.required must be true")
        self.assertIn("cannot be recorded as not_required", output["reason"])

    def test_claimed_pass_without_a_reviewer_dispatch_blocks(self) -> None:
        self.two_file_change()
        self.receipt(changed_files=self.TWO_PRODUCTION,
                     review={"required": True, "status": "pass", "findings": []})
        self.assertBlocked(self.stop(), "no reviewer subagent completed")

    def test_review_before_the_last_production_edit_does_not_count(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.reviewed()
        time.sleep(0.05)
        self.edit("src/util.py")
        self.ran("python -m pytest -q")
        self.receipt(changed_files=self.TWO_PRODUCTION,
                     review={"required": True, "status": "pass", "findings": []})
        self.assertBlocked(self.stop(), "no reviewer subagent completed")

    def test_real_reviewer_dispatch_after_the_change_passes(self) -> None:
        self.two_file_change()
        self.reviewed()
        self.receipt(changed_files=self.TWO_PRODUCTION,
                     review={"required": True, "status": "pass", "findings": []})
        self.assertAllowed(self.stop())

    def test_feature_freeze_without_flags_does_not_require_review(self) -> None:
        self.two_file_change()
        self.receipt(deadline_mode="feature_freeze", changed_files=self.TWO_PRODUCTION)
        self.assertAllowed(self.stop())

    def test_demo_survival_with_shared_state_requires_review(self) -> None:
        self.two_file_change()
        flags = {name: {"value": False, "paths": []} for name in RISK_FLAGS}
        flags["shared_state"] = {"value": True, "paths": ["src/util.py"]}
        self.receipt(deadline_mode="demo_survival", changed_files=self.TWO_PRODUCTION, risk_flags=flags)
        self.assertBlocked(self.stop(), "review.required must be true")

    def test_tests_do_not_count_toward_the_production_threshold(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.edit("tests/test_app.py", "def test_x():\n    pass\n")
        self.ran("python -m pytest -q")
        self.receipt(changed_files=[
            {"path": "src/app.py", "class": "production", "reason": "code"},
            {"path": "tests/test_app.py", "class": "non_production", "reason": "test"},
        ])
        self.assertAllowed(self.stop())


class HonestIncompleteTest(GateTestCase):
    def test_incomplete_with_an_explanation_may_stop(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.receipt(status="incomplete", commands=[], acceptance=[],
                     blocked="need the user to approve the schema migration")
        output = self.stop()
        self.assertAllowed(output)
        self.assertIn("status=incomplete", output.get("systemMessage", ""))

    def test_verification_blocked_needs_an_explanation(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.receipt(status="verification_blocked", commands=[], acceptance=[], blocked=None)
        self.assertBlocked(self.stop(), "must explain what is blocked")

    def test_incomplete_still_cannot_misreport_exit_codes(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q", exit_code=2)
        self.receipt(status="incomplete", blocked="tests red")
        self.assertBlocked(self.stop(), "last run exited 2")


class LoopCapTest(GateTestCase):
    def test_gate_gives_up_loudly_after_three_blocks(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.assertBlocked(self.stop(active=False), "attempt 1/3")
        self.assertBlocked(self.stop(active=True), "attempt 2/3")
        self.assertBlocked(self.stop(active=True), "attempt 3/3")
        final = self.stop(active=True)
        self.assertAllowed(final)
        self.assertIn("COMPLETION GATE FAILED", final.get("systemMessage", ""))
        self.assertIn("NOT complete", final["systemMessage"])

    def test_a_new_user_turn_resets_the_counter(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.stop(active=False)
        self.stop(active=True)
        self.assertBlocked(self.stop(active=False), "attempt 1/3")


class LiveRunRegressionTest(GateTestCase):
    """Friction observed in the first live claude-core run (Claude Code 2.1.148)."""

    def test_a_cd_to_the_repository_root_prefix_matches_the_bare_command(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran(f'cd "{self.repo}" && python -m pytest -q')
        self.receipt()
        self.assertAllowed(self.stop())

    def test_a_cd_elsewhere_is_a_different_command(self) -> None:
        other = Path(self._tmp.name) / "other"
        other.mkdir()
        self.start()
        self.edit("src/app.py")
        self.ran(f'cd "{other}" && python -m pytest -q')
        self.receipt()
        self.assertBlocked(self.stop(), "never run in this session")

    def test_python_bytecode_caches_are_not_changes(self) -> None:
        self.start()
        self.edit("__pycache__/calc.cpython-311.pyc", "bytes")
        self.edit("src/__pycache__/app.cpython-311.pyc", "bytes")
        self.edit(".pytest_cache/v/cache/lastfailed", "{}")
        self.assertEqual(self.stop(), {})


class ReviewFindingsRegressionTest(GateTestCase):
    """Defects found by the independent review of the first implementation."""

    def raw_hook(self, command: str, payload: dict) -> subprocess.CompletedProcess:
        # Claude Code writes UTF-8 bytes regardless of the machine's code page. The
        # hook runs from a neutral non-git directory, so a garbled cwd cannot fall
        # back to some other repository and pass by accident.
        neutral = Path(self._tmp.name) / "neutral"
        neutral.mkdir(exist_ok=True)
        return subprocess.run(
            [sys.executable, str(GATE), command],
            input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            capture_output=True, timeout=60, cwd=neutral,
        )

    def test_gate_works_in_a_repository_under_a_non_ascii_path(self) -> None:
        repo = Path(self._tmp.name) / "桌面" / "專案"
        repo.mkdir(parents=True)
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "t@example.com")
        git(repo, "config", "user.name", "t")
        (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-qm", "init")
        event = {"session_id": self.session, "cwd": str(repo)}
        self.assertEqual(self.raw_hook("session-start", {**event, "hook_event_name": "SessionStart"}).returncode, 0)
        (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
        result = self.raw_hook("stop", {**event, "hook_event_name": "Stop", "stop_hook_active": False})
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout.decode("ascii"))
        self.assertBlocked(output, "1 file(s) changed: a.py")

    def test_background_command_is_not_evidence_of_a_pass(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.hook("record", hook_event_name="PostToolUse", tool_name="Bash",
                  tool_input={"command": "python -m pytest -q", "run_in_background": True})
        self.receipt()
        self.assertBlocked(self.stop(), "last run exited None")

    def test_background_reviewer_launch_is_not_a_completed_review(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.edit("src/util.py")
        self.ran("python -m pytest -q")
        self.hook("record", hook_event_name="PostToolUse", tool_name="Agent",
                  tool_input={"subagent_type": "kit-core:reviewer", "run_in_background": True})
        self.receipt(changed_files=ReviewTriggerTest.TWO_PRODUCTION,
                     review={"required": True, "status": "pass", "findings": []})
        self.assertBlocked(self.stop(), "no reviewer subagent completed")

    def test_default_async_reviewer_launch_is_not_a_completed_review(self) -> None:
        """Observed live on 2.1.148: no run_in_background in tool_input, yet the
        subagent ran async and PostToolUse fired at launch."""
        self.start()
        self.edit("src/app.py")
        self.edit("src/util.py")
        self.ran("python -m pytest -q")
        self.hook("record", hook_event_name="PostToolUse", tool_name="Agent",
                  tool_input={"subagent_type": "kit-core:reviewer", "prompt": "review"},
                  tool_response={"status": "async_launched", "isAsync": True, "agentId": "a1"})
        self.receipt(changed_files=ReviewTriggerTest.TWO_PRODUCTION,
                     review={"required": True, "status": "pass", "findings": []})
        self.assertBlocked(self.stop(), "no reviewer subagent completed")

    def test_subagent_stop_records_a_finished_reviewer(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.edit("src/util.py")
        self.ran("python -m pytest -q")
        self.hook("record", hook_event_name="PostToolUse", tool_name="Agent",
                  tool_input={"subagent_type": "kit-core:reviewer", "run_in_background": True})
        self.hook("record", hook_event_name="SubagentStop", agent_type="kit-core:reviewer",
                  agent_id="a1", last_assistant_message="VERDICT: PASS")
        self.receipt(changed_files=ReviewTriggerTest.TWO_PRODUCTION,
                     review={"required": True, "status": "pass", "findings": []})
        self.assertAllowed(self.stop())

    def test_every_stop_decision_leaves_a_verdict_on_disk(self) -> None:
        self.start()
        self.edit("src/app.py")
        for active in (False, True, True, True):
            self.stop(active=active)
        verdict = json.loads((self.repo / ".git" / "claude-kit" / "last-verdict.json").read_text(encoding="utf-8"))
        self.assertEqual(verdict["verdict"], "gate_failed")
        self.assertEqual(verdict["session_id"], self.session)
        self.assertTrue(verdict["problems"])

    def test_passing_stop_records_a_pass_verdict(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("python -m pytest -q")
        self.receipt()
        self.stop()
        verdict = json.loads((self.repo / ".git" / "claude-kit" / "last-verdict.json").read_text(encoding="utf-8"))
        self.assertEqual((verdict["verdict"], verdict["status"]), ("pass", "complete"))

    def test_piped_or_forced_verification_cannot_prove_complete(self) -> None:
        for command in ("python -m pytest -q | tail -5", "python -m pytest -q || true",
                        "python -m pytest -q; exit 0"):
            with self.subTest(command=command):
                self.setUp()
                self.start()
                self.edit("src/app.py")
                self.ran(command)
                self.receipt(commands=[{"command": command, "exit_code": 0}])
                self.assertBlocked(self.stop(), "cannot prove a pass")

    def test_a_new_session_reusing_an_id_re_anchors_but_a_resume_does_not(self) -> None:
        other = Path(self._tmp.name) / "other"
        other.mkdir()
        git(other, "init", "-q")
        self.start()
        pointer = Path(tempfile.gettempdir()) / "claude-kit-sessions" / f"{self.session}.json"
        subprocess.run([sys.executable, str(GATE), "session-start"],
                       input=json.dumps({"session_id": self.session, "cwd": str(other), "source": "resume"}),
                       capture_output=True, text=True, timeout=60)
        self.assertEqual(Path(json.loads(pointer.read_text(encoding="utf-8"))["root"]), self.repo.resolve())
        subprocess.run([sys.executable, str(GATE), "session-start"],
                       input=json.dumps({"session_id": self.session, "cwd": str(other), "source": "startup"}),
                       capture_output=True, text=True, timeout=60)
        self.assertEqual(Path(json.loads(pointer.read_text(encoding="utf-8"))["root"]), other.resolve())

    def test_receipt_is_excluded_in_a_linked_worktree(self) -> None:
        worktree = Path(self._tmp.name) / "wt"
        git(self.repo, "worktree", "add", "-q", str(worktree))
        subprocess.run([sys.executable, str(GATE), "session-start"],
                       input=json.dumps({"session_id": self.session, "cwd": str(worktree)}),
                       capture_output=True, text=True, timeout=60)
        (worktree / ".claude-kit").mkdir()
        (worktree / ".claude-kit" / "receipt.json").write_text("{}", encoding="utf-8")
        status = subprocess.run(["git", "-C", str(worktree), "status", "--porcelain"],
                                capture_output=True, text=True).stdout
        self.assertNotIn(".claude-kit", status)

    def test_stop_checks_the_session_repository_even_after_cwd_moves(self) -> None:
        self.start()
        self.edit("src/app.py")
        elsewhere = Path(self._tmp.name) / "plain"
        elsewhere.mkdir()
        result = subprocess.run(
            [sys.executable, str(GATE), "stop"],
            input=json.dumps({"session_id": self.session, "cwd": str(elsewhere), "stop_hook_active": False}),
            capture_output=True, text=True, timeout=60,
        )
        self.assertBlocked(json.loads(result.stdout), "no receipt")


class SecondReviewRegressionTest(GateTestCase):
    """Defects found by the follow-up review."""

    def verdict_env(self) -> tuple:
        path = Path(self._tmp.name) / "launch-verdict.json"
        return path, {**os.environ, "CLAUDE_KIT_VERDICT_FILE": str(path)}

    def test_stop_writes_the_launch_verdict_file(self) -> None:
        path, env = self.verdict_env()
        self.start()
        self.edit("src/app.py")
        self.hook("stop", _env=env, hook_event_name="Stop", stop_hook_active=False)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["verdict"], "blocked")
        self.ran("python -m pytest -q")
        self.receipt()
        self.hook("stop", _env=env, hook_event_name="Stop", stop_hook_active=True)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["verdict"], "pass")

    def test_outside_a_repository_the_launch_verdict_says_so(self) -> None:
        path, env = self.verdict_env()
        outside = Path(self._tmp.name) / "plain"
        outside.mkdir()
        subprocess.run([sys.executable, str(GATE), "stop"], env=env, capture_output=True, timeout=60,
                       input=json.dumps({"session_id": self.session, "cwd": str(outside)}).encode(),
                       cwd=outside)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["verdict"], "no_repository")

    def test_a_crashing_gate_blocks_once_then_fails_loudly_with_a_verdict(self) -> None:
        path, env = self.verdict_env()
        env["PATH"] = str(Path(self._tmp.name) / "no-git-here")  # git cannot start
        first = self.hook("stop", _env=env, hook_event_name="Stop", stop_hook_active=False)
        self.assertEqual(json.loads(first.stdout)["decision"], "block")
        second = json.loads(self.hook("stop", _env=env, hook_event_name="Stop", stop_hook_active=True).stdout)
        self.assertNotEqual(second.get("decision"), "block")
        self.assertIn("COMPLETION GATE CRASHED", second.get("systemMessage", ""))
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["verdict"], "gate_crashed")

    def test_only_simple_or_and_chained_commands_prove_a_pass(self) -> None:
        rejected = [
            "python -m pytest -q; echo ok",
            "python -m pytest -q; true",
            "python -m pytest -q\nexit 0",
            "python -m pytest -q &",
            "python -m pytest -q; $global:LASTEXITCODE=0",
            "python -m pytest -q | tail -5",
            "python -m pytest -q || true",
        ]
        for command in rejected:
            with self.subTest(rejected=command):
                self.setUp()
                self.start()
                self.edit("src/app.py")
                self.ran(command)
                self.receipt(commands=[{"command": command, "exit_code": 0}])
                self.assertBlocked(self.stop(), "cannot prove a pass")

    def test_quoted_separators_and_redirects_are_fine(self) -> None:
        accepted = [
            'python -m pytest -k "a or b" -q',
            'python -c "import sys; sys.exit(0)"',
            'python -m pytest -q 2>&1',
            "npm run build && npm test",
            "grep -E 'a|b' src/app.py",
        ]
        for command in accepted:
            with self.subTest(accepted=command):
                self.setUp()
                self.start()
                self.edit("src/app.py")
                self.ran(command)
                self.receipt(commands=[{"command": command, "exit_code": 0}])
                self.assertAllowed(self.stop())

    def test_git_bash_style_cd_to_the_root_is_normalized(self) -> None:
        drive, rest = str(self.repo.resolve()).split(":", 1)
        bash_path = "/" + drive.lower() + rest.replace("\\", "/")
        self.start()
        self.edit("src/app.py")
        self.ran(f'cd "{bash_path}" && python -m pytest -q')
        self.receipt()
        self.assertAllowed(self.stop())

    def test_a_trailing_stderr_merge_matches_the_bare_command(self) -> None:
        """Observed live: the agent ran `pytest -q 2>&1` and reported `pytest -q`."""
        self.start()
        self.edit("src/app.py")
        self.ran(f'cd "{self.repo}" && python -m pytest -q 2>&1')
        self.receipt()
        self.assertAllowed(self.stop())

    def test_each_turn_starts_in_progress_and_a_session_starts_ok(self) -> None:
        """Third review: an interrupted turn (no Stop) must not inherit the last OK."""
        path, env = self.verdict_env()
        self.hook("session-start", _env=env, hook_event_name="SessionStart")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["verdict"], "no_changes")
        self.hook("stop", _env=env, hook_event_name="Stop", stop_hook_active=False)
        self.hook("prompt", _env=env, hook_event_name="UserPromptSubmit", prompt="next task")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["verdict"], "in_progress")

    def test_a_restart_inside_the_launch_never_overwrites_a_verdict(self) -> None:
        """Fourth review: /compact, /clear, /resume fire SessionStart again."""
        path, env = self.verdict_env()
        self.hook("session-start", _env=env, hook_event_name="SessionStart", source="startup")
        for last in ("gate_failed", "in_progress"):
            with self.subTest(last=last):
                path.write_text(json.dumps({"verdict": last}), encoding="utf-8")
                for source in ("compact", "clear", "resume", "startup"):
                    self.hook("session-start", _env=env, hook_event_name="SessionStart", source=source)
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["verdict"], last)

    def test_a_stderr_merge_on_its_own_line_is_not_stripped(self) -> None:
        self.start()
        self.edit("src/app.py")
        command = "python -m pytest -q\n2>&1"
        self.ran(command)
        self.receipt(commands=[{"command": command, "exit_code": 0}])
        self.assertBlocked(self.stop(), "cannot prove a pass")

    def test_powershell_call_operator_and_bash_redirect_are_provable(self) -> None:
        for command in ('& "C:\\Program Files\\Python311\\python.exe" -m pytest -q',
                        "python -m pytest -q &>pytest.log"):
            with self.subTest(command=command):
                self.setUp()
                self.start()
                self.edit("src/app.py")
                self.ran(command)
                self.receipt(commands=[{"command": command, "exit_code": 0}])
                self.assertAllowed(self.stop())

    def test_non_object_hook_input_is_handled(self) -> None:
        result = subprocess.run([sys.executable, str(GATE), "stop"], input=b"[1]",
                                capture_output=True, timeout=60, cwd=Path(self._tmp.name))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_relative_cd_is_not_normalized(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.ran("cd . && python -m pytest -q")
        self.receipt()
        self.assertBlocked(self.stop(), "never run in this session")

    def test_only_the_kits_own_reviewer_counts(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.edit("src/util.py")
        self.ran("python -m pytest -q")
        self.reviewed(agent="other-plugin:reviewer")
        self.receipt(changed_files=ReviewTriggerTest.TWO_PRODUCTION,
                     review={"required": True, "status": "pass", "findings": []})
        self.assertBlocked(self.stop(), "no reviewer subagent completed")


class RecorderTest(GateTestCase):
    def evidence(self) -> list:
        state = self.repo / ".git" / "claude-kit" / self.session / "evidence.jsonl"
        return [json.loads(line) for line in state.read_text(encoding="utf-8").splitlines()]

    def test_records_real_exit_codes_and_reviewer_dispatches(self) -> None:
        self.start()
        self.ran("npm test", exit_code=0)
        self.ran("npm test", exit_code=3)
        self.hook("record", hook_event_name="PostToolUseFailure", tool_name="Bash",
                  tool_input={"command": "sleep 99"}, error="interrupted", is_interrupt=True)
        self.reviewed()
        self.hook("record", hook_event_name="PostToolUse", tool_name="Read",
                  tool_input={"file_path": "x"})
        records = self.evidence()
        self.assertEqual([r.get("exit_code") for r in records if r["kind"] == "command"], [0, 3, None])
        self.assertEqual([r["agent"] for r in records if r["kind"] == "subagent"], ["kit-core:reviewer"])
        self.assertEqual(len(records), 4, "non-shell, non-subagent tools are not recorded")

    def test_powershell_tool_is_recorded(self) -> None:
        self.start()
        self.hook("record", hook_event_name="PostToolUse", tool_name="PowerShell",
                  tool_input={"command": "Invoke-Pester"})
        self.assertEqual(self.evidence()[0]["command"], "Invoke-Pester")

    def test_gate_state_never_appears_as_a_change(self) -> None:
        self.start()
        self.ran("npm test")
        self.assertEqual(self.stop(), {})


class FailClosedTest(GateTestCase):
    def test_non_object_receipt_blocks_instead_of_crashing(self) -> None:
        self.start()
        self.edit("src/app.py")
        (self.repo / ".claude-kit").mkdir()
        (self.repo / ".claude-kit" / "receipt.json").write_text("[1, 2]", encoding="utf-8")
        self.assertBlocked(self.stop(), "must be a JSON object")

    def test_wrongly_typed_fields_block_instead_of_crashing(self) -> None:
        self.start()
        self.edit("src/app.py")
        self.receipt(changed_files="src/app.py", risk_flags=[], review="pass", commands={}, acceptance=3)
        output = self.stop()
        self.assertBlocked(output, "changed_files must be a list")


if __name__ == "__main__":
    unittest.main()
