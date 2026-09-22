"""Prospective routing-state builder.

The dry-run derived ``candidate_paths`` from the frozen worktree diff. A live
router cannot do that: the diff does not exist until after the task runs. Before
the task runs, the only evidence is the request text and the repository.

This module turns that evidence into a section 8 routing state. It is the piece
that decides whether the static tier can act at all, because section 9's fast
gate needs provably bounded file ownership, and "provably" here means "the request
names paths that actually exist in this repository".

It is deliberately conservative. A path that is named but does not exist is
dropped, so a stale or hallucinated reference cannot prove boundedness. A request
that names nothing falls through to ``uncertain``, which section 9 already treats
as the safe direction.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from router.risk_signals import scan_contract_signals, scan_risk_signals

__all__ = ["build_state", "detect_test_commands", "extract_acceptance", "extract_candidate_paths"]

_BACKTICK = re.compile(r"`([^`\n]+)`")
_URL = re.compile(r"https?://[^\s)\]]+")

#: A bare path-like token, used only on text with commands and URLs removed.
_BARE_PATH = re.compile(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.[A-Za-z0-9]{1,8}")

#: Tokens that mark a backticked span as an executable check rather than a path.
_RUNNER_TOKENS = frozenset(
    {"python", "pytest", "uv", "npm", "pnpm", "yarn", "cargo", "dotnet", "gradle", "mvn", "npx", "bun"}
)

_TRAILING = "`'\").,;:]}\""


def _resolve(candidate: str, repo_root: Path) -> str | None:
    """Return the repo-relative path ``candidate`` points at, if one exists.

    A candidate may be a plain path, or a path embedded in a URL. The longest
    suffix that exists in the repository wins, so
    ``https://.../blob/abc123/src/x.py`` resolves to ``src/x.py``.
    """
    text = candidate.strip().strip("`").rstrip(_TRAILING)
    text = text.split("#", 1)[0].lstrip("/")
    parts = [part for part in text.split("/") if part not in ("", ".", "..")]
    for index in range(len(parts)):
        suffix = "/".join(parts[index:])
        if suffix and (repo_root / suffix).exists():
            return suffix
    return None


def extract_candidate_paths(request: str, repo_root: Union[str, Path]) -> Tuple[str, ...]:
    """Repo-relative paths the request names that actually exist in ``repo_root``.

    Pure and deterministic. Backticked spans are treated as paths only when they
    carry no whitespace; a span with whitespace is a command, and its operands are
    not modification targets.
    """
    repo_root = Path(repo_root)
    candidates: List[str] = []

    for span in _BACKTICK.findall(request):
        stripped = span.strip()
        if stripped and not any(char.isspace() for char in stripped):
            candidates.append(stripped)

    remainder = _BACKTICK.sub(" ", request)

    candidates.extend(_URL.findall(remainder))
    remainder = _URL.sub(" ", remainder)

    candidates.extend(_BARE_PATH.findall(remainder))

    resolved = {path for path in (_resolve(c, repo_root) for c in candidates) if path}
    return tuple(sorted(resolved))


def extract_acceptance(request: str) -> Tuple[str, ...]:
    """Backticked spans in the request that look like executable checks.

    Pure and deterministic, and intentionally narrow: a span qualifies only if it
    contains whitespace and at least one recognised runner token.
    """
    found: List[str] = []
    for span in _BACKTICK.findall(request):
        stripped = span.strip()
        if not stripped or not any(char.isspace() for char in stripped):
            continue
        tokens = re.split(r"[\s;]+", stripped)
        if any(token.strip(_TRAILING).lower() in _RUNNER_TOKENS for token in tokens):
            found.append(stripped)
    return tuple(dict.fromkeys(found))


#: Repository markers that imply a runnable test command. A false positive here
#: would let an unverifiable change through the fast gate, which is the expensive
#: direction, so the table is limited to markers that unambiguously name a runner.
_TEST_RUNNER_SIGNALS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("pyproject.toml", "pytest.ini", "tox.ini", "conftest.py", "tests"), "python -m pytest -q"),
    (("package.json",), "npm test"),
    (("Cargo.toml",), "cargo test"),
    (("go.mod",), "go test ./..."),
)


def detect_test_commands(repo_root: Union[str, Path]) -> Tuple[str, ...]:
    """How this repository runs its tests, inferred from repository markers.

    Acceptance is a repository fact, not a request fact. Benchmark task C01 is
    the proof: its issue text names no runnable command, yet the repository has a
    pytest suite. Requiring the request to spell out the command made the fast
    gate unreachable on five of six real tasks.
    """
    repo_root = Path(repo_root)
    return tuple(
        command
        for markers, command in _TEST_RUNNER_SIGNALS
        if any((repo_root / marker).exists() for marker in markers)
    )


def build_state(
    request: str,
    repo_root: Union[str, Path],
    *,
    language: str = "en",
    project_type: str = "unknown",
) -> Dict[str, Any]:
    """Build a section 8 routing state from a request and its repository.

    The request text itself is never carried into the state: section 17 forbids
    logging raw prompts, and the state is what gets logged.

    Section 9's ``explicit_acceptance`` and ``existing_executable_verification``
    conditions collapse to one value here. Live, both mean "there is a runnable
    check for this change", sourced from the request or the repository. Treating
    them as independent would be a fiction; the gate still requires it to be
    non-empty.
    """
    repo_root = Path(repo_root)
    paths = extract_candidate_paths(request, repo_root)
    checks = tuple(dict.fromkeys(extract_acceptance(request) + detect_test_commands(repo_root)))
    return {
        "task": {
            "request": "",
            "language": language,
            "acceptance_summary": list(checks),
            "risk_signals": list(scan_risk_signals(request)),
        },
        "repo": {
            "project_type": project_type,
            "candidate_paths": list(paths),
            "estimated_files": len(paths),
            "test_commands": list(checks),
            "static_flags": {
                "auth": False,
                "migration": False,
                # A declared public/shared contract change is a section 9 expert
                # override. It is detected rather than declared because the
                # request is the only evidence available before the task runs.
                "shared_contract": bool(scan_contract_signals(request)),
                "destructive": False,
            },
        },
    }
