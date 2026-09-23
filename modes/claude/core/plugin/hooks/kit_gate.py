#!/usr/bin/env python3
"""Deterministic completion gate for the Claude Code lane.

The real-task baseline recorded a false completion claim on every task. Prompt
rules did not stop that, so this gate does not ask the model whether it is done;
it checks. Three hook entry points share one state directory inside the git dir:

    session-start  records the baseline: HEAD and the digests of already-dirty files
    record         appends what actually ran: shell commands with their real exit
                   codes, and subagent dispatches (the reviewer)
    stop           refuses to let the session stop while files changed since the
                   baseline and `.claude-kit/receipt.json` is missing, stale, or
                   contradicted by the recorded evidence

A receipt may honestly say `incomplete` or `verification_blocked`; the gate only
refuses a receipt that is structurally invalid or that claims something the
evidence does not show. Standard library only, so the hook runs wherever Python
does. State lives under `<git-dir>/claude-kit/`, which git never tracks.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

RECEIPT_DIR = ".claude-kit"
RECEIPT_REL = f"{RECEIPT_DIR}/receipt.json"
STATE_DIRNAME = "claude-kit"

#: Blocks allowed in one continuous stop sequence before the gate lets the session
#: stop anyway, loudly. Claude Code itself overrides a Stop hook after 8 blocks.
MAX_BLOCKS = 3

DEADLINE_MODES = ("build", "feature_freeze", "demo_survival")
RISK_FLAGS = (
    "demo_path",
    "cross_module",
    "concurrency",
    "shared_state",
    "external_api",
    "external_integration",
    "demo_blocking_cross_module_crash",
)
#: Mirrors the Core review rules: Build needs only the file-count threshold; the
#: later deadline modes also need one of these flags.
REVIEW_TRIGGER_FLAGS: Dict[str, Tuple[str, ...]] = {
    "build": (),
    "feature_freeze": ("demo_path", "cross_module", "concurrency", "shared_state", "external_api"),
    "demo_survival": (
        "concurrency",
        "shared_state",
        "external_integration",
        "demo_blocking_cross_module_crash",
    ),
}
STATUSES = ("complete", "incomplete", "verification_blocked")
REVIEW_STATUSES = ("pass", "not_required", "blocked", "findings_open")
SEVERITIES = ("critical", "important", "minor")
ACCEPTANCE_STATUSES = ("pass", "fail", "not_run")
FILE_CLASSES = ("production", "non_production")

NON_PRODUCTION_DIRS = {
    "test", "tests", "__tests__", "spec", "specs",
    "doc", "docs", "fixture", "fixtures", "example", "examples",
}
NON_PRODUCTION_SUFFIXES = (".md", ".rst", ".txt")
NON_PRODUCTION_NAME = re.compile(r"(^test_.*\.py$|_test\.[^.]+$|\.test\.[^.]+$|\.spec\.[^.]+$)")
EXIT_CODE_LINE = re.compile(r"^\s*Exit code (-?\d+)")
SHELL_TOOLS = ("Bash", "PowerShell")
SUBAGENT_TOOLS = ("Agent", "Task")
#: A pass can only be read from the command's own exit code, so only a simple
#: command or an `&&` chain proves one. A pipe reports its last stage, `;` or a
#: newline lets a later statement overwrite the code, `||` masks a failure, and a
#: lone `&` backgrounds the command. Quoted text is removed before the check, so
#: `grep -E "a|b"` and `python -c "a; b"` stay provable; `2>&1` is a redirect.
QUOTED = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'[^']*'")
UNPROVABLE = re.compile(r"[\n;|]|(?<![&>])&(?![&>])")
#: PowerShell's call operator (`& "C:\...\python.exe" ...`) runs one command.
CALL_OPERATOR = re.compile(r"^\s*&\s+")
#: Where the reviewer comes from. Another plugin's `reviewer` does not count.
REVIEWER_AGENT = "kit-core:reviewer"
#: Set by the launcher: this launch's own verdict file, so concurrent sessions in
#: one repository never read each other's decision.
VERDICT_FILE_ENV = "CLAUDE_KIT_VERDICT_FILE"


# --------------------------------------------------------------------------- git


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        timeout=60,
    )


def repo_root(cwd: Path) -> Optional[Path]:
    result = _git(cwd, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return None
    return Path(result.stdout.decode("utf-8", "replace").strip())


def git_dir(root: Path) -> Path:
    result = _git(root, "rev-parse", "--absolute-git-dir")
    return Path(result.stdout.decode("utf-8", "replace").strip())


def head(root: Path) -> Optional[str]:
    result = _git(root, "rev-parse", "--verify", "-q", "HEAD")
    return result.stdout.decode().strip() if result.returncode == 0 else None


def dirty_paths(root: Path) -> Set[str]:
    """Every path git reports as modified, staged, deleted, renamed, or untracked."""
    result = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries = result.stdout.decode("utf-8", "replace").split("\0")
    paths: Set[str] = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        paths.add(path)
        if "R" in status or "C" in status:
            if index < len(entries) and entries[index]:
                paths.add(entries[index])
            index += 1
    return {p for p in paths if not _is_kit_path(p)}


def committed_since(root: Path, base: Optional[str]) -> Set[str]:
    current = head(root)
    if not base or not current or base == current:
        return set()
    result = _git(root, "diff", "--name-only", "-z", base, current)
    if result.returncode != 0:
        return set()
    names = result.stdout.decode("utf-8", "replace").split("\0")
    return {n for n in names if n and not _is_kit_path(n)}


#: Interpreter byproducts that are never production and never the agent's intent.
#: Repositories usually ignore them; a fresh one may not.
CACHE_DIRS = {"__pycache__", ".pytest_cache"}


def _is_kit_path(path: str) -> bool:
    if path == RECEIPT_DIR or path.startswith(RECEIPT_DIR + "/"):
        return True
    return any(part in CACHE_DIRS for part in PurePosixPath(path).parts)


def digest(root: Path, rel: str) -> str:
    target = root / rel
    if not target.is_file():
        return "<absent>"
    return hashlib.sha256(target.read_bytes()).hexdigest()


# ------------------------------------------------------------------------- state


def _safe_session(session_id: Any) -> str:
    text = str(session_id or "unknown")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)[:128] or "unknown"


def state_dir(root: Path, session_id: Any) -> Path:
    path = git_dir(root) / STATE_DIRNAME / _safe_session(session_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_excluded(root: Path) -> None:
    """Keep the receipt out of `git status` without touching tracked files."""
    # --git-path: a linked worktree reads the shared info/exclude, not its own.
    result = _git(root, "rev-parse", "--git-path", "info/exclude")
    exclude = root / result.stdout.decode("utf-8", "replace").strip()
    line = f"/{RECEIPT_DIR}/"
    try:
        existing = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    except OSError:
        return
    if line in existing.splitlines():
        return
    exclude.parent.mkdir(parents=True, exist_ok=True)
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write(f"{prefix}{line}\n")


def _pointer(session_id: Any) -> Path:
    return Path(tempfile.gettempdir()) / "claude-kit-sessions" / f"{_safe_session(session_id)}.json"


def session_root(data: Dict[str, Any]) -> Optional[Path]:
    """The repository the session started in, even after its cwd moved away."""
    pointer = _read_json(_pointer(data.get("session_id")), {})
    recorded = pointer.get("root")
    if recorded and Path(recorded).is_dir() and repo_root(Path(recorded)) is not None:
        return Path(recorded)
    return repo_root(Path(data.get("cwd") or os.getcwd()))


def write_launch_verdict(record: Dict[str, Any]) -> None:
    """The launcher's per-launch file; it reads this instead of parsing git output."""
    target = os.environ.get(VERDICT_FILE_ENV)
    if target:
        _write_json(Path(target), record)


