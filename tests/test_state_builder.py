"""Acceptance tests for the prospective routing-state builder.

The dry-run derived ``candidate_paths`` from the frozen worktree diff. That is
retrospective ground truth and a live router cannot have it. Before the request
runs, the only evidence available is the request text plus the repository.

This module answers the question that gates the whole static tier: can a live
builder determine enough state to fast-route anything at all? If it cannot, the
treatment arm of the T1 benchmark would be identical to the control and the run
would be wasted.

The builder is conservative by construction. A task whose scope it cannot prove
is bounded falls through to ``uncertain``, which section 9 already defines as the
safe direction.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.state_builder import (  # noqa: E402
    build_state,
    detect_test_commands,
    extract_acceptance,
    extract_candidate_paths,
)

BOUNDED_REQUEST = """
**Safe zone:** `data/agent/recipes.json` only. You do not need to touch the
agent core or any Python service.

## Checking your work

- `python -m pytest cli/tests/test_recipes.py -q` exits 0.
"""

UNBOUNDED_REQUEST = """
Refactor the persistence layer so that the caching behaviour is consistent
across every backend, and make sure nothing else regresses.
"""

URL_REQUEST = """
[`_read_stdout`](https://github.com/cheenulabs/pi-agent-python-sdk/blob/abc123/src/pi_agent/_transport.py#L192-L214)
parses all records in a read buffer.
"""


def make_repo(root: Path) -> None:
    (root / "data" / "agent").mkdir(parents=True)
    (root / "data" / "agent" / "recipes.json").write_text("{}", encoding="utf-8")
    (root / "src" / "pi_agent").mkdir(parents=True)
    (root / "src" / "pi_agent" / "_transport.py").write_text("", encoding="utf-8")
    (root / "cli" / "tests").mkdir(parents=True)
    (root / "cli" / "tests" / "test_recipes.py").write_text("", encoding="utf-8")
    (root / "src" / "util.py").write_text("", encoding="utf-8")


class ExtractCandidatePathsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        make_repo(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_backticked_existing_path_is_found(self) -> None:
        self.assertIn("data/agent/recipes.json", extract_candidate_paths(BOUNDED_REQUEST, self.repo))

    def test_named_path_that_does_not_exist_is_dropped(self) -> None:
        """A hallucinated or stale path must not prove bounded ownership."""
        request = "Change `src/does_not_exist.py` only."
        self.assertEqual(extract_candidate_paths(request, self.repo), ())

    def test_url_embedded_repo_path_is_found_and_anchor_stripped(self) -> None:
        found = extract_candidate_paths(URL_REQUEST, self.repo)
        self.assertIn("src/pi_agent/_transport.py", found)
        self.assertNotIn("src/pi_agent/_transport.py#L192-L214", found)

    def test_request_without_paths_yields_nothing(self) -> None:
        self.assertEqual(extract_candidate_paths(UNBOUNDED_REQUEST, self.repo), ())

    def test_output_is_sorted_unique_and_deterministic(self) -> None:
        request = "Touch `src/util.py` and `src/util.py` and `data/agent/recipes.json`."
        first = extract_candidate_paths(request, self.repo)
        self.assertEqual(first, tuple(sorted(set(first))))
        self.assertEqual(first, extract_candidate_paths(request, self.repo))

    def test_empty_request_is_handled(self) -> None:
        self.assertEqual(extract_candidate_paths("", self.repo), ())


class ExtractAcceptanceTest(unittest.TestCase):
    def test_backticked_test_command_is_found(self) -> None:
        found = extract_acceptance(BOUNDED_REQUEST)
        self.assertTrue(any("pytest" in item for item in found))

    def test_prose_without_a_command_yields_nothing(self) -> None:
        self.assertEqual(extract_acceptance(UNBOUNDED_REQUEST), ())

    def test_deterministic(self) -> None:
        self.assertEqual(extract_acceptance(BOUNDED_REQUEST), extract_acceptance(BOUNDED_REQUEST))


class DetectTestCommandsTest(unittest.TestCase):
    """Acceptance is a repository fact, not a request fact.

    Real Core reads the repository to learn how to verify a change. Requiring the
    issue text to spell out the command made the fast gate unreachable: five of
    six real benchmark requests name no runnable check at all.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_pyproject_implies_pytest(self) -> None:
        (self.repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        self.assertTrue(any("pytest" in item for item in detect_test_commands(self.repo)))

    def test_tests_directory_implies_pytest(self) -> None:
        (self.repo / "tests").mkdir()
        self.assertTrue(any("pytest" in item for item in detect_test_commands(self.repo)))

    def test_package_json_implies_npm_test(self) -> None:
        (self.repo / "package.json").write_text("{}", encoding="utf-8")
        self.assertTrue(any("npm" in item for item in detect_test_commands(self.repo)))

    def test_cargo_implies_cargo_test(self) -> None:
        (self.repo / "Cargo.toml").write_text("[package]\n", encoding="utf-8")
        self.assertTrue(any("cargo" in item for item in detect_test_commands(self.repo)))

    def test_bare_repository_yields_nothing(self) -> None:
        self.assertEqual(detect_test_commands(self.repo), ())

    def test_deterministic(self) -> None:
        (self.repo / "pyproject.toml").write_text("", encoding="utf-8")
        self.assertEqual(detect_test_commands(self.repo), detect_test_commands(self.repo))

    def test_detection_reaches_the_state_and_unblocks_the_fast_gate(self) -> None:
        """A bounded request with no stated command still verifies via the repo."""
        from router.static_router import FAST_DEEPSEEK, route

        (self.repo / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        (self.repo / "data" / "agent").mkdir(parents=True)
        (self.repo / "data" / "agent" / "recipes.json").write_text("{}", encoding="utf-8")
        request = "**Safe zone:** `data/agent/recipes.json` only. Keep it minimal."
        self.assertEqual(route(build_state(request, self.repo)).tier, FAST_DEEPSEEK)


class BuildStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        make_repo(self.repo)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_state_has_the_section_8_shape(self) -> None:
        state = build_state(BOUNDED_REQUEST, self.repo)
        self.assertEqual(set(state), {"task", "repo"})
        self.assertEqual(
            set(state["repo"]),
            {"project_type", "candidate_paths", "estimated_files", "test_commands", "static_flags"},
        )
        self.assertEqual(
            set(state["task"]), {"request", "language", "acceptance_summary", "risk_signals"}
        )

    def test_request_text_is_not_carried_into_the_state(self) -> None:
        """Section 17 forbids logging raw prompts; the state is what gets logged."""
        state = build_state(BOUNDED_REQUEST, self.repo)
        self.assertEqual(state["task"]["request"], "")

    def test_bounded_request_with_acceptance_routes_fast(self) -> None:
        from router.static_router import FAST_DEEPSEEK, route

        self.assertEqual(route(build_state(BOUNDED_REQUEST, self.repo)).tier, FAST_DEEPSEEK)

    def test_unbounded_request_does_not_route_fast(self) -> None:
        from router.static_router import UNCERTAIN, route

        self.assertEqual(route(build_state(UNBOUNDED_REQUEST, self.repo)).tier, UNCERTAIN)

    def test_concurrency_request_does_not_route_fast(self) -> None:
        from router.static_router import UNCERTAIN, route

        request = BOUNDED_REQUEST + "\nAvoid the race condition in the worker.\n"
        state = build_state(request, self.repo)
        self.assertIn("concurrency", state["task"]["risk_signals"])
        self.assertEqual(route(state).tier, UNCERTAIN)

    def test_declared_public_interface_routes_to_expert(self) -> None:
        """Benchmark task C06 shape: a documented standard interface is a contract."""
        from router.static_router import EXPERT_GPT, route

        (self.repo / "src" / "plugins.py").write_text("", encoding="utf-8")
        request = (
            "Load plugins through a documented standard interface. "
            "Touch `src/plugins.py`."
        )
        state = build_state(request, self.repo)
        self.assertTrue(state["repo"]["static_flags"]["shared_contract"])
        self.assertEqual(route(state).tier, EXPERT_GPT)


if __name__ == "__main__":
    unittest.main()
