"""Acceptance tests for the Claude lane (claude-core, claude-ds).

Three layers:

* static: the lane cannot drift from the OpenCode Core contract (same six skills,
  same credential and destructive-git denials, read-only agents, gate wiring);
* deployment: scripts/setup-claude-lane.ps1 really deploys into a temp root and
  passes `claude plugin validate` when claude is installed;
* launcher: the deployed launcher runs inside a real pwsh session against a
  stubbed `claude` function, so the child environment and argv are observed
  directly. PowerShell resolves functions before executables, so nothing real is
  launched and no subscription or API quota is spent.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "modes" / "claude"
CORE = LANE / "core"
PLUGIN = CORE / "plugin"
SETUP = ROOT / "scripts" / "setup-claude-lane.ps1"

CORE_SKILLS = [
    "test-driven-development",
    "systematic-debugging",
    "verification-before-completion",
    "requesting-code-review",
    "receiving-code-review",
    "finishing-a-development-branch",
]
FORBIDDEN_SKILLS = ["brainstorming", "writing-plans", "subagent-driven-development", "using-git-worktrees"]


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    block = text.split("---", 2)[1]
    fields = {}
    for line in block.strip().splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


class StaticContractTest(unittest.TestCase):
    def test_setup_deploys_the_same_six_skills_as_opencode_core(self) -> None:
        for script in (SETUP, ROOT / "scripts" / "setup-windows.ps1"):
            text = script.read_text(encoding="utf-8")
            block = re.search(r"\$CoreSkills = @\((.*?)\)", text, re.S).group(1)
            self.assertEqual(re.findall(r"'([^']+)'", block), CORE_SKILLS, script.name)

    def test_setup_pins_the_same_superpowers_version(self) -> None:
        pin = re.compile(r"\$RequiredSuperpowersVersion = '([^']+)'")
        lane = pin.search(SETUP.read_text(encoding="utf-8")).group(1)
        core = pin.search((ROOT / "scripts" / "setup-windows.ps1").read_text(encoding="utf-8")).group(1)
        self.assertEqual(lane, core)

    def test_rules_name_the_six_skills_and_reject_the_heavy_workflows(self) -> None:
        rules = " ".join((CORE / "CORE.md").read_text(encoding="utf-8").split())
        for skill in CORE_SKILLS:
            self.assertIn(skill, rules)
        self.assertIn("Do not imitate brainstorming, plan-writing, subagent-driven development, or worktree", rules)

    def test_rules_document_every_field_the_gate_checks(self) -> None:
        rules = (CORE / "CORE.md").read_text(encoding="utf-8")
        for field in ("status", "deadline_mode", "changed_files", "risk_flags", "review",
                      "commands", "acceptance", "scope", "blocked", ".claude-kit/receipt.json"):
            self.assertIn(field, rules)

    def test_permissions_mirror_the_core_lead_denials(self) -> None:
        settings = json.loads((CORE / "settings.json").read_text(encoding="utf-8"))
        deny = set(settings["permissions"]["deny"])
        ask = set(settings["permissions"]["ask"])
        lead = (ROOT / "modes" / "core" / "agents" / "core-lead.md").read_text(encoding="utf-8")
        read_denials = re.findall(r'^\s+"([^"]+)": deny$', lead.split("skill:")[0], re.M)
        self.assertTrue(read_denials)
        for pattern in read_denials:
            self.assertIn(f"Read({pattern})", deny)
        bash = lead.split("bash:")[1].split("---")[0]
        # Every shell tool gets the rule: on Windows the lane can also run PowerShell.
        for tool in ("Bash", "PowerShell"):
            for command in re.findall(r'"([^"]+)": deny', bash):
                self.assertIn(f"{tool}({command})", deny)
            for command in re.findall(r'"([^"]+)": ask', bash):
                self.assertIn(f"{tool}({command})", ask)

    def test_plugin_is_named_kit_core(self) -> None:
        manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "kit-core")

    def test_agents_are_read_only(self) -> None:
        for name in ("reviewer", "explorer"):
            with self.subTest(agent=name):
                fields = frontmatter(PLUGIN / "agents" / f"{name}.md")
                self.assertEqual(fields["name"], name)
                tools = {t.strip() for t in fields["tools"].split(",")}
                self.assertEqual(tools, {"Read", "Grep", "Glob"})

    def test_gate_hooks_cover_start_evidence_and_stop(self) -> None:
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        expected = {"SessionStart": "session-start", "UserPromptSubmit": "prompt", "PostToolUse": "record",
                    "PostToolUseFailure": "record", "SubagentStop": "record", "Stop": "stop"}
        self.assertEqual(set(hooks), set(expected))
        for event, command in expected.items():
            handler = hooks[event][0]["hooks"][0]
            self.assertEqual(handler["args"], ["${CLAUDE_PLUGIN_ROOT}/hooks/kit_gate.py", command])
        for event in ("PostToolUse", "PostToolUseFailure"):
            matcher = set(hooks[event][0]["matcher"].split("|"))
            self.assertTrue({"Bash", "PowerShell", "Agent"} <= matcher, event)

    def test_deployed_skills_are_never_vendored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("modes/claude/core/plugin/skills/", ignore)

    def test_launcher_never_writes_user_claude_configuration(self) -> None:
        launcher = (LANE / "claude-lane.ps1").read_text(encoding="utf-8")
        setup = SETUP.read_text(encoding="utf-8")
        for text in (launcher, setup):
            self.assertNotRegex(text, r"(Set-Content|WriteAllText|Copy-Item)[^\n]*\.claude\\")
        self.assertNotIn("SetEnvironmentVariable($name, $saved[$name], 'User')", launcher)
        self.assertNotRegex(launcher, r"SetEnvironmentVariable\([^)]*'(User|Machine)'\)")


def find_superpowers() -> str:
    root = Path.home() / ".cache" / "opencode" / "packages"
    if not root.exists():
        return ""
    for candidate in root.rglob("superpowers"):
        package = candidate / "package.json"
        if package.is_file():
            try:
                if json.loads(package.read_text(encoding="utf-8")).get("version") == "6.3.0":
                    return str(candidate)
            except ValueError:
                continue
    return ""


SUPERPOWERS = find_superpowers() if shutil.which("pwsh") else ""


@unittest.skipUnless(SUPERPOWERS, "pwsh and the pinned Superpowers package are required to deploy")
class DeployedLaneTestCase(unittest.TestCase):
    """Deploys once per class into a temp root; tests run the deployed copy."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.base = Path(cls._tmp.name)
        cls.kit = cls.base / "claude-kit"
        cls.home = cls.base / "home"
        (cls.home / ".claude" / "skills" / "gstack").mkdir(parents=True)
        (cls.home / ".claude" / "skills" / "hyperframes").mkdir(parents=True)
        cls.setup = subprocess.run(
            ["pwsh", "-NoProfile", "-File", str(SETUP), "-TargetRoot", str(cls.kit),
             "-SuperpowersPath", SUPERPOWERS, "-SkipShims"],
            capture_output=True, text=True, timeout=300,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def launch(self, lane: str, *claude_args: str, env: dict = None, stub_exit: int = 0,
               verdict: str = "pass", cwd: Path = None) -> dict:
        """Run the deployed launcher in one pwsh session and report what `claude` saw.

        The stub plays a whole session: unless `verdict` is None it writes the Stop
        verdict to the file the launcher named, as the real gate would.
        """
        stub_body = "" if verdict is None else (
            "if ($env:CLAUDE_KIT_VERDICT_FILE) { [IO.File]::WriteAllText($env:CLAUDE_KIT_VERDICT_FILE, "
            f"'{{\"verdict\": \"{verdict}\", \"problems\": [\"no receipt\"]}}') }}"
        )
        observed = [
            "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL",
            "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_CUSTOM_HEADERS", "CLAUDE_CONFIG_DIR",
            "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "DEEPSEEK_API_KEY",
            "CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH",
            "CLAUDE_CODE_MESSAGING_TOKEN", "CLAUDE_KIT_VERDICT_FILE",
        ]
        env_table = "; ".join(f"'{n}' = [Environment]::GetEnvironmentVariable('{n}')" for n in observed)
        setup_env = "; ".join(
            (f"Remove-Item -LiteralPath 'Env:{k}' -ErrorAction SilentlyContinue" if v is None
             else f"Set-Item -LiteralPath 'Env:{k}' -Value {repr(v)}")
            for k, v in (env or {}).items()
        )
        quoted_args = " ".join("'" + a.replace("'", "''") + "'" for a in claude_args)
        script = f"""
$ErrorActionPreference = 'Stop'
$env:USERPROFILE = '{self.home}'
{setup_env}
$global:seen = $null
function claude {{
  $settingsFile = $null
  for ($i = 0; $i -lt $args.Count; $i++) {{ if ($args[$i] -eq '--settings') {{ $settingsFile = $args[$i + 1] }} }}
  $global:seen = [ordered]@{{
    args = @($args)
    env = [ordered]@{{ {env_table} }}
    settings = if ($settingsFile) {{ Get-Content -LiteralPath $settingsFile -Raw | ConvertFrom-Json }} else {{ $null }}
    settingsFile = $settingsFile
  }}
  {stub_body}
  $global:LASTEXITCODE = {stub_exit}
}}
& '{self.kit / "claude-lane.ps1"}' {lane} {quoted_args} 2>$null
$code = $LASTEXITCODE
$after = [ordered]@{{ {env_table} }}
[ordered]@{{
  exit = $code
  seen = $global:seen
  after = $after
  settingsFileExistsAfter = if ($global:seen) {{ Test-Path -LiteralPath $global:seen.settingsFile }} else {{ $false }}
}} | ConvertTo-Json -Depth 8 -Compress
"""
        result = subprocess.run(["pwsh", "-NoProfile", "-Command", script],
                                capture_output=True, text=True, timeout=120, cwd=cwd or self.base)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout.strip().splitlines()[-1])
        report["stderr"] = result.stderr
        return report