def write_verdict(root: Optional[Path], state: Optional[Path], session_id: Any, verdict: str,
                  status: Optional[str], problems: List[str]) -> None:
    """Leave the decision on disk, so a headless run can be audited afterwards."""
    record = {"verdict": verdict, "status": status, "session_id": str(session_id or ""),
              "problems": problems, "ts": time.time()}
    write_launch_verdict(record)
    if state is not None:
        _write_json(state / "verdict.json", record)
    if root is not None:
        _write_json(git_dir(root) / STATE_DIRNAME / "last-verdict.json", record)


def load_baseline(state: Path) -> Dict[str, Any]:
    return _read_json(state / "baseline.json", {"head": None, "dirty": {}, "ts": 0})


def load_evidence(state: Path) -> List[Dict[str, Any]]:
    path = state / "evidence.jsonl"
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records


def changed_since_baseline(root: Path, baseline: Dict[str, Any]) -> Set[str]:
    before: Dict[str, str] = baseline.get("dirty") or {}
    now = dirty_paths(root)
    changed = {p for p in now if before.get(p) != digest(root, p)}
    changed |= {p for p in before if p not in now}
    changed |= committed_since(root, baseline.get("head"))
    return changed


# --------------------------------------------------------------------- receipts


def is_production_path(path: str) -> bool:
    """The default classification. A receipt may be stricter, never looser."""
    posix = PurePosixPath(path)
    if any(part.lower() in NON_PRODUCTION_DIRS for part in posix.parts[:-1]):
        return False
    name = posix.name.lower()
    if name.endswith(NON_PRODUCTION_SUFFIXES):
        return False
    return not NON_PRODUCTION_NAME.search(name)


