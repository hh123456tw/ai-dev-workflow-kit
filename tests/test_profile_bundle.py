import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SECRET_PATHS = [
    "**/.env",
    "**/.env.*",
    "**/secrets/**",
    "**/credentials/**",
    "**/*credentials*",
    "**/*secret*",
    "**/*.pem",
    "**/*.key",
    "**/id_rsa",
    "**/id_ed25519",
]

CORE_SKILLS = [
    "test-driven-development",
    "systematic-debugging",
    "verification-before-completion",
    "requesting-code-review",
    "receiving-code-review",
    "finishing-a-development-branch",
]

HEAVY_SKILLS = [
    "brainstorming",
    "writing-plans",
    "subagent-driven-development",
    "using-git-worktrees",
]

SUPERPOWERS_SPEC = "superpowers@git+https://github.com/obra/superpowers.git"

# Core must actively clear an inherited OPENCODE_DISABLE_DEFAULT_PLUGINS and must
# never assign it on: default provider plugins are required to resolve the pinned
# model. A plain "does not mention the variable" check is not enough, because the
# clear form necessarily names it.
CORE_DEFAULT_PLUGINS_ASSIGN = re.compile(
    r"\$env:OPENCODE_DISABLE_DEFAULT_PLUGINS\s*="
    r"|export\s+OPENCODE_DISABLE_DEFAULT_PLUGINS\s*="
)
CORE_DEFAULT_PLUGINS_CLEAR = re.compile(
    r"Remove-Item\s+Env:OPENCODE_DISABLE_DEFAULT_PLUGINS"
    r"|^\s*unset\s+OPENCODE_DISABLE_DEFAULT_PLUGINS",
    re.MULTILINE,
)

CORE_ENTRY_POINTS = (
    "scripts/oc-core.ps1",
    "scripts/oc-core.sh",
    "scripts/desktop-core.ps1",
)

RETIRED_WORKFLOW = re.compile(
    r"(?i)matt\s+pocock|grill|to-spec|to-tickets|wayfinder|\bDAG\b|TEAM V2|Ensemble"
)

RETIRED_PATHS = [
    "profiles",
    "agents/team-lead.md",
    "agents/team-scout.md",
    "agents/team-builder.md",
    "agents/team-reviewer.md",
    "commands/team.md",
    "scripts/oc-product.ps1",
    "scripts/oc-product.sh",
    "scripts/oc-team.ps1",
    "scripts/oc-team.sh",
    "scripts/models.ps1.example",
    "scripts/models.sh.example",
    "modes/core/skills/test-driven-development",
    "modes/core/skills/manifest.json",
    "workflows/team-v2.md",
]


def body(content: str) -> str:
    match = re.match(r"(?s)^---\r?\n.*?\r?\n---\r?\n(.*)$", content)
    return match.group(1) if match else content


def flat(content: str) -> str:
    return re.sub(r"\s+", " ", content)


def section(content: str, heading: str) -> str:
    match = re.search(
        rf"(?ms)^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)",
        content,
    )
    return match.group(1) if match else ""


def permission_section(content: str, key: str) -> str:
    match = re.search(
        rf"(?m)^  {key}:\r?\n((?:    \S.*(?:\r?\n|$))+)",
        content,
    )
    return match.group(1) if match else ""