class DeploymentTest(DeployedLaneTestCase):
    def test_setup_succeeds(self) -> None:
        self.assertEqual(self.setup.returncode, 0, self.setup.stdout + self.setup.stderr)
        self.assertIn("CLAUDE_LANE_SETUP_OK", self.setup.stdout)

    @unittest.skipUnless(shutil.which("claude"), "claude CLI not installed")
    def test_plugin_passes_claude_plugin_validate(self) -> None:
        self.assertIn("claude plugin validate: OK", self.setup.stdout)

    def test_exactly_the_six_skills_are_deployed(self) -> None:
        skills = sorted(p.name for p in (self.kit / "core" / "plugin" / "skills").iterdir() if p.is_dir())
        self.assertEqual(skills, sorted(CORE_SKILLS))
        for forbidden in FORBIDDEN_SKILLS:
            self.assertFalse((self.kit / "core" / "plugin" / "skills" / forbidden).exists())

    def test_gate_interpreter_is_pinned_to_an_existing_absolute_path(self) -> None:
        hooks = json.loads((self.kit / "core" / "plugin" / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        manifest = json.loads((self.kit / "core" / "plugin" / "skills" / "manifest.json").read_text(encoding="utf-8-sig"))
        for event in hooks["hooks"].values():
            command = event[0]["hooks"][0]["command"]
            self.assertTrue(Path(command).is_absolute(), command)
            self.assertTrue(Path(command).is_file(), command)
            self.assertEqual(command, manifest["python"])
        self.assertEqual(manifest["superpowers_version"], "6.3.0")
        self.assertEqual(len(hooks["hooks"]), 6, "every gate event is pinned")
        probe = subprocess.run([manifest["python"], "-c", "print('ok')"], capture_output=True, text=True)
        self.assertEqual(probe.stdout.strip(), "ok", "the pinned interpreter must actually run")

    def test_deployed_gate_is_the_tested_gate(self) -> None:
        deployed = (self.kit / "core" / "plugin" / "hooks" / "kit_gate.py").read_bytes()
        self.assertEqual(deployed, (PLUGIN / "hooks" / "kit_gate.py").read_bytes())


class CoreLaunchTest(DeployedLaneTestCase):
    def test_core_loads_the_lane_and_passes_user_arguments_through(self) -> None:
        run = self.launch("core", "-p", "hello world", "--model", "opus")
        self.assertEqual(run["exit"], 0)
        args = run["seen"]["args"]
        self.assertEqual(args[:2], ["--setting-sources", "project,local"])
        self.assertEqual(args[args.index("--plugin-dir") + 1], str(self.kit / "core" / "plugin"))
        self.assertEqual(args[args.index("--append-system-prompt-file") + 1], str(self.kit / "core" / "CORE.md"))
        self.assertEqual(args[-4:], ["-p", "hello world", "--model", "opus"])

    def test_core_strips_leftover_vendor_overrides_from_the_child(self) -> None:
        run = self.launch("core", env={
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5",
            "ANTHROPIC_MODEL": "glm-5",
            "ANTHROPIC_BASE_URL": "https://api.xairouter.com",
            "ANTHROPIC_AUTH_TOKEN": "proxy-token",
            "ANTHROPIC_API_KEY": "sk-test",
            "ANTHROPIC_CUSTOM_HEADERS": "x: y",
            "CLAUDE_CONFIG_DIR": "C:/elsewhere",
        })
        child = run["seen"]["env"]
        for name in ("ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_MODEL",
                     "ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY",
                     "ANTHROPIC_CUSTOM_HEADERS", "CLAUDE_CONFIG_DIR"):
            with self.subTest(variable=name):
                self.assertIsNone(child[name])

    def test_core_does_not_force_the_default_permission_mode(self) -> None:
        """CLAUDE_CODE_SUBPROCESS_ENV_SCRUB silently forces permission mode to default
        (observed live on Claude Code 2.1.148); Core has no credential left to scrub."""
        run = self.launch("core", env={"CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": None})
        self.assertIsNone(run["seen"]["env"]["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"])

    def test_core_runs_standalone_when_started_inside_another_claude_session(self) -> None:
        """Observed live: inherited Desktop host wiring made the child report 'Not logged in'."""
        run = self.launch("core", env={
            "CLAUDECODE": "1",
            "CLAUDE_CODE_CHILD_SESSION": "1",
            "CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH": "1",
            "CLAUDE_CODE_MESSAGING_TOKEN": "host-token",
        })
        child = run["seen"]["env"]
        for name in ("CLAUDECODE", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_CODE_SDK_HAS_HOST_AUTH_REFRESH",
                     "CLAUDE_CODE_MESSAGING_TOKEN"):
            with self.subTest(variable=name):
                self.assertIsNone(child[name])
        self.assertEqual(run["after"]["CLAUDE_CODE_MESSAGING_TOKEN"], "host-token")

    def test_core_drops_a_deepseek_key_it_does_not_use(self) -> None:
        run = self.launch("core", env={"DEEPSEEK_API_KEY": "ds-key"})
        self.assertIsNone(run["seen"]["env"]["DEEPSEEK_API_KEY"])
        self.assertEqual(run["after"]["DEEPSEEK_API_KEY"], "ds-key")

    def test_core_keeps_a_max_setup_token(self) -> None:
        run = self.launch("core", env={"CLAUDE_CODE_OAUTH_TOKEN": "max-token"})
        self.assertEqual(run["seen"]["env"]["CLAUDE_CODE_OAUTH_TOKEN"], "max-token")

    def test_caller_environment_is_restored(self) -> None:
        run = self.launch("core", env={"ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5",
                                       "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": None})
        self.assertEqual(run["after"]["ANTHROPIC_DEFAULT_SONNET_MODEL"], "glm-5")
        self.assertIsNone(run["after"]["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"])

    def test_personal_skills_are_hidden_and_permissions_carried(self) -> None:
        settings = self.launch("core")["seen"]["settings"]
        self.assertEqual(settings["skillOverrides"], {"gstack": "off", "hyperframes": "off"})
        self.assertIn("Read(**/.env)", settings["permissions"]["deny"])

    def test_session_settings_file_is_removed_afterwards(self) -> None:
        self.assertFalse(self.launch("core")["settingsFileExistsAfter"])

    def test_claude_exit_code_is_propagated(self) -> None:
        self.assertEqual(self.launch("core", stub_exit=7)["exit"], 7)

    def test_unknown_lane_is_rejected(self) -> None:
        run = self.launch("gpt")
        self.assertEqual(run["exit"], 2)
        self.assertIsNone(run["seen"])


class GateVerdictSurfaceTest(DeployedLaneTestCase):
    """A headless run must not end in exit 0 unless the gate explicitly said OK."""

    def test_each_launch_gets_its_own_verdict_file_and_cleans_it_up(self) -> None:
        first = self.launch("core")["seen"]["env"]["CLAUDE_KIT_VERDICT_FILE"]
        second = self.launch("core")["seen"]["env"]["CLAUDE_KIT_VERDICT_FILE"]
        self.assertNotEqual(first, second, "concurrent sessions must not share a verdict")
        self.assertFalse(Path(first).exists())

    def test_verdict_variable_does_not_leak_into_the_caller(self) -> None:
        self.assertIsNone(self.launch("core")["after"]["CLAUDE_KIT_VERDICT_FILE"])

    def test_ok_verdicts_keep_exit_0(self) -> None:
        for verdict in ("pass", "no_changes", "no_repository"):
            with self.subTest(verdict=verdict):
                self.assertEqual(self.launch("core", verdict=verdict)["exit"], 0)

    def test_failing_verdicts_turn_exit_0_into_3(self) -> None:
        for verdict in ("gate_failed", "blocked", "gate_crashed", "in_progress"):
            with self.subTest(verdict=verdict):
                run = self.launch("core", verdict=verdict)
                self.assertEqual(run["exit"], 3)
                self.assertIn(f"COMPLETION GATE {verdict.upper()}", run["stderr"])

    def test_no_verdict_at_all_is_a_failure(self) -> None:
        run = self.launch("core", verdict=None)
        self.assertEqual(run["exit"], 3)
        self.assertIn("PRODUCED NO VERDICT", run["stderr"])

    def test_claude_failure_code_is_kept(self) -> None:
        self.assertEqual(self.launch("core", verdict=None, stub_exit=5)["exit"], 5)

    def test_non_session_commands_need_no_verdict(self) -> None:
        for args in (("--version",), ("auth", "status"), ("plugin", "validate", "."),
                     ("--debug", "mcp", "list"), ("--verbose", "--help")):
            with self.subTest(args=args):
                self.assertEqual(self.launch("core", *args, verdict=None)["exit"], 0)

    def test_a_flag_value_never_exempts_a_session(self) -> None:
        """Fourth review: `--add-dir config` made `config` look like a subcommand."""
        for args in (("--add-dir", "config", "fix the bug"), ("--agent", "agents", "go"), ("-p", "update")):
            with self.subTest(args=args):
                self.assertEqual(self.launch("core", *args, verdict=None)["exit"], 3)

    def test_works_from_a_non_ascii_directory(self) -> None:
        repo = self.base / "桌面" / "專案"
        repo.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        run = self.launch("core", verdict="gate_failed", cwd=repo)
        self.assertEqual(run["exit"], 3)


class DeepSeekLaunchTest(DeployedLaneTestCase):
    def test_refuses_without_a_deepseek_key(self) -> None:
        run = self.launch("ds", env={"DEEPSEEK_API_KEY": None})
        self.assertEqual(run["exit"], 2)
        self.assertIsNone(run["seen"], "claude must not start without the key")

    def test_routes_to_deepseek_with_every_alias_pinned_to_flash(self) -> None:
        run = self.launch("ds", "-p", "hi", env={
            "DEEPSEEK_API_KEY": "ds-key",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5",
            "ANTHROPIC_API_KEY": "sk-anthropic",
            "CLAUDE_CODE_OAUTH_TOKEN": "max-token",
        })
        self.assertEqual(run["exit"], 0)
        child = run["seen"]["env"]
        self.assertEqual(child["ANTHROPIC_BASE_URL"], "https://api.deepseek.com/anthropic")
        self.assertEqual(child["ANTHROPIC_AUTH_TOKEN"], "ds-key")
        for name in ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL"):
            self.assertEqual(child[name], "deepseek-flash[1m]", name)
        self.assertEqual(child["ANTHROPIC_DEFAULT_HAIKU_MODEL"], "deepseek-flash")
        self.assertEqual(child["CLAUDE_CODE_SUBAGENT_MODEL"], "deepseek-flash")
        self.assertEqual(child["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"], "1")

    def test_permission_mode_is_honoured_by_default(self) -> None:
        """Scrubbing makes Claude Code force the default permission mode, which
        overrides a requested bypass/acceptEdits; it is therefore opt-in."""
        run = self.launch("ds", "--permission-mode", "bypassPermissions",
                          env={"DEEPSEEK_API_KEY": "k", "CLAUDE_DS_SCRUB": None,
                               "CLAUDE_CODE_SUBPROCESS_ENV_SCRUB": "1"})
        self.assertIsNone(run["seen"]["env"]["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"])
        self.assertIn("bypassPermissions", run["seen"]["args"])

    def test_key_scrubbing_is_opt_in(self) -> None:
        run = self.launch("ds", env={"DEEPSEEK_API_KEY": "k", "CLAUDE_DS_SCRUB": "1"})
        self.assertEqual(run["seen"]["env"]["CLAUDE_CODE_SUBPROCESS_ENV_SCRUB"], "1")

    def test_cannot_reach_the_max_subscription(self) -> None:
        run = self.launch("ds", env={"DEEPSEEK_API_KEY": "ds-key", "CLAUDE_CODE_OAUTH_TOKEN": "max-token",
                                     "ANTHROPIC_API_KEY": "sk-anthropic"})
        child = run["seen"]["env"]
        self.assertIsNone(child["CLAUDE_CODE_OAUTH_TOKEN"])
        self.assertIsNone(child["ANTHROPIC_API_KEY"])
        self.assertEqual(Path(child["CLAUDE_CONFIG_DIR"]), self.kit / "ds-home")
        self.assertFalse((self.kit / "ds-home" / ".credentials.json").exists())

    def test_key_is_not_left_in_the_child_environment_under_its_own_name(self) -> None:
        run = self.launch("ds", env={"DEEPSEEK_API_KEY": "ds-key"})
        self.assertIsNone(run["seen"]["env"]["DEEPSEEK_API_KEY"])
        self.assertEqual(run["after"]["DEEPSEEK_API_KEY"], "ds-key")

    def test_model_is_overridable(self) -> None:
        run = self.launch("ds", env={"DEEPSEEK_API_KEY": "k", "CLAUDE_DS_MODEL": "deepseek-v4-flash"})
        self.assertEqual(run["seen"]["env"]["ANTHROPIC_MODEL"], "deepseek-v4-flash")


class NotDeployedTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("pwsh"), "pwsh required")
    def test_repository_copy_refuses_to_run_undeployed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            launcher = Path(tmp) / "claude-lane.ps1"
            shutil.copy(LANE / "claude-lane.ps1", launcher)
            result = subprocess.run(
                ["pwsh", "-NoProfile", "-Command",
                 f"function claude {{ 'CALLED' }}; & '{launcher}' core; 'EXIT=' + $LASTEXITCODE"],
                capture_output=True, text=True, timeout=60,
            )
        self.assertIn("EXIT=2", result.stdout)
        self.assertNotIn("CALLED", result.stdout)
        self.assertIn("not deployed", result.stderr)


if __name__ == "__main__":
    unittest.main()