def review_required(mode: str, production_count: int, flags: Dict[str, bool]) -> bool:
    if production_count < 2:
        return False
    triggers = REVIEW_TRIGGER_FLAGS[mode]
    if not triggers:
        return True
    return any(flags.get(name) for name in triggers)


def _mtime(root: Path, rel: str) -> float:
    try:
        return (root / rel).stat().st_mtime
    except OSError:
        return 0.0


CD_PREFIX = re.compile(r"""^cd\s+(?:"([^"]+)"|'([^']+)'|(\S+))\s*&&\s*(.+)$""", re.S)


def normalize_command(command: str, root: Path) -> str:
    """Drop a leading `cd <repository root> &&`, which does not change what ran.

    A `cd` anywhere else is kept, so it stays a different command. Only absolute
    targets count; a Git Bash path such as `/c/Users/x` is read as `C:/Users/x`.
    A relative target is kept, because the hook cannot know the shell's cwd.
    """
    text = command.strip()
    # Merging stderr into stdout does not change the exit code. Same line only: a
    # `2>&1` on its own line is a second statement that exits 0.
    text = re.sub(r"[ \t]+2>&1$", "", text)
    match = CD_PREFIX.match(text)
    if not match:
        return text
    target = next(group for group in match.groups()[:3] if group)
    drive = re.match(r"^/([A-Za-z])(/.*)?$", target)
    if drive and os.name == "nt":
        target = f"{drive.group(1)}:{drive.group(2) or '/'}"
    if not Path(target).is_absolute():
        return text
    try:
        same = Path(target).resolve() == root.resolve()
    except OSError:
        same = False
    return match.group(4).strip() if same else text


def is_unprovable(command: str) -> bool:
    return bool(UNPROVABLE.search(CALL_OPERATOR.sub("", QUOTED.sub("", command))))


def _normalize(path: Any) -> str:
    if not isinstance(path, str):
        return ""
    text = path.replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text


