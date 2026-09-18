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

# The retired multi-agent artifacts that must no longer exist anywhere.
RETIRED_PATHS = [
    "profiles/team/opencode.jsonc",
    "profiles/team/TEAM_MVP_SPRINT.md",
    "profiles/team/ensemble.json.template",
    "profiles/team/agents/orchestrator.md",
    "profiles/team/agents/ds-worker.md",
    "profiles/team/agents/researcher.md",
    "profiles/team/agents/reviewer.md",
    "profiles/product/PRODUCT.md",
    "profiles/product/agents/product.md",
    "agents/team-lead.md",
    "agents/team-scout.md",
    "agents/team-builder.md",
    "agents/team-reviewer.md",
    "commands/team.md",
    "scripts/oc-team.ps1",
    "scripts/oc-team.sh",
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

    def test_the_single_profile_matches_the_contract(self) -> None:
        profile = self.read_json("profiles/product/opencode.jsonc")

        self.assertIn("permission", profile)
        self.assertNotIn("permissions", profile)
        self.assertNotIn("agents", profile)
        self.assertNotIn("instructions", profile)
        self.assertEqual(profile["default_agent"], "stable-lead")
        self.assertEqual(profile["subagent_depth"], 1)
        self.assertEqual(profile["model"], "{env:OPENCODE_PRIMARY_MODEL}")
        self.assertEqual(profile["small_model"], "{env:OPENCODE_WORKER_MODEL}")
        self.assertEqual(
            profile["plugin"],
            ["superpowers@git+https://github.com/obra/superpowers.git"],
        )

        for pattern in SECRET_PATHS:
            self.assertEqual(profile["permission"]["read"][pattern], "deny", pattern)
            self.assertEqual(profile["permission"]["edit"][pattern], "deny", pattern)
        for command in (
            "git reset --hard*",
            "git clean*",
            "git branch -D*",
            "git push --force*",
            "git push -f*",
        ):
            self.assertEqual(profile["permission"]["bash"][command], "deny", command)
        for command in ("git rebase*", "git push*"):
            self.assertEqual(profile["permission"]["bash"][command], "ask", command)

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

    def test_shared_commands_and_agents_are_deployed_by_setup(self) -> None:
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
            "scripts/oc-product.ps1",
            "scripts/oc-product.sh",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)

        stable_cmd = self.read_text("commands/stable.md")
        self.assertIn("agent: stable-lead", stable_cmd)

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
        self.assertIn("oc-product", readme)
        self.assertIn("```mermaid", readme)

        agents_doc = self.read_text("AGENTS.md")
        self.assertIn("One workflow", agents_doc)
        self.assertNotIn("/team", agents_doc)
        self.assertIn("cost per successful slice", agents_doc)

        spec = self.read_text("docs/superpowers/specs/2026-09-18-single-workflow-design.md")
        self.assertIn("Keep exactly **one workflow**", spec)
        self.assertIn("cost per successful slice", spec)

    def test_windows_setup_deploys_and_offers_legacy_cleanup(self) -> None:
        setup = self.read_text("scripts/setup-windows.ps1")
        self.assertIn(".local", setup)
        self.assertIn("models.ps1", setup)
        self.assertIn("agents\\*.md", setup)
        self.assertIn("commands\\*.md", setup)
        self.assertIn("backup_*", setup)
        self.assertIn("CleanLegacy", setup)
        self.assertIn("stable-lead.md", setup)
        self.assertIn("team-lead.md", setup)
        self.assertIn("ensemble.json", setup)
        self.assertNotIn("mattpocock/skills", setup)
        self.assertNotIn("profiles\\team\\skills", setup)
        self.assertNotIn("ensemble.json.template", setup)
        self.assertNotIn("oc-team", setup)

    def test_unix_setup_matches_windows_setup(self) -> None:
        setup = self.read_text("scripts/setup-unix.sh")
        self.assertIn(".local", setup)
        self.assertIn("models.sh", setup)
        self.assertIn("agents/*.md", setup)
        self.assertIn("commands/*.md", setup)
        self.assertIn("--clean-legacy", setup)
        self.assertIn("stable-lead.md", setup)
        self.assertIn("team-lead.md", setup)
        self.assertIn("ensemble.json", setup)
        self.assertNotIn("mattpocock/skills", setup)
        self.assertNotIn("profiles/team/skills", setup)
        self.assertNotIn("ensemble.json.template", setup)
        self.assertNotIn("oc-team", setup)

    def test_portable_global_and_gstack_configs(self) -> None:
        for relative in ("global/opencode.jsonc", "gstack/gstack.jsonc"):
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            parsed = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("permissions", parsed)

        global_config = self.read_json("global/opencode.jsonc")
        self.assertEqual(global_config["model"], "openai/gpt-5.6-sol")
        self.assertEqual(global_config["small_model"], "deepseek/deepseek-v4-flash")
        self.assertNotIn("plugin", global_config)
        self.assertNotIn("opencode-ensemble", json.dumps(global_config))

        setup = self.read_text("scripts/setup-windows.ps1")
        self.assertIn("global\\opencode.jsonc", setup)
        self.assertIn("gstack\\gstack.jsonc", setup)


if __name__ == "__main__":
    unittest.main()
