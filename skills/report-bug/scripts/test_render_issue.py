"""Unit and CLI tests for the structured bug-description renderer."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "render_issue.py"
TEMPLATE = SCRIPT.parents[1] / "templates" / "default.md"
_SPEC = importlib.util.spec_from_file_location("render_issue", SCRIPT)
assert _SPEC and _SPEC.loader
render_issue = importlib.util.module_from_spec(_SPEC)
sys.modules["render_issue"] = render_issue
_SPEC.loader.exec_module(render_issue)


class RenderIssueTests(unittest.TestCase):
    def raw_model(self) -> dict:
        """Return input containing characters that commonly break serialization."""
        return {
            "description": 'Save shows *failure* for "José" at C:\\tmp <node>.',
            "reproducibility": "Always (3/3)",
            "steps": ["Open [Devices]", "Run `save` with café ☕"],
            "actual_results": "HTTP 500 instead of success.\nSecond line.",
            "diagnostics": [
                {
                    "language": "json",
                    "text": '{"path":"C:\\\\tmp","tick":"```"}',
                }
            ],
            "expected_results": "The device is saved.",
            "links": [
                {
                    "label": "Issue [one]",
                    "url": "https://example.test/a_(b)",
                }
            ],
        }

    def model(self) -> dict:
        """Return the normalized model used by rendering tests."""
        return render_issue.validate_model(self.raw_model())

    def blocks(self) -> list[tuple[str, object]]:
        """Return parsed blocks from the shipped default template."""
        return render_issue.parse_template(TEMPLATE.read_text(encoding="utf-8"))

    def test_markdown_escapes_data_and_uses_safe_fence(self):
        output = render_issue.render_markdown(self.blocks(), self.model())
        self.assertIn(r"\*failure\*", output)
        self.assertIn("José", output)
        self.assertIn(r"C:\\tmp \<node\>", output)
        self.assertIn("````json", output)
        self.assertIn("https://example.test/a_%28b%29", output)

    def test_adf_preserves_characters_and_structure(self):
        adf = render_issue.render_adf(self.blocks(), self.model())
        encoded = json.dumps(adf, ensure_ascii=False)
        self.assertIn("José", encoded)
        self.assertIn("<node>", encoded)
        self.assertTrue(any(node["type"] == "orderedList" for node in adf["content"]))
        self.assertTrue(any(node["type"] == "codeBlock" for node in adf["content"]))
        self.assertTrue(
            any(
                child.get("type") == "hardBreak"
                for node in adf["content"]
                for child in node.get("content", [])
            )
        )
        self.assertEqual(json.loads(json.dumps(adf, ensure_ascii=False)), adf)

    def test_rejects_bad_templates(self):
        for template in (
            "{{unknown}}",
            "Description: {{description}}",
            "{{description}}",
        ):
            with (
                self.subTest(template=template),
                self.assertRaises(render_issue.RenderError),
            ):
                render_issue.parse_template(template)

    def test_rejects_bad_model_and_link(self):
        with self.assertRaises(render_issue.RenderError):
            render_issue.validate_model({})
        raw = dict(self.model())
        raw["links"] = [{"label": "unsafe", "url": "javascript:alert(1)"}]
        with self.assertRaises(render_issue.RenderError):
            render_issue.validate_model(raw)
        for unsafe_url in (
            "https://user:secret@example.test/path",
            "https://example.test/has space",
            "https://example.test/line\nbreak",
        ):
            raw = self.raw_model()
            raw["links"] = [{"label": "unsafe", "url": unsafe_url}]
            with (
                self.subTest(url=unsafe_url),
                self.assertRaises(render_issue.RenderError),
            ):
                render_issue.validate_model(raw)
        raw = dict(self.model())
        raw["unknown"] = "value"
        with self.assertRaises(render_issue.RenderError):
            render_issue.validate_model(raw)

    def test_rejects_template_that_drops_populated_optional_data(self):
        blocks = [block for block in self.blocks() if block != ("placeholder", "links")]
        with self.assertRaises(render_issue.RenderError):
            render_issue.render_adf(blocks, self.model())

    def test_optional_values_may_be_absent(self):
        raw = self.raw_model()
        raw.pop("diagnostics")
        raw.pop("links")
        adf = render_issue.render_adf(
            self.blocks(),
            render_issue.validate_model(raw),
        )
        self.assertFalse(any(node["type"] == "codeBlock" for node in adf["content"]))

    def test_optional_null_scalars_are_normalized_and_render_in_both_formats(self):
        raw = self.raw_model()
        raw.update({"environment": None, "severity": None})
        model = render_issue.validate_model(raw)
        self.assertNotIn("environment", model)
        self.assertNotIn("severity", model)

        source = (
            TEMPLATE.read_text(encoding="utf-8") + "\n{{environment}}\n\n{{severity}}\n"
        )
        blocks = render_issue.parse_template(source)
        markdown = render_issue.render_markdown(blocks, model)
        adf = render_issue.render_adf(blocks, model)
        self.assertTrue(markdown.startswith("## Description of the problem\n"))
        self.assertEqual(adf["type"], "doc")

    def test_literal_template_markdown_is_escaped_in_preview(self):
        source = TEMPLATE.read_text(encoding="utf-8").replace(
            "## Description of the problem",
            "## Description *literal*",
        )
        output = render_issue.render_markdown(
            render_issue.parse_template(source),
            self.model(),
        )
        self.assertIn(r"## Description \*literal\*", output)

    def test_line_leading_markdown_blocks_are_escaped_in_preview(self):
        raw = self.raw_model()
        raw["actual_results"] = (
            "- item\n+ item\n1. item\n2) item\n---\n> quote\n# heading\n"
            "~~strike~~\nheading\n==="
        )
        output = render_issue.render_markdown(
            self.blocks(),
            render_issue.validate_model(raw),
        )
        for expected in (
            r"\- item",
            r"\+ item",
            r"1\. item",
            r"2\) item",
            r"\---",
            r"\> quote",
            r"\# heading",
            r"\~\~strike\~\~",
            r"\=\=\=",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, output)

    def test_literal_template_block_markers_are_escaped_in_preview(self):
        source = TEMPLATE.read_text(encoding="utf-8").replace(
            "## Description of the problem\n",
            "## Description of the problem\n\n---\n\n",
        )
        output = render_issue.render_markdown(
            render_issue.parse_template(source),
            self.model(),
        )
        self.assertIn(r"\---", output)

    def test_provenance_uses_skill_and_authoritative_assistant_identity(self):
        skill = render_issue.load_skill_metadata(SCRIPT.parents[1] / "SKILL.md")
        provenance = render_issue.build_provenance(self.model(), skill)
        self.assertEqual(
            provenance,
            "Reported with AI assistance using report-bug v0.1.0. Review for accuracy.",
        )

        raw = self.raw_model()
        raw["assistant"] = {"agent": "Codex", "model": "gpt-5.6-sol"}
        identified = render_issue.build_provenance(
            render_issue.validate_model(raw),
            skill,
        )
        self.assertIn("(Codex using gpt-5.6-sol)", identified)

    def test_adf_provenance_is_emphasized_after_rule(self):
        provenance = "Reported with AI assistance using report-bug v0.1.0."
        adf = render_issue.render_adf(self.blocks(), self.model(), provenance)
        self.assertEqual(adf["content"][-2], {"type": "rule"})
        self.assertEqual(
            adf["content"][-1]["content"][0]["marks"],
            [{"type": "em"}],
        )

    def test_rejects_unbounded_or_unknown_assistant_identity(self):
        for assistant in (
            {"agent": "Codex", "provider": "unknown"},
            {"agent": "line one\nline two"},
            {"model": "x" * 201},
        ):
            raw = self.raw_model()
            raw["assistant"] = assistant
            with (
                self.subTest(assistant=assistant),
                self.assertRaises(render_issue.RenderError),
            ):
                render_issue.validate_model(raw)


class RenderIssueCliTests(unittest.TestCase):
    def run_cli(
        self,
        model: object,
        *,
        output_format: str = "adf",
        template: Path = TEMPLATE,
        no_provenance: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Run the public CLI against a temporary JSON input file."""
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "issue.json"
            input_path.write_text(json.dumps(model), encoding="utf-8")
            command = [
                sys.executable,
                str(SCRIPT),
                "--input",
                str(input_path),
                "--template",
                str(template),
                "--format",
                output_format,
            ]
            if no_provenance:
                command.append("--no-provenance")
            return subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )

    def test_cli_emits_parseable_adf(self):
        result = self.run_cli(RenderIssueTests().raw_model())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        adf = json.loads(result.stdout)
        self.assertEqual(adf["type"], "doc")
        self.assertIn("report-bug v0.1.0", adf["content"][-1]["content"][0]["text"])

    def test_cli_emits_markdown_preview(self):
        result = self.run_cli(
            RenderIssueTests().raw_model(),
            output_format="markdown",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("## Description of the problem\n"))
        self.assertIn("report-bug v0.1.0", result.stdout)

    def test_cli_can_disable_provenance_by_policy(self):
        result = self.run_cli(
            RenderIssueTests().raw_model(),
            output_format="markdown",
            no_provenance=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Reported with AI assistance", result.stdout)

    def test_cli_reports_malformed_input_without_traceback(self):
        result = self.run_cli({"description": "incomplete"})
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("render_issue:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_accepts_explicit_null_optional_scalar_without_traceback(self):
        model = RenderIssueTests().raw_model()
        model["environment"] = None
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "custom.md"
            template.write_text(
                TEMPLATE.read_text(encoding="utf-8") + "\n{{environment}}\n",
                encoding="utf-8",
            )
            result = self.run_cli(model, output_format="markdown", template=template)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