def validate(
    root: Path,
    changed: Set[str],
    evidence: List[Dict[str, Any]],
) -> Tuple[List[str], Optional[Dict[str, Any]]]:
    """Return (problems, receipt). An empty problem list means the stop is allowed."""
    receipt_path = root / RECEIPT_REL
    listing = ", ".join(sorted(changed)[:10])
    if not receipt_path.is_file():
        return ([f"no receipt at {RECEIPT_REL}, but {len(changed)} file(s) changed: {listing}"], None)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except ValueError as error:
        return ([f"{RECEIPT_REL} is not valid JSON: {error}"], None)
    if not isinstance(receipt, dict):
        return ([f"{RECEIPT_REL} must be a JSON object"], None)

    problems: List[str] = []
    receipt_mtime = receipt_path.stat().st_mtime
    last_change = max((_mtime(root, p) for p in changed), default=0.0)
    if receipt_mtime < last_change:
        newest = max(changed, key=lambda p: _mtime(root, p))
        problems.append(f"receipt is older than the latest change ({newest}); update it after the last edit")

    status = receipt.get("status")
    if status not in STATUSES:
        problems.append(f"status must be one of {list(STATUSES)}")
    mode = receipt.get("deadline_mode")
    if mode not in DEADLINE_MODES:
        problems.append(f"deadline_mode must be one of {list(DEADLINE_MODES)}")
        mode = "build"

    # Changed files: the receipt must describe exactly what git shows.
    entries = receipt.get("changed_files")
    listed: Dict[str, Dict[str, Any]] = {}
    if not isinstance(entries, list):
        problems.append("changed_files must be a list of {path, class, reason}")
        entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            problems.append("every changed_files entry must be an object")
            continue
        path = _normalize(entry.get("path"))
        if not path:
            problems.append("a changed_files entry has no path")
            continue
        listed[path] = entry
        if entry.get("class") not in FILE_CLASSES:
            problems.append(f"{path}: class must be one of {list(FILE_CLASSES)}")
        if not str(entry.get("reason") or "").strip():
            problems.append(f"{path}: classification needs a reason")
        if (
            entry.get("class") == "non_production"
            and is_production_path(path)
            and not str(entry.get("reason") or "").strip().lower().startswith("generated")
        ):
            problems.append(
                f"{path}: classified non_production, but it is outside tests/docs/fixtures/examples "
                "(only generated output may be downgraded; start the reason with 'generated')"
            )
    missing = sorted(changed - set(listed))
    extra = sorted(set(listed) - changed)
    if missing:
        problems.append(f"changed_files omits files git shows as changed: {', '.join(missing[:10])}")
    if extra:
        problems.append(f"changed_files lists files that did not change: {', '.join(extra[:10])}")
    production = [p for p, e in listed.items() if e.get("class") == "production" and p in changed]

    # Risk flags: every flag recorded, true flags name their paths.
    flags_raw = receipt.get("risk_flags")
    flags: Dict[str, bool] = {}
    if not isinstance(flags_raw, dict):
        problems.append(f"risk_flags must record every flag: {list(RISK_FLAGS)}")
        flags_raw = {}
    for name in RISK_FLAGS:
        value = flags_raw.get(name)
        if not isinstance(value, dict) or not isinstance(value.get("value"), bool):
            problems.append(f"risk_flags.{name} must be {{\"value\": true|false, \"paths\": [...]}}")
            continue
        flags[name] = value["value"]
        if value["value"] and not value.get("paths"):
            problems.append(f"risk_flags.{name} is true but names no affected paths")

    # Review: the gate recomputes the trigger instead of trusting the receipt.
    review = receipt.get("review")
    if not isinstance(review, dict):
        problems.append("review must be an object {required, status, findings}")
        review = {}
    required = review_required(mode, len(production), flags)
    if review.get("required") is not required:
        problems.append(
            f"review.required must be {str(required).lower()} ({mode}, "
            f"{len(production)} production file(s))"
        )
    review_status = review.get("status")
    if review_status not in REVIEW_STATUSES:
        problems.append(f"review.status must be one of {list(REVIEW_STATUSES)}")
    if required and review_status == "not_required":
        problems.append("a required review cannot be recorded as not_required")
    findings = review.get("findings", [])
    if not isinstance(findings, list):
        problems.append("review.findings must be a list")
        findings = []
    open_findings = [
        f for f in findings
        if isinstance(f, dict) and f.get("severity") in ("critical", "important") and not f.get("resolved")
    ]
    for finding in findings:
        if not isinstance(finding, dict) or finding.get("severity") not in SEVERITIES:
            problems.append(f"every finding needs severity in {list(SEVERITIES)}")
            break

    # Commands: every claim must match what the record hook observed.
    commands = receipt.get("commands")
    if not isinstance(commands, list):
        problems.append("commands must be a list of {command, exit_code}")
        commands = []
    observed: Dict[str, Dict[str, Any]] = {}
    for record in evidence:
        if record.get("kind") == "command":
            observed[normalize_command(str(record.get("command", "")), root)] = record
    for claim in commands:
        if not isinstance(claim, dict) or not isinstance(claim.get("command"), str):
            problems.append("every commands entry needs a command string")
            continue
        text = normalize_command(claim["command"], root)
        seen = observed.get(text)
        if seen is None:
            problems.append(f"command was never run in this session (copy it exactly; a leading `cd <repo root> &&` is ignored): {text[:120]}")
            continue
        if claim.get("exit_code") != seen.get("exit_code"):
            problems.append(
                f"command claims exit {claim.get('exit_code')} but its last run exited "
                f"{seen.get('exit_code')}: {text[:120]}"
            )

    acceptance = receipt.get("acceptance")
    if not isinstance(acceptance, list):
        problems.append("acceptance must be a list of {criterion, status}")
        acceptance = []
    for item in acceptance:
        if not isinstance(item, dict) or item.get("status") not in ACCEPTANCE_STATUSES:
            problems.append(f"every acceptance entry needs status in {list(ACCEPTANCE_STATUSES)}")
            break

    if not str(receipt.get("scope") or "").strip():
        problems.append("scope must state what changed and what did not")
    blocked = receipt.get("blocked")
    if blocked is not None and not isinstance(blocked, str):
        problems.append("blocked must be null or a string")

    if status == "complete":
        if blocked:
            problems.append("a complete receipt cannot carry a blocked condition")
        if not commands:
            problems.append("complete requires at least one executed verification command")
        for claim in commands:
            if not isinstance(claim, dict):
                continue
            seen = observed.get(normalize_command(str(claim.get("command", "")), root))
            if seen is None:
                continue
            if is_unprovable(normalize_command(claim["command"], root)):
                problems.append(
                    "a command with ; | || & or a newline cannot prove a pass; run it alone "
                    f"or as an && chain: {claim['command'][:120]}"
                )
            elif seen.get("exit_code") != 0:
                problems.append(f"complete requires every listed command to pass: {claim['command'][:120]}")
            elif float(seen.get("ts", 0)) < last_change:
                problems.append(f"command ran before the latest change; re-run it: {claim['command'][:120]}")
        if not acceptance:
            problems.append("complete requires acceptance coverage")
        elif any(isinstance(i, dict) and i.get("status") != "pass" for i in acceptance):
            problems.append("complete requires every acceptance check to pass")
        if open_findings:
            problems.append(f"{len(open_findings)} Critical/Important finding(s) are unresolved")
        if required:
            if review_status != "pass":
                problems.append("review is required and has not passed")
            last_production = max((_mtime(root, p) for p in production), default=0.0)
            reviews = [
                r for r in evidence
                if r.get("kind") == "subagent"
                and str(r.get("agent", "")) == REVIEWER_AGENT
                and r.get("ok")
                and float(r.get("ts", 0)) >= last_production
            ]
            if not reviews:
                problems.append(
                    "review is required but no reviewer subagent completed after the latest production change"
                )
    elif status in ("incomplete", "verification_blocked"):
        if not str(blocked or "").strip():
            problems.append(f"status {status} must explain what is blocked or remaining in 'blocked'")

    return problems, receipt


