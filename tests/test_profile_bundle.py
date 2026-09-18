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

RETIRED_WORKFLOW = re.compile(
    r"(?i)matt\s+pocock|grill|to-spec|to-tickets|wayfinder|\bDAG\b|TEAM V2|Ensemble"
)

# Retired artifacts that must no longer exist anywhere in the repo.
RETIRED_PATHS = [
    "profiles",
    "profiles/product/opencode.jsonc",
    "profiles/team/opencode.jsonc",
    "profiles/team/TEAM_MVP_SPRINT.md",
    "profiles/team/ensemble.json.template",
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
    ".local/README.md",
    "workflows/team-v2.md",
    "prompts/team-v2-upgrade.md",
    "prompts/original-dual-workflow-brief.md",
]


def body(content: str) -> str:
    """Return the prompt body, excluding YAML frontmatter.

    Frontmatter legitimately names retired skills in order to deny them, so prose
    checks must ignore it.
    """
    match = re.match(r"(?s)^---\r?\n.*?\r?\n---\r?\n(.*)$", content)
    return match.group(1) if match else content


def flat(content: str) -> str:
    """Collapse whitespace so phrase assertions survive prose line wrapping."""
    return re.sub(r"\s+", " ", content)


class SingleWorkflowBundleTest(unittest.TestCase):
    def read_text(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def read_json(self, relative: str) -> dict:
        return json.loads(self.read_text(relative))

    def test_retired_workflow_artifacts_are_gone(self) -> None:
        for relative in RETIRED_PATHS:
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_the_global_config_is_the_single_entry_point(self) -> None:
        global_config = self.read_json("global/opencode.jsonc")

        self.assertEqual(global_config["default_agent"], "stable-lead")
        self.assertEqual(global_config["model"], "openai/gpt-5.6-sol")
        self.assertEqual(global_config["small_model"], "deepseek/deepseek-v4-flash")
        self.assertEqual(
            global_config["plugin"],
            ["superpowers@git+https://github.com/obra/superpowers.git"],
        )
        self.assertNotIn("opencode-ensemble", self.read_text("global/opencode.jsonc"))

    def test_the_lead_definition_carries_the_single_workflow_policy(self) -> None:
        lead = self.read_text("agents/stable-lead.md")

        self.assertNotRegex(lead, re.compile(r"(?m)^model:"))
        flat_lead = flat(lead)
        for phrase in (
            "There is one workflow",
            "At most one writer is active at a time",
            "Delegation is conditional, not automatic",
            "its result can be reverted independently",
            "Build the spine first",
            "Progress is judged by artifacts",
            "Demo Survival",
            "Never invent a deadline",
            "cost per successful slice",
            "Workers never approve themselves",
        ):
            self.assertIn(phrase, flat_lead, phrase)

        self.assertNotRegex(body(lead), RETIRED_WORKFLOW)
        for denied in (
            "grill-me",
            "to-tickets",
            "implement",
            "tdd",
            "domain-modeling",
            "codebase-design",
            "handoff",
        ):
            self.assertRegex(lead, re.compile(rf"(?m)^    {re.escape(denied)}: deny$"))

    def test_worker_agents_are_bounded_and_evidence_based(self) -> None:
        agents = {
            "explorer": self.read_text("agents/explorer.md"),
            "implementer": self.read_text("agents/implementer.md"),
            "reviewer": self.read_text("agents/reviewer.md"),
            "test-writer": self.read_text("agents/test-writer.md"),
        }

        for name, content in agents.items():
            self.assertIn("model: deepseek/deepseek-v4-flash", content, name)
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
            self.assertRegex(
                agents[name], re.compile(r"(?m)^  edit: deny\s*$"), name
            )

        implementer = agents["implementer"]
        self.assertRegex(implementer, re.compile(r"(?m)^## Completion handback\s*$"))
        for bullet in (
            "- Changed files",
            "- Commands run and exact result",
            "- Core acceptance result",
            "- Remaining limitation or blocker",
        ):
            self.assertRegex(
                implementer, re.compile(r"(?m)^" + re.escape(bullet) + r"\s*$")
            )
        for command in (
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
                re.compile(rf'(?m)^    "{re.escape(command)}": deny\s*$'),
                command,
            )

        test_writer = agents["test-writer"]
        self.assertRegex(test_writer, re.compile(r'(?m)^    "\*": deny\s*$'))
        self.assertRegex(test_writer, re.compile(r'(?m)^    "\*\*/tests/\*\*": allow\s*$'))

    def test_shared_commands_and_agents_exist(self) -> None:
        for relative in (
            "agents/stable-lead.md",
            "agents/explorer.md",
            "agents/test-writer.md",
            "agents/implementer.md",
            "agents/reviewer.md",
            "commands/stable.md",
            "commands/gstack-qa.md",
            "commands/gstack-review.md",
            "commands/gstack-ship.md",
            "commands/gstack-cso.md",
            "commands/gstack-investigate.md",
            "commands/gstack-plan-ceo-review.md",
            "commands/gstack-design-review.md",
            "commands/gstack-benchmark.md",
            "AGENTS.md",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

        self.assertIn("agent: stable-lead", self.read_text("commands/stable.md"))

        lead = self.read_text("agents/stable-lead.md")
        self.assertIn("Compound learning", lead)
        self.assertIn("40 lines", lead)
        self.assertIn("a required model is unavailable", flat(lead))
        self.assertIn("quota", lead)

    def test_readme_and_agents_document_one_workflow(self) -> None:
        readme = self.read_text("README.md")
        self.assertIn("單一工作流", readme)
        self.assertNotIn("/team", readme)
        self.assertNotIn("oc-team", readme)
        self.assertIn("原始捷徑", readme)
        self.assertIn("```mermaid", readme)
        # The README may explain that the wrapper was retired; it must not
        # advertise it as an entry point (a table row or a bare command line).
        entry_lines = [
            line
            for line in readme.splitlines()
            if re.match(r"^\s*\|.*oc-product", line) or re.match(r"^\s*oc-product", line)
        ]
        self.assertEqual(entry_lines, [], "README must not list oc-product as an entry point")

        agents_doc = self.read_text("AGENTS.md")
        self.assertIn("One workflow", agents_doc)
        self.assertNotIn("/team", agents_doc)
        self.assertIn("cost per successful slice", agents_doc)

        spec = self.read_text("docs/superpowers/specs/2026-09-18-single-workflow-design.md")
        self.assertIn("Keep exactly **one workflow**", spec)
        self.assertIn("cost per successful slice", spec)

    def test_setup_scripts_deploy_globally_and_offer_legacy_cleanup(self) -> None:
        win = self.read_text("scripts/setup-windows.ps1")
        unix = self.read_text("scripts/setup-unix.sh")

        for name, setup in (("windows", win), ("unix", unix)):
            self.assertIn("stable-lead.md", setup, name)
            self.assertIn("agents", setup, name)
            self.assertIn("commands", setup, name)
            self.assertIn("team-lead.md", setup, name)
            self.assertIn("ensemble.json", setup, name)
            self.assertNotIn("ensemble.json.template", setup, name)
            self.assertNotIn("mattpocock/skills", setup, name)
            self.assertNotIn("oc-team", setup, name)
            self.assertNotIn("oc-product", setup, name)
            self.assertNotIn("models.ps1.example", setup, name)
            self.assertNotIn("models.sh.example", setup, name)

        self.assertIn("CleanLegacy", win)
        self.assertIn("--clean-legacy", unix)
        self.assertIn("backup_*", win)
        self.assertIn("backup_*", unix)

    def test_gstack_config_is_portable(self) -> None:
        path = ROOT / "gstack/gstack.jsonc"
        self.assertTrue(path.is_file())
        parsed = json.loads(path.read_text(encoding="utf-8"))
        self.assertNotIn("permissions", parsed)


if __name__ == "__main__":
    unittest.main()
