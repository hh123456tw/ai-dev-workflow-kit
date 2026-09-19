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


class ThreeModeBundleTest(unittest.TestCase):
    def read_text(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def read_json(self, relative: str) -> dict:
        return json.loads(self.read_text(relative))

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
            self.assertNotIn(
                "OPENCODE_DISABLE_DEFAULT_PLUGINS",
                content,
                "default provider plugins are required for model resolution",
            )

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
        self.assertNotIn(
            "OPENCODE_DISABLE_DEFAULT_PLUGINS",
            core,
            "default provider plugins are required for model resolution",
        )
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


if __name__ == "__main__":
    unittest.main()