# ------------------------------------------------------------------------ hooks


def _emit(payload: Dict[str, Any]) -> None:
    # ASCII-escaped: stdout uses the machine's code page (cp950 here), not UTF-8.
    sys.stdout.write(json.dumps(payload, ensure_ascii=True))
    sys.stdout.flush()


def cmd_session_start(data: Dict[str, Any]) -> int:
    root = repo_root(Path(data.get("cwd") or os.getcwd()))
    # A session that ends before any prompt changed nothing. Only the launch's first
    # start writes this: /compact, /clear and /resume start again inside the same
    # launch and must never erase a failed or in-progress verdict.
    target = os.environ.get(VERDICT_FILE_ENV)
    if target and not Path(target).exists():
        write_launch_verdict({"verdict": "no_changes" if root else "no_repository", "status": None,
                              "problems": [], "ts": time.time()})
    if root is None:
        return 0
    pointer = _pointer(data.get("session_id"))
    pointer.parent.mkdir(parents=True, exist_ok=True)
    # A resumed or compacted session keeps its original repository; a new one
    # (startup, clear) re-anchors even if its id was seen before.
    if data.get("source") not in ("resume", "compact") or not pointer.exists():
        _write_json(pointer, {"root": str(root)})
    state = state_dir(root, data.get("session_id"))
    baseline_path = state / "baseline.json"
    if not baseline_path.exists():
        dirty = {p: digest(root, p) for p in dirty_paths(root)}
        _write_json(baseline_path, {"head": head(root), "dirty": dirty, "ts": time.time()})
    ensure_excluded(root)
    return 0


