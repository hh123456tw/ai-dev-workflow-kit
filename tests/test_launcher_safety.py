"""Acceptance tests for the hybrid Core launcher's safety guarantees.

The launcher's contract is narrow and must stay narrow: it reads the deployed
Core mode, sets environment variables for one child process, and writes nothing.
These tests enforce that textually, because the risk is not a logic bug -- it is
someone later adding a convenience line that quietly edits the user's OpenCode
configuration.

They also pin the two behaviours that make the script worth having: the model
comes from the router rather than being hardcoded, and -DryRun exits before
anything is launched.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "oc-core-hybrid.ps1"

#: Cmdlets that can create or modify a file. A launcher needs none of them.
WRITE_CMDLETS = (
    "Set-Content",
    "Add-Content",
    "Out-File",
    "New-Item",
    "Copy-Item",
    "Move-Item",
    "Rename-Item",
    "Set-ItemProperty",
    "New-ItemProperty",
    "Export-Csv",
    "Tee-Object",
)

REMOVE_ITEM = re.compile(r"Remove-Item\s+(\S+)")


class LauncherSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SCRIPT.read_text(encoding="utf-8")

    def test_launcher_exists(self) -> None:
        self.assertTrue(SCRIPT.exists())

    def test_no_file_writing_cmdlets(self) -> None:
        for cmdlet in WRITE_CMDLETS:
            with self.subTest(cmdlet=cmdlet):
                self.assertNotIn(cmdlet, self.text)

    def test_every_remove_item_targets_an_environment_variable(self) -> None:
        targets = REMOVE_ITEM.findall(self.text)
        self.assertTrue(targets, "expected the launcher to clear inherited env vars")
        for target in targets:
            with self.subTest(target=target):
                self.assertTrue(
                    target.startswith("Env:"),
                    f"{target} is not an environment variable; the launcher must not remove files",
                )

    def test_launcher_reads_the_core_config_without_writing_it(self) -> None:
        self.assertIn("opencode\\modes\\core", self.text)
        self.assertIn("Test-Path -LiteralPath $config", self.text)

    def test_model_comes_from_the_router_not_a_literal(self) -> None:
        """Hardcoding a model here would silently defeat the router."""
        self.assertIn("--model $decision.model", self.text)
        self.assertNotIn("--model deepseek", self.text)
        self.assertNotIn("--model openai", self.text)

    def test_dry_run_exits_before_launching(self) -> None:
        dry_run_at = self.text.index("if ($DryRun)")
        launch_at = self.text.index("& opencode")
        exit_at = self.text.index("exit 0", dry_run_at)
        self.assertLess(dry_run_at, exit_at)
        self.assertLess(exit_at, launch_at, "-DryRun must exit before opencode starts")

    def test_launcher_uses_the_same_isolation_variables_as_core(self) -> None:
        for variable in (
            "OPENCODE_CONFIG",
            "OPENCODE_CONFIG_DIR",
            "XDG_CONFIG_HOME",
            "OPENCODE_DISABLE_EXTERNAL_SKILLS",
        ):
            with self.subTest(variable=variable):
                self.assertIn(variable, self.text)

    def test_launcher_is_not_deployed_by_setup(self) -> None:
        """It is a measurement tool, so setup must not install it as a mode."""
        setup = (ROOT / "scripts" / "setup-windows.ps1").read_text(encoding="utf-8")
        self.assertNotIn("oc-core-hybrid", setup)


ISOLATION_VARIABLES = (
    "OPENCODE_CONFIG",
    "OPENCODE_CONFIG_DIR",
    "XDG_CONFIG_HOME",
    "OPENCODE_DISABLE_EXTERNAL_SKILLS",
)


@unittest.skipUnless(shutil.which("pwsh"), "pwsh is required to execute the launcher")
class LauncherEnvironmentScopeTest(unittest.TestCase):
    """Run the real launcher in one pwsh session and inspect that session afterwards.

    A script invoked with `&` runs in the caller's process, so `$env:` assignments
    outlive it unless the launcher restores them. A leaked OPENCODE_CONFIG would make
    the next plain `opencode` in that terminal silently run the Core configuration.
    `opencode` is stubbed with a function, which PowerShell resolves before any
    executable, so nothing real is launched.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        home = Path(self._tmp.name)
        core = home / ".config" / "opencode" / "modes" / "core"
        core.mkdir(parents=True)
        (core / "opencode.jsonc").write_text("{}", encoding="utf-8")
        self.home = home
        self.request = home / "req.md"
        self.request.write_text(
            "**Safe zone:** `router/cli.py` only. Keep it minimal.\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_session(self, stub_exit: int) -> subprocess.CompletedProcess:
        # Test-Path tells unset from empty; `[string]$env:X` cannot.
        report = "; ".join(
            f"'{name}=' + [string]$env:{name} + '|defined=' + (Test-Path Env:{name})"
            for name in ISOLATION_VARIABLES
        )
        command = (
            f"$env:USERPROFILE = '{self.home}'; "
            "$env:OPENCODE_CONFIG = 'caller-value'; "
            "Remove-Item Env:OPENCODE_CONFIG_DIR -ErrorAction SilentlyContinue; "
            "Remove-Item Env:XDG_CONFIG_HOME -ErrorAction SilentlyContinue; "
            "Remove-Item Env:OPENCODE_DISABLE_EXTERNAL_SKILLS -ErrorAction SilentlyContinue; "
            "function opencode { $global:LASTEXITCODE = " + str(stub_exit) + " }; "
            f"& '{SCRIPT}' -RequestFile '{self.request}' -RepoRoot '{ROOT}' | Out-Null; "
            "'LAUNCHER_EXIT=' + $LASTEXITCODE; " + report
        )
        env = dict(os.environ)
        return subprocess.run(
            ["pwsh", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )

    def test_caller_environment_is_restored_after_launch(self) -> None:
        result = self.run_session(stub_exit=0)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertIn("OPENCODE_CONFIG=caller-value|defined=True", lines)
        for name in ISOLATION_VARIABLES[1:]:
            with self.subTest(variable=name):
                self.assertIn(f"{name}=|defined=False", lines)

    def test_opencode_exit_code_is_propagated(self) -> None:
        result = self.run_session(stub_exit=7)
        self.assertIn("LAUNCHER_EXIT=7", result.stdout.splitlines(), result.stderr)


if __name__ == "__main__":
    unittest.main()
