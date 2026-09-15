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


if __name__ == "__main__":
    unittest.main()