def cmd_record(data: Dict[str, Any]) -> int:
    root = session_root(data)
    if root is None:
        return 0
    tool = data.get("tool_name")
    tool_input = data.get("tool_input") or {}
    event = data.get("hook_event_name")
    # PostToolUse fires when a background task is launched, not when it finishes.
    # Subagents can run async by default with no run_in_background in the input
    # (observed on 2.1.148), so the response is checked as well. A finished
    # subagent is recorded from SubagentStop instead.
    response = data.get("tool_response")
    response = response if isinstance(response, dict) else {}
    background = bool(
        tool_input.get("run_in_background")
        or response.get("isAsync")
        or response.get("status") == "async_launched"
        or response.get("backgroundTaskId")
    )
    record: Optional[Dict[str, Any]] = None
    if event == "SubagentStop":
        record = {"kind": "subagent", "agent": str(data.get("agent_type", "")), "ok": True}
    elif tool in SHELL_TOOLS:
        exit_code: Optional[int] = None if background else 0
        if event == "PostToolUseFailure":
            match = EXIT_CODE_LINE.match(str(data.get("error") or ""))
            exit_code = int(match.group(1)) if match and not data.get("is_interrupt") else None
        record = {"kind": "command", "tool": tool, "command": str(tool_input.get("command", "")), "exit_code": exit_code}
    elif tool in SUBAGENT_TOOLS:
        record = {"kind": "subagent", "agent": str(tool_input.get("subagent_type", "")),
                  "ok": event == "PostToolUse" and not background}
    if record is None:
        return 0
    record["ts"] = time.time()
    state = state_dir(root, data.get("session_id"))
    with (state / "evidence.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return 0


def cmd_stop(data: Dict[str, Any]) -> int:
    root = session_root(data)
    if root is None:
        write_verdict(None, None, data.get("session_id"), "no_repository", None, [])
        return 0
    state = state_dir(root, data.get("session_id"))
    counter_path = state / "blocks.json"
    blocks = int(_read_json(counter_path, {"count": 0}).get("count", 0)) if data.get("stop_hook_active") else 0

    changed = changed_since_baseline(root, load_baseline(state))
    session_id = data.get("session_id")
    if not changed:
        _write_json(counter_path, {"count": 0})
        write_verdict(root, state, session_id, "no_changes", None, [])
        return 0

    problems, receipt = validate(root, changed, load_evidence(state))
    if not problems:
        _write_json(counter_path, {"count": 0})
        status = receipt.get("status") if receipt else "unknown"
        write_verdict(root, state, session_id, "pass", status, [])
        _emit({"systemMessage": f"Completion gate: receipt verified (status={status}, {len(changed)} changed file(s))."})
        return 0

    blocks += 1
    summary = "\n".join(f"- {p}" for p in problems[:25])
    if blocks > MAX_BLOCKS:
        _write_json(counter_path, {"count": 0})
        write_verdict(root, state, session_id, "gate_failed", None, problems)
        _emit({
            "systemMessage": (
                f"COMPLETION GATE FAILED after {MAX_BLOCKS} attempts. Treat this task as NOT complete, "
                f"whatever the final message says.\n{summary}"
            )
        })
        return 0
    _write_json(counter_path, {"count": blocks})
    write_verdict(root, state, session_id, "blocked", None, problems)
    _emit({
        "decision": "block",
        "reason": (
            f"Completion gate (attempt {blocks}/{MAX_BLOCKS}) refused to stop:\n{summary}\n\n"
            f"Fix {RECEIPT_REL} as the Core rules describe. If the work is not done, say so: "
            "status 'incomplete' or 'verification_blocked' with a 'blocked' explanation is accepted."
        ),
    })
    return 0


def cmd_prompt(data: Dict[str, Any]) -> int:
    """Each turn starts unverified. A turn that never reaches Stop (the user
    interrupts, the Stop hook times out) must not inherit the previous turn's OK."""
    write_launch_verdict({"verdict": "in_progress", "status": None, "problems": [], "ts": time.time()})
    return 0


COMMANDS = {"session-start": cmd_session_start, "prompt": cmd_prompt, "record": cmd_record, "stop": cmd_stop}


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in COMMANDS:
        print(f"usage: kit_gate.py {{{'|'.join(COMMANDS)}}} < hook-input.json", file=sys.stderr)
        return 1
    data: Dict[str, Any] = {}
    try:
        # Claude Code sends UTF-8. sys.stdin would decode it with the machine's code
        # page, garble a non-ASCII cwd, and silently disable the gate.
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
        try:
            data = json.loads(raw) if raw.strip() else {}
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        return COMMANDS[args[0]](data)
    except Exception as error:  # noqa: BLE001 - a broken gate must fail closed at Stop
        if args[0] != "stop":
            return 0
        detail = f"{type(error).__name__}: {error}"
        try:
            write_launch_verdict({"verdict": "gate_crashed", "status": None, "problems": [detail], "ts": time.time()})
        except Exception:  # noqa: BLE001 - the verdict is best effort; the launcher treats none as failure
            pass
        if data.get("stop_hook_active"):
            # Blocking again would loop on a crash the agent cannot fix. Stop, loudly.
            _emit({"systemMessage": f"COMPLETION GATE CRASHED ({detail}). Treat this task as NOT verified."})
        else:
            _emit({"decision": "block", "reason": f"Completion gate crashed ({detail}); fix the gate or the receipt."})
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
