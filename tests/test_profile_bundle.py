import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# The approved Team skill allowlist: 14 Superpowers + 9 gstack, nothing else.
TEAM_SKILLS = [
    "brainstorming",
    "dispatching-parallel-agents",
    "executing-plans",
    "finishing-a-development-branch",
    "receiving-code-review",
    "requesting-code-review",
    "subagent-driven-development",
    "systematic-debugging",
    "test-driven-development",
    "using-git-worktrees",
    "using-superpowers",
    "verification-before-completion",
    "writing-plans",
    "writing-skills",
    "qa",
    "qa-only",
    "review",
    "ship",
    "cso",
    "investigate",
    "plan-ceo-review",
    "design-review",
    "benchmark",
]

TEAM_SECRET_PATHS = [
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

LEGACY_TEAM_WORKFLOW = re.compile(
    r"(?i)matt\s+pocock|grill|to-spec|to-tickets|\btickets?\b|\bDAG\b|wayfinder|TEAM V2"
)


class PortableProfileBundleTest(unittest.TestCase):
    def read_json(self, relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_profile_bundle_matches_team_mvp_sprint_contract(self) -> None:
        team = self.read_json("profiles/team/opencode.jsonc")
        product = self.read_json("profiles/product/opencode.jsonc")

        self.assertIn("permission", team)
        self.assertNotIn("permissions", team)
        self.assertNotIn("agents", team)
        self.assertEqual(team["default_agent"], "orchestrator")
        self.assertEqual(team["subagent_depth"], 1)
        self.assertEqual(team["model"], "{env:OPENCODE_PRIMARY_MODEL}")
        self.assertEqual(team["small_model"], "{env:OPENCODE_WORKER_MODEL}")
        self.assertEqual(team["instructions"], ["./TEAM_MVP_SPRINT.md"])
        self.assertEqual(
            team["plugin"],
            [
                "superpowers@git+https://github.com/obra/superpowers.git",
                "@hueyexe/opencode-ensemble@0.18.0",
            ],
        )
        self.assertTrue((ROOT / "profiles/team/ensemble.json.template").is_file())

        # Agent models resolve from env through the config `agent` block; the
        # Markdown agents intentionally declare no model line.
        agent_config = team["agent"]
        self.assertEqual(
            agent_config["orchestrator"]["model"], "{env:OPENCODE_PRIMARY_MODEL}"
        )
        for name in ("ds-worker", "researcher", "reviewer"):
            self.assertEqual(
                agent_config[name]["model"], "{env:OPENCODE_WORKER_MODEL}", name
            )

        skill = team["permission"]["skill"]
        self.assertEqual(skill["*"], "deny")
        allowed = sorted(name for name, value in skill.items() if value == "allow")
        self.assertEqual(len(allowed), 23)
        self.assertEqual(allowed, sorted(TEAM_SKILLS))
        for legacy in (
            "setup-matt-pocock-skills",
            "grill-with-docs",
            "grill-me",
            "wayfinder",
            "to-spec",
            "to-tickets",
            "implement",
            "tdd",
            "codebase-design",
            "domain-modeling",
            "diagnosing-bugs",
            "code-review",
            "research",
            "handoff",
        ):
            self.assertNotIn(legacy, skill)

        for pattern in TEAM_SECRET_PATHS:
            self.assertEqual(team["permission"]["read"][pattern], "deny", pattern)
            self.assertEqual(team["permission"]["edit"][pattern], "deny", pattern)
        for command in (
            "git reset --hard*",
            "git clean*",
            "git branch -D*",
            "git push --force*",
            "git push -f*",
        ):
            self.assertEqual(team["permission"]["bash"][command], "deny", command)
        for command in ("git rebase*", "git push*"):
            self.assertEqual(team["permission"]["bash"][command], "ask", command)

        self.assertIn("permission", product)
        self.assertNotIn("permissions", product)
        self.assertNotIn("agents", product)
        self.assertEqual(product["default_agent"], "product")
        self.assertEqual(product["subagent_depth"], 1)
        self.assertIn(
            "superpowers@git+https://github.com/obra/superpowers.git",
            product["plugin"],
        )

        required = [
            "profiles/team/agents/orchestrator.md",
            "profiles/team/agents/ds-worker.md",
            "profiles/team/agents/reviewer.md",
            "profiles/team/agents/researcher.md",
            "profiles/product/agents/product.md",
        ]
        for relative in required:
            self.assertTrue((ROOT / relative).is_file(), relative)

        orchestrator = (ROOT / required[0]).read_text(encoding="utf-8")
        worker = (ROOT / required[1]).read_text(encoding="utf-8")
        reviewer = (ROOT / required[2]).read_text(encoding="utf-8")
        researcher = (ROOT / required[3]).read_text(encoding="utf-8")

        self.assertIn("Parallelize discovery freely", orchestrator)
        self.assertIn("at most two writable workers", orchestrator)
        self.assertNotRegex(orchestrator, re.compile(r"(?m)^model:"))

        for name, content in (
            ("orchestrator", orchestrator),
            ("ds-worker", worker),
            ("reviewer", reviewer),
            ("researcher", researcher),
        ):
            self.assertNotRegex(content, re.compile(r"(?m)^model:"), name)
            self.assertNotRegex(content, LEGACY_TEAM_WORKFLOW, name)

        self.assertRegex(worker, re.compile(r"(?m)^  task: deny\s*$"))
        self.assertRegex(worker, re.compile(r"(?m)^  webfetch: deny\s*$"))
        self.assertRegex(worker, re.compile(r"(?m)^## Completion handback\s*$"))
        for bullet in (
            "- Changed files",
            "- Commands run and exact result",
            "- Core acceptance result",
            "- Remaining limitation or blocker",
        ):
            self.assertRegex(worker, re.compile(r"(?m)^" + re.escape(bullet) + r"\s*$"))
        self.assertNotRegex(
            worker, re.compile(r"\*\*/tests/\*\*|\*\*/docs/\*\*|\*\*/migrations/\*\*")
        )
        self.assertRegex(reviewer, re.compile(r"(?m)^  edit: deny\s*$"))
        self.assertRegex(reviewer, re.compile(r"(?m)^  task: deny\s*$"))
        self.assertIn("read-only scout", researcher)
        self.assertRegex(researcher, re.compile(r"(?m)^  edit: deny\s*$"))
        self.assertRegex(researcher, re.compile(r"(?m)^  task: deny\s*$"))

        policy = (ROOT / "profiles/team/TEAM_MVP_SPRINT.md").read_text(encoding="utf-8")
        for section in (
            "Core Principle",
            "Wave 0: Recon",
            "Wave 1: Spine",
            "Wave 2: Independent Expansion",
            "Wave 3: Integration",
            "Wave 4: QA",
            "Wave 5: Demo Hardening",
            "Parallelization Rubric",
            "Artifact-Based Recovery",
            "Time-Pressure Modes",
        ):
            self.assertIn(f"## {section}", policy)
        self.assertNotRegex(policy, LEGACY_TEAM_WORKFLOW)

        template = self.read_json("profiles/team/ensemble.json.template")
        self.assertFalse(template["mergeOnCleanup"])
        self.assertGreater(template["stallThresholdMs"], 0)
        self.assertGreater(template["timeoutMs"], 0)
        self.assertEqual(template["defaultModel"], "__OPENCODE_WORKER_MODEL__")
        for role in ("ds-worker", "researcher", "reviewer"):
            self.assertEqual(
                template["modelsByAgent"][role], "__OPENCODE_WORKER_MODEL__", role
            )
        self.assertNotIn("maxAgents", template)

    def test_shared_agents_commands_and_skill_isolation(self) -> None:
        for relative in (
            "agents/stable-lead.md",
            "agents/team-lead.md",
            "agents/explorer.md",
            "agents/test-writer.md",
            "agents/implementer.md",
            "agents/reviewer.md",
            "commands/stable.md",
            "commands/team.md",
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

        stable = (ROOT / "agents/stable-lead.md").read_text(encoding="utf-8")
        team_lead = (ROOT / "agents/team-lead.md").read_text(encoding="utf-8")
        self.assertIn("model: openai/gpt-5.6-sol", stable)
        self.assertNotRegex(team_lead, re.compile(r"(?m)^model:"))
        for denied in ("to-spec", "to-tickets", "implement", "grill-me", "tdd"):
            self.assertIn(f"{denied}: deny", stable)
        for agent in ("team-scout", "team-builder", "team-reviewer"):
            self.assertIn(f"{agent}: allow", team_lead)
        for name in ("explorer", "test-writer", "implementer", "reviewer"):
            content = (ROOT / f"agents/{name}.md").read_text(encoding="utf-8")
            self.assertIn("model: deepseek/deepseek-v4-flash", content)

        stable_cmd = (ROOT / "commands/stable.md").read_text(encoding="utf-8")
        team_cmd = (ROOT / "commands/team.md").read_text(encoding="utf-8")
        self.assertIn("agent: stable-lead", stable_cmd)
        self.assertIn("agent: team-lead", team_cmd)
        for lead in ("agents/stable-lead.md", "agents/team-lead.md"):
            content = (ROOT / lead).read_text(encoding="utf-8")
            self.assertIn("Compound learning", content)
            self.assertIn("40 lines", content)
            self.assertIn("required model is unavailable", content)
        self.assertIn("quota", stable)

    def test_readme_explains_the_isolated_workflows_and_team_architecture(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## 工作流差異", readme)
        self.assertIn("## TEAM 執行架構", readme)
        self.assertIn("OpenCode Ensemble", readme)
        self.assertIn("```mermaid", readme)
        self.assertIn("## PRODUCT 執行架構", readme)
        self.assertIn("PRODUCT：", readme)
        self.assertIn("TEAM：", readme)

    def test_windows_setup_installs_the_portable_ensemble_configuration(self) -> None:
        setup = (ROOT / "scripts/setup-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("ensemble.json.template", setup)
        self.assertIn("OPENCODE_WORKER_MODEL", setup)
        self.assertIn("'implement'", setup)
        self.assertIn("'resolving-merge-conflicts'", setup)
        self.assertIn("agents\\*.md", setup)
        self.assertIn("commands\\*.md", setup)
        self.assertIn("backup_*", setup)

    def test_design_brief_is_archived(self) -> None:
        brief = ROOT / "prompts/original-dual-workflow-brief.md"
        self.assertTrue(brief.is_file())
        content = brief.read_text(encoding="utf-8")
        self.assertIn("STABLE MODE", content)
        self.assertIn("TEAM MODE", content)

    def test_unix_setup_matches_windows_setup(self) -> None:
        setup = (ROOT / "scripts/setup-unix.sh").read_text(encoding="utf-8")
        self.assertIn("ensemble.json.template", setup)
        self.assertIn("OPENCODE_WORKER_MODEL", setup)
        self.assertIn("resolving-merge-conflicts", setup)
        self.assertIn("agents/*.md", setup)
        self.assertIn("commands/*.md", setup)

    def test_portable_global_and_gstack_configs(self) -> None:
        for relative in ("global/opencode.jsonc", "gstack/gstack.jsonc"):
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            parsed = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("permissions", parsed)

        global_config = self.read_json("global/opencode.jsonc")
        self.assertEqual(global_config["model"], "openai/gpt-5.6-sol")
        self.assertEqual(global_config["small_model"], "deepseek/deepseek-v4-flash")
        self.assertIn("@hueyexe/opencode-ensemble@0.18.0", global_config["plugin"])

        setup = (ROOT / "scripts/setup-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("global\\opencode.jsonc", setup)
        self.assertIn("gstack\\gstack.jsonc", setup)


if __name__ == "__main__":
    unittest.main()
