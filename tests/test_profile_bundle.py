import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PortableProfileBundleTest(unittest.TestCase):
    def read_json(self, relative: str) -> dict:
        return json.loads((ROOT / relative).read_text(encoding="utf-8"))

    def test_profile_bundle_matches_team_v2_contract(self) -> None:
        team = self.read_json("profiles/team/opencode.jsonc")
        product = self.read_json("profiles/product/opencode.jsonc")

        self.assertIn("permission", team)
        self.assertNotIn("permissions", team)
        self.assertNotIn("agents", team)
        self.assertEqual(team["default_agent"], "orchestrator")
        self.assertEqual(team["subagent_depth"], 1)
        self.assertEqual(team["plugin"], ["@hueyexe/opencode-ensemble@0.17.0"])
        self.assertEqual(team["small_model"], "{env:OPENCODE_WORKER_MODEL}")
        self.assertTrue((ROOT / "profiles/team/ensemble.json.template").is_file())

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
        self.assertIn("Contract freeze gate", orchestrator)
        self.assertIn("at most two implementation", orchestrator)
        self.assertIn("GPT-5.6 takeover", orchestrator)
        self.assertNotIn("\nmodel:", worker)
        self.assertIn("steps: 15", worker)
        self.assertRegex(worker, re.compile(r"task:\s*deny", re.S))
        self.assertRegex(worker, re.compile(r"webfetch:\s*deny", re.S))
        self.assertIn('"**/tests/**": deny', worker)
        self.assertIn("model: openai/gpt-5.6-sol", reviewer)
        self.assertRegex(reviewer, re.compile(r"edit:\s*deny", re.S))

        skill = team["permission"]["skill"]
        for name in (
            "qa", "qa-only", "review", "ship", "cso", "investigate",
            "plan-ceo-review", "design-review", "benchmark",
        ):
            self.assertEqual(skill.get(name), "allow", name)
        self.assertEqual(skill.get("superpowers-*"), "deny")
        self.assertIn("specialist toolbox", orchestrator)

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
        self.assertIn("model: openai/gpt-5.6-sol", team_lead)
        for denied in ("to-spec", "to-tickets", "implement", "grill-me", "tdd"):
            self.assertIn(f"{denied}: deny", stable)
        self.assertIn("superpowers-*: deny", team_lead)
        for name in ("explorer", "test-writer", "implementer", "reviewer"):
            content = (ROOT / f"agents/{name}.md").read_text(encoding="utf-8")
            self.assertIn("model: deepseek/deepseek-v4-flash", content)

        stable_cmd = (ROOT / "commands/stable.md").read_text(encoding="utf-8")
        team_cmd = (ROOT / "commands/team.md").read_text(encoding="utf-8")
        self.assertIn("agent: stable-lead", stable_cmd)
        self.assertIn("agent: team-lead", team_cmd)

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

    def test_unix_setup_matches_windows_setup(self) -> None:
        setup = (ROOT / "scripts/setup-unix.sh").read_text(encoding="utf-8")
        self.assertIn("ensemble.json.template", setup)
        self.assertIn("OPENCODE_WORKER_MODEL", setup)
        self.assertIn("resolving-merge-conflicts", setup)
        self.assertIn("agents/*.md", setup)
        self.assertIn("commands/*.md", setup)

    def test_portable_global_and_gstack_configs_have_no_dead_models(self) -> None:
        dead = ("kimi", "claude", "gpt-5.3", "gpt-5-nano", "sfkey")
        for relative in ("global/opencode.jsonc", "gstack/gstack.jsonc"):
            path = ROOT / relative
            self.assertTrue(path.is_file(), relative)
            content = path.read_text(encoding="utf-8")
            parsed = json.loads(content)
            self.assertNotIn("permissions", parsed)
            for token in dead:
                self.assertNotIn(token, content, f"{relative} references dead {token}")

        global_config = self.read_json("global/opencode.jsonc")
        self.assertEqual(global_config["model"], "openai/gpt-5.6-sol")
        self.assertEqual(global_config["small_model"], "deepseek/deepseek-v4-flash")
        self.assertIn("@hueyexe/opencode-ensemble@0.17.0", global_config["plugin"])

        gstack = self.read_json("gstack/gstack.jsonc")
        allowed = {"openai/gpt-5.6-sol", "deepseek/deepseek-v4-flash"}
        for name, entry in gstack["categories"].items():
            self.assertIn(entry["model"], allowed, name)
        for name, entry in gstack["agents"].items():
            self.assertIn(entry["model"], allowed, name)

        setup = (ROOT / "scripts/setup-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("global\\opencode.jsonc", setup)
        self.assertIn("gstack\\gstack.jsonc", setup)


if __name__ == "__main__":
    unittest.main()