class ThreeModeBundleTest(unittest.TestCase):
    def read_text(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def read_json(self, relative: str) -> dict:
        return json.loads(self.read_text(relative))

    def assert_core_clears_default_plugins(self, relative: str) -> None:
        content = self.read_text(relative)
        self.assertNotRegex(
            content,
            CORE_DEFAULT_PLUGINS_ASSIGN,
            f"{relative}: default provider plugins are required for model resolution",
        )
        self.assertRegex(
            content,
            CORE_DEFAULT_PLUGINS_CLEAR,
            f"{relative}: must clear an inherited OPENCODE_DISABLE_DEFAULT_PLUGINS",
        )

    def test_retired_artifacts_are_gone(self) -> None:
        for relative in RETIRED_PATHS:
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_three_modes_are_isolated_and_configured(self) -> None:
        vanilla = self.read_json("modes/vanilla/opencode.jsonc")
        stable = self.read_json("modes/stable/opencode.jsonc")
        core = self.read_json("modes/core/opencode.jsonc")

        self.assertEqual(vanilla["default_agent"], "build")
        self.assertEqual(stable["default_agent"], "stable-lead")
        self.assertEqual(core["default_agent"], "core-lead")

        for name, config in (("vanilla", vanilla), ("stable", stable), ("core", core)):
            self.assertEqual(config["model"], "openai/gpt-5.6-sol", name)
            self.assertEqual(config["small_model"], "deepseek/deepseek-v4-flash", name)

        self.assertIn(SUPERPOWERS_SPEC, vanilla["plugin"])
        self.assertIn(SUPERPOWERS_SPEC, stable["plugin"])
        self.assertNotIn("plugin", core)
        self.assertEqual(core["subagent_depth"], 1)

        self.assertIn("modes/core/skills/", self.read_text(".gitignore"))

    def test_codegraph_canary_is_pinned_core_only_and_keeps_control_clean(self) -> None:
        control = self.read_json("modes/core/opencode.jsonc")
        treatment = self.read_json("modes/core/opencode-codegraph.jsonc")
        self.assertNotIn("mcp", control)
        self.assertEqual(treatment["default_agent"], "core-lead")
        self.assertEqual(treatment["model"], control["model"])
        self.assertEqual(treatment["small_model"], control["small_model"])
        self.assertNotIn("plugin", treatment)
        self.assertEqual(set(treatment["mcp"]), {"codegraph"})
        server = treatment["mcp"]["codegraph"]
        self.assertEqual(server["type"], "local")
        self.assertTrue(server["enabled"])
        self.assertIn("v0.20.1", server["command"][0])
        self.assertEqual(server["command"][1:], ["--mcp", "--profile=core"])

        installer = self.read_text("scripts/install-codegraph-windows.ps1")
        for phrase in (
            "v0.20.1",
            "codegraph-server-win32-x64.exe",
            "onnxruntime.dll",
            "aa1b6108217c119af6ac444b8652a0eadcfe2c343bff78ead2edd15b6b7b15b1",
            "52f8ebe8f08f369a44fed6d1cb680c7c89169795e1c2949ee25b88b538ef0948",
            ".sha256",
            "Get-FileHash",
        ):
            self.assertIn(phrase, installer, phrase)

        launcher = self.read_text("scripts/oc-core-codegraph.ps1")
        for phrase in (
            "opencode-codegraph.jsonc",
            "v0.20.1",
            "--pure",
            "OPENCODE_CONFIG_DIR",
            "CODEGRAPH_HOME",
            "OPENCODE_DISABLE_EXTERNAL_SKILLS",
            "Get-FileHash",
        ):
            self.assertIn(phrase, launcher, phrase)
        for pinned_hash in (
            "aa1b6108217c119af6ac444b8652a0eadcfe2c343bff78ead2edd15b6b7b15b1",
            "52f8ebe8f08f369a44fed6d1cb680c7c89169795e1c2949ee25b88b538ef0948",
        ):
            self.assertIn(pinned_hash, launcher)
            self.assertIn(pinned_hash, installer)
        self.assert_core_clears_default_plugins("scripts/oc-core-codegraph.ps1")

        setup = self.read_text("scripts/setup-windows.ps1")
        self.assertIn("opencode-codegraph.jsonc", setup)
        self.assertIn("oc-core-codegraph.ps1", setup)
        self.assertIn("oc-core-codegraph.cmd", setup)

        manifest = self.read_text(
            "docs/research/2026-09-20-codegraph-core-canary.md"
        )
        for phrase in (
            "CodeGraph-only",
            "oc-core",
            "oc-core-codegraph",
            "paired",
            "strict success",
            "input tokens",
            "wall time",
            "get_edit_context",
            "get_ai_context",
            "symbol_search",
            "persistent memory",
            "Jev",
        ):
            self.assertIn(phrase, manifest, phrase)

    def test_core_lead_is_autonomous_and_limited_to_core_skills(self) -> None:
        lead = self.read_text("modes/core/agents/core-lead.md")

        self.assertNotRegex(lead, re.compile(r"(?m)^model:"))
        self.assertNotRegex(body(lead), RETIRED_WORKFLOW)
        flat_lead = flat(lead)
        for phrase in (
            "Start immediately",
            "irreversible or destructive",
            "security- or credential-sensitive",
            "destructive data or schema migration",
            "At most one writer is active at a time",
        ):
            self.assertIn(phrase, flat_lead, phrase)

        for skill in CORE_SKILLS:
            self.assertRegex(lead, re.compile(rf"(?m)^    {re.escape(skill)}: allow$"))
        for skill in HEAVY_SKILLS:
            self.assertNotRegex(lead, re.compile(rf"(?m)^    {re.escape(skill)}: allow$"))
        self.assertRegex(lead, re.compile(r'(?m)^    "\*": deny\s*$'))

    def test_launchers_enforce_core_isolation_only(self) -> None:
        core = self.read_text("scripts/oc-core.ps1")
        core_sh = self.read_text("scripts/oc-core.sh")
        vanilla = self.read_text("scripts/oc-vanilla.ps1")
        vanilla_sh = self.read_text("scripts/oc-vanilla.sh")

        for content in (core, core_sh):
            self.assertIn("--pure", content)
            self.assertIn("XDG_CONFIG_HOME", content)
            self.assertIn("OPENCODE_CONFIG_DIR", content)
            self.assertIn("OPENCODE_DISABLE_EXTERNAL_SKILLS", content)

        for relative in CORE_ENTRY_POINTS:
            self.assert_core_clears_default_plugins(relative)

        for content in (vanilla, vanilla_sh):
            self.assertNotIn("--pure", content)
            self.assertNotIn("XDG_CONFIG_HOME", content)

        for relative in (
            "scripts/oc-vanilla.ps1",
            "scripts/oc-stable.ps1",
            "scripts/oc-core.ps1",
            "scripts/oc-vanilla.sh",
            "scripts/oc-stable.sh",
            "scripts/oc-core.sh",
            "scripts/desktop-vanilla.ps1",
            "scripts/desktop-core.ps1",
            "scripts/opencode-desktop-common.ps1",
            "scripts/verify-modes.ps1",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

    def test_vanilla_and_stable_clear_default_plugins(self) -> None:
        # Vanilla and Stable must clear an inherited OPENCODE_DISABLE_DEFAULT_PLUGINS
        # so the built-in provider plugins stay enabled for the pinned model. Only
        # the Core entry points were covered before.
        for relative in (
            "scripts/oc-vanilla.ps1",
            "scripts/oc-vanilla.sh",
            "scripts/oc-stable.ps1",
            "scripts/oc-stable.sh",
            "scripts/desktop-vanilla.ps1",
        ):
            self.assert_core_clears_default_plugins(relative)

    def test_primary_agents_deny_credential_paths(self) -> None:
        # The binding requirement denies credential paths in every agent. Only the
        # four workers were covered; the two primary agents were not.
        for relative in ("agents/stable-lead.md", "modes/core/agents/core-lead.md"):
            content = self.read_text(relative)
            for pattern in SECRET_PATHS:
                self.assertRegex(
                    content,
                    re.compile(rf'(?m)^    "{re.escape(pattern)}": deny\s*$'),
                    f"{relative} {pattern}",
                )

    def test_desktop_wrappers_use_separate_user_data_dirs(self) -> None:
        core = self.read_text("scripts/desktop-core.ps1")
        vanilla = self.read_text("scripts/desktop-vanilla.ps1")

        self.assertIn("user-data-dir", core)
        self.assertIn("user-data-dir", vanilla)
        self.assertIn("desktop-core", core)
        self.assertIn("desktop-vanilla", vanilla)
        self.assertIn("XDG_CONFIG_HOME", core)
        self.assertIn("OPENCODE_CONFIG_DIR", core)
        self.assertIn("OPENCODE_DISABLE_EXTERNAL_SKILLS", core)
        self.assert_core_clears_default_plugins("scripts/desktop-core.ps1")
        # The Desktop app is Electron and does not forward --pure to its OpenCode
        # sidecar, so Desktop isolation rests on OPENCODE_CONFIG_DIR,
        # XDG_CONFIG_HOME, and OPENCODE_DISABLE_EXTERNAL_SKILLS; --pure is required
        # only of the two CLI Core launchers.
        self.assertNotIn(
            "--pure",
            core,
            "the Desktop wrapper must not rely on --pure; Electron does not "
            "forward it, so Desktop isolation rests on OPENCODE_CONFIG_DIR, "
            "XDG_CONFIG_HOME, and OPENCODE_DISABLE_EXTERNAL_SKILLS",
        )
        self.assertNotIn("XDG_CONFIG_HOME", vanilla)

    def test_setup_deploys_modes_and_pins_superpowers(self) -> None:
        win = self.read_text("scripts/setup-windows.ps1")
        unix = self.read_text("scripts/setup-unix.sh")

        for name, setup in (("windows", win), ("unix", unix)):
            self.assertIn("6.3.0", setup, name)
            self.assertIn("modes", setup, name)
            self.assertIn("core-lead.md", setup, name)
            self.assertIn("finishing-a-development-branch", setup, name)
            self.assertIn("manifest.json", setup, name)
            self.assertIn("team-lead.md", setup, name)
            self.assertIn("ensemble.json", setup, name)
            self.assertIn("oc-product", setup, name)
            self.assertNotIn("mattpocock/skills", setup, name)
            self.assertNotIn("ensemble.json.template", setup, name)

        self.assertIn("CleanLegacy", win)
        self.assertIn("--clean-legacy", unix)
        self.assertIn("OpenCode Vanilla", win)
        self.assertIn("OpenCode Core", win)
        self.assertIn("the stock OpenCode shortcut was not modified", win)
        for launcher in ("oc-vanilla", "oc-stable", "oc-core"):
            self.assertIn(launcher, win)

        # The shim and *.ps1 backups must actually copy. A wildcard passed to
        # -LiteralPath copies nothing, and -ErrorAction SilentlyContinue hides it.
        modes_backup = re.search(
            r"(?s)\$modesSource = Join-Path \$OcConfig 'modes'.*?(?=\$coreSource)",
            win,
        )
        assert modes_backup is not None
        modes_backup_text = modes_backup.group(0)
        self.assertIn(
            "Get-ChildItem -Path (Join-Path $modesSource '*.ps1')",
            modes_backup_text,
        )
        self.assertIn("Copy-Item -LiteralPath $modeScript.FullName", modes_backup_text)
        self.assertNotRegex(modes_backup_text, re.compile(r"Copy-Item -LiteralPath[^\n]*\*"))
        self.assertNotIn("SilentlyContinue", modes_backup_text)

        shim_backup = re.search(
            r"(?s)# CLI shims and the two mode shortcuts this repository owns\..*?"
            r"\nforeach \(\$desktop",
            win,
        )
        assert shim_backup is not None
        shim_backup_text = shim_backup.group(0)
        self.assertIn(
            "Get-ChildItem -Path (Join-Path $binSource 'oc-*.cmd')",
            shim_backup_text,
        )
        self.assertIn("Copy-Item -LiteralPath $shim.FullName", shim_backup_text)
        self.assertNotRegex(shim_backup_text, re.compile(r"Copy-Item -LiteralPath[^\n]*\*"))
        self.assertNotIn("SilentlyContinue", shim_backup_text)

        # The stock OpenCode shortcut must be absent from the deletion list, not
        # merely absent from a reassuring print.
        self.assertNotIn("OpenCode.lnk", win)
        self.assertNotIn("'OpenCode'", win)
        self.assertRegex(
            win, re.compile(r"\$label in @\('OpenCode PRODUCT', 'OpenCode TEAM'\)")
        )
        self.assertNotIn(".lnk", unix)
        # Version handling compares against the pin and fails loudly, with no
        # silent full-plugin fallback.
        self.assertRegex(win, re.compile(r"\$version -ne \$RequiredSuperpowersVersion"))
        self.assertRegex(
            win,
            re.compile(
                r'throw "Superpowers \$version found but '
                r'\$RequiredSuperpowersVersion is required'
            ),
        )
        self.assertNotRegex(win, re.compile(r"(?i)fall\s?back"))
        self.assertRegex(unix, re.compile(r"\$VERSION.*\$REQUIRED_SUPERPOWERS_VERSION"))
        # The mismatch branch must actually fail: removing the || { ...; exit 1; }
        # arm would otherwise still satisfy the comparison-regex check above.
        self.assertRegex(
            unix,
            re.compile(
                r'\|\| \{ echo "Superpowers \$VERSION found but '
                r'\$REQUIRED_SUPERPOWERS_VERSION is required[^"]*" >&2; exit 1; \}'
            ),
        )
        self.assertNotRegex(unix, re.compile(r"(?i)fall\s?back"))

        # gstack routing is shared and portable, so a fresh machine must get the
        # config and an existing one must be left untouched. Read the install block
        # itself, so deleting it fails the suite instead of leaving a path string.
        unix_gstack = re.search(r"(?s)# gstack routing is shared.*?\nfi", unix)
        assert unix_gstack is not None
        unix_gstack_block = unix_gstack.group(0)
        self.assertIn('[[ ! -e "$GSTACK_CONFIG" ]]', unix_gstack_block)
        self.assertIn('cp "$ROOT/gstack/gstack.jsonc" "$GSTACK_CONFIG"', unix_gstack_block)
        self.assertIn("left untouched", unix_gstack_block)
        self.assertRegex(
            win,
            re.compile(r"Copy-Item \(Join-Path \$RepoRoot 'gstack\\gstack\.jsonc'\)"),
        )
        self.assertIn("gstack.jsonc exists; left untouched", win)

    def test_core_manifest_records_pinned_version_and_six_skills(self) -> None:
        # The deployed manifest is git-ignored, so validate the shape the setup
        # scripts generate: the pinned version plus exactly the six Core skills.
        win = self.read_text("scripts/setup-windows.ps1")
        unix = self.read_text("scripts/setup-unix.sh")

        win_version_match = re.search(
            r"\$RequiredSuperpowersVersion\s*=\s*'([^']+)'", win
        )
        win_skills_match = re.search(r"(?s)\$CoreSkills = @\((.*?)\n\)", win)
        unix_version_match = re.search(
            r'REQUIRED_SUPERPOWERS_VERSION="([^"]+)"', unix
        )
        unix_skills_match = re.search(r"(?s)CORE_SKILLS=\((.*?)\)", unix)
        assert win_version_match is not None
        assert win_skills_match is not None
        assert unix_version_match is not None
        assert unix_skills_match is not None

        win_version = win_version_match.group(1)
        win_skills = re.findall(r"'([a-z][a-z-]*)'", win_skills_match.group(1))
        unix_version = unix_version_match.group(1)
        unix_skills = re.findall(r"([a-z][a-z-]*)", unix_skills_match.group(1))

        for name, version, skills in (
            ("windows", win_version, win_skills),
            ("unix", unix_version, unix_skills),
        ):
            manifest = {"superpowers_version": version, "skills": skills}
            self.assertEqual(manifest["superpowers_version"], "6.3.0", name)
            self.assertEqual(manifest["skills"], CORE_SKILLS, name)

        # Both scripts write the resolved version and the skill list into the
        # manifest they emit.
        self.assertRegex(win, re.compile(r"superpowers_version\s*=\s*\$version"))
        self.assertRegex(win, re.compile(r"skills\s*=\s*\$CoreSkills"))
        self.assertRegex(unix, re.compile(r'"superpowers_version": "%s"'))
        self.assertRegex(unix, re.compile(r'"skills": \['))

    def test_shared_global_config_and_workers(self) -> None:
        global_config = self.read_json("global/opencode.jsonc")
        self.assertEqual(global_config["default_agent"], "stable-lead")
        self.assertIn(SUPERPOWERS_SPEC, global_config["plugin"])
        self.assertNotIn("opencode-ensemble", self.read_text("global/opencode.jsonc"))

        workers = {
            "explorer": self.read_text("agents/explorer.md"),
            "implementer": self.read_text("agents/implementer.md"),
            "reviewer": self.read_text("agents/reviewer.md"),
            "test-writer": self.read_text("agents/test-writer.md"),
        }
        for name, content in workers.items():
            self.assertRegex(
                content,
                re.compile(r"(?m)^model: deepseek/deepseek-v4-flash\s*$"),
                name,
            )
            self.assertNotRegex(body(content), RETIRED_WORKFLOW, name)
            self.assertRegex(content, re.compile(r"(?m)^  task: deny\s*$"), name)
            self.assertRegex(content, re.compile(r"(?m)^  webfetch: deny\s*$"), name)
            for pattern in SECRET_PATHS:
                self.assertRegex(
                    content,
                    re.compile(rf'(?m)^    "{re.escape(pattern)}": deny\s*$'),
                    f"{name} {pattern}",
                )
        for name in ("explorer", "reviewer"):
            self.assertRegex(workers[name], re.compile(r"(?m)^  edit: deny\s*$"), name)
        self.assertRegex(
            workers["implementer"], re.compile(r"(?m)^## Completion handback\s*$")
        )

        # Restore the worker assertions dropped in the refactor: the rules still
        # exist in the agent files, but nothing would catch future drift.
        implementer = workers["implementer"]
        for denial in (
            "git push*",
            "git commit*",
            "git merge*",
            "git rebase*",
            "git reset --hard*",
            "git clean*",
            "git branch -D*",
            "rm -rf*",
        ):
            self.assertRegex(
                implementer,
                re.compile(rf'(?m)^    "{re.escape(denial)}": deny\s*$'),
                denial,
            )
        for bullet in (
            "- Changed files",
            "- Commands run and exact result",
            "- Core acceptance result",
            "- Remaining limitation or blocker",
        ):
            self.assertRegex(
                implementer,
                re.compile(rf"(?m)^{re.escape(bullet)}\s*$"),
                bullet,
            )
        test_writer_edit = permission_section(workers["test-writer"], "edit")
        self.assertRegex(test_writer_edit, re.compile(r'(?m)^    "\*": deny\s*$'))
        self.assertRegex(
            test_writer_edit, re.compile(r'(?m)^    "\*\*/tests/\*\*": allow\s*$')
        )

    def test_documentation_covers_three_modes(self) -> None:
        readme = self.read_text("README.md")
        for token in ("Vanilla", "Stable", "Core", "oc-vanilla", "oc-stable", "oc-core"):
            self.assertIn(token, readme, token)

        agents_doc = self.read_text("AGENTS.md")
        for token in ("Vanilla", "Stable", "Core"):
            self.assertIn(token, agents_doc, token)

        spec = self.read_text(
            "docs/superpowers/specs/2026-09-19-three-mode-opencode-workflows-design.md"
        )
        self.assertIn("Three-Mode OpenCode Workflows Design", spec)
        self.assertIn("Verified limitation: one Desktop instance at a time", spec)
        self.assertIn("deadline-aware read-only reviewer gate", spec)

        # Regression guard: the design must not re-claim concurrent Desktop instances.
        self.assertIn("一次只能開一個實例", readme)
        self.assertNotIn("可以**同時開啟**", readme)
        self.assertIn(
            "only one Desktop instance at a time",
            self.read_text("desktop/opencode/README.md"),
        )

        research = self.read_text(
            "docs/research/2026-09-19-jev-risk-routed-hybrid-core.md"
        )
        self.assertIn("Research proposal only", research)

    def test_core_completion_gate_policy_requirements(self) -> None:
        # Static policy-content check, not a behavior guarantee. Baseline finding:
        # every valid run claimed completion before a required check passed, and one
        # run shipped with its reviewer dispatch denied. Whether a live model obeys
        # this prose is measured by the Phase 3 revalidation, not here.
        lead = self.read_text("modes/core/agents/core-lead.md")
        gate = flat(section(lead, "Completion gate"))
        self.assertNotEqual(gate, "", "core-lead must define a Completion gate section")

        for field in (
            "deadline mode",
            "changed-file count",
            "file classifications",
            "risk flags",
            "exact result and exit codes",
            "acceptance coverage",
            "reviewer status",
            "scope statement",
            "blocked condition",
        ):
            self.assertIn(field, gate, field)

        self.assertIn("verification_blocked", gate)
        self.assertIn("do not claim done", gate)
        self.assertIn("instead of claiming done", gate)
        self.assertIn("re-verify before completion", gate)
        # Polarity-aware: the copula is asserted, so negating the rule fails.
        self.assertIn(
            "dispatch that fails, is denied, times out, or returns no result is a "
            "`verification_blocked` outcome",
            gate,
        )
        self.assertIn("reviewer tool is unavailable", gate)
        self.assertIn("Never treat an unperformed review as a passed review", gate)
        # Baseline C02: the model skipped a required review by calling the change
        # trivial. "not required" must not be an available reviewer status.
        self.assertIn('never record a required review as "not required"', gate)

        agents_doc = self.read_text("AGENTS.md")
        core_behavior = flat(section(agents_doc, "Core behavior"))
        self.assertNotEqual(
            core_behavior, "", "AGENTS.md must define a Core behavior section"
        )
        for phrase in (
            "completion receipt",
            "verification_blocked",
            "deadline mode",
            "Feature Freeze",
            "Demo Survival",
            "demo_path",
            "demo_blocking_cross_module_crash",
            "Classify every changed file",
            "`explorer` is not a substitute",
        ):
            self.assertIn(phrase, core_behavior, phrase)

        readme_core = flat(section(self.read_text("README.md"), "Core 的行為"))
        self.assertIn("`explorer` 不可替代", readme_core)
        self.assertIn("completion receipt", readme_core)
        self.assertIn("Demo Survival", readme_core)
        self.assertIn("demo_path", readme_core)
        self.assertIn("demo_blocking_cross_module_crash", readme_core)

    def test_core_review_trigger_is_objective_and_findings_block(self) -> None:
        # Baseline C02: the "non-trivial multi-file change" trigger was subjective,
        # so the model declared a three-file change trivial and dispatched no
        # reviewer. The trigger must be the changed-file count.
        lead = self.read_text("modes/core/agents/core-lead.md")
        self.assertIn("\n    reviewer: allow\n", lead)
        review = flat(section(lead, "Review"))
        self.assertNotEqual(review, "", "core-lead must define a Review section")

        for phrase in (
            "Build: review is required when a change touches two or more production files",
            "Feature Freeze: review is required only when a change touches two or more production files and at least one",
            "Demo Survival: review is required only when a change touches two or more production files and at least one",
            "Production files are tracked files outside tests, documentation, fixtures, examples, and generated output",
            "Runtime configuration and package manifests count as production",
            "classify every changed file",
            "record every risk flag as true or false with affected paths",
            "demo_path",
            "cross_module",
            "concurrency",
            "shared_state",
            "external_api",
            "external_integration",
            "demo_blocking_cross_module_crash",
            "review_not_required",
            "`reviewer` subagent",
            "`explorer` is not a substitute",
            "not your judgment",
            "authoritative for what they cover",
            "not sufficient for completion",
            "gets a regression test when the correction changes behavior",
        ):
            self.assertIn(phrase, review, phrase)

        self.assertIn(
            "Feature Freeze: review is required only when a change touches two or more production files and at least one of these flags is true: `demo_path`, `cross_module`, `concurrency`, `shared_state`, or `external_api`",
            review,
        )
        self.assertIn(
            "Demo Survival: review is required only when a change touches two or more production files and at least one of these flags is true: `concurrency`, `shared_state`, `external_integration`, or `demo_blocking_cross_module_crash`",
            review,
        )

        deadline = flat(section(lead, "Deadline awareness"))
        self.assertIn(
            "Never invent a deadline; with none stated, use Build discipline and say so",
            deadline,
        )

    def test_core_requires_real_path_measurement_evidence(self) -> None:
        # Baseline finding: Core verified a "<20% warm time" criterion with a
        # synthetic counter while the measured real ratio was 0.335 (false green).
        lead = self.read_text("modes/core/agents/core-lead.md")
        evidence = flat(section(lead, "Real-path evidence"))
        self.assertNotEqual(
            evidence, "", "core-lead must define a Real-path evidence section"
        )

        # Polarity-aware: the prohibition is asserted as one contiguous sentence,
        # so inverting it into permission fails.
        self.assertIn(
            "Do not use a mocked clock, a synthetic counter, implementation "
            "internals, or a self-authored substitute metric as evidence",
            evidence,
        )
        for phrase in (
            "real command, API, or execution path",
            "substitute metric",
            "fixture or input size",
            "threshold",
            "observed value",
            "exit code",
        ):
            self.assertIn(phrase, evidence, phrase)

    def test_reviewer_blocked_smoke_uses_an_isolated_fault_profile(self) -> None:
        relative = "scripts/smoke-core-reviewer-blocked.ps1"
        self.assertTrue((ROOT / relative).is_file(), relative)
        smoke = self.read_text(relative)

        # --auto handles ordinary non-interactive permissions, while an explicit
        # deny in the temporary profile still fault-injects reviewer failure.
        for phrase in (
            "[IO.Path]::GetTempPath()",
            "reviewer: allow",
            "reviewer: deny",
            "OPENCODE_CONFIG_DIR",
            "Remove-Item Env:OPENCODE_CONFIG_CONTENT",
            "Remove-Item Env:OPENCODE_DISABLE_DEFAULT_PLUGINS",
            "--pure",
            "--auto",
            "verification_blocked",
            "CORE_REVIEWER_BLOCKED_SMOKE_PASS",
            "CORE_REVIEWER_BLOCKED_SELFTEST_PASS",
            "final_answer",
            "TaskEvents",
            "NestedOpenCodeCommands",
            "positive completion claim",
            "-SelfTest",
            "finally",
        ):
            self.assertIn(phrase, smoke, phrase)

        self.assertIn(
            "two or more production files",
            smoke,
            "the smoke must exercise the objective reviewer trigger",
        )


if __name__ == "__main__":
    unittest.main()
