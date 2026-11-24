import contextlib
import io
import itertools
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sowgen import Intake, build_scope, render_html, render_markdown
from sowgen.cli import main
from sowgen.intake import ROOM_OPTIONS
from sowgen.render import TemplateError, render_template

from .helpers import EXAMPLES, ROOT, scope_for

ROOMS = ("bathroom", "kitchen", "basement")
EM_DASH = chr(0x2014)


class TemplateEngineTests(unittest.TestCase):
    def test_variables_and_dotted_paths(self):
        self.assertEqual(render_template("Hi {{ a.b }}!", {"a": {"b": "there"}}), "Hi there!")

    def test_for_loop_and_block_lines_leave_no_blank_lines(self):
        source = "start\n{% for x in items %}\n- {{ x }}\n{% endfor %}\nend\n"
        self.assertEqual(render_template(source, {"items": ["a", "b"]}), "start\n- a\n- b\nend\n")

    def test_if_else_and_not(self):
        source = "{% if on %}yes{% else %}no{% endif %}/{% if not on %}off{% endif %}"
        self.assertEqual(render_template(source, {"on": ["x"]}), "yes/")
        self.assertEqual(render_template(source, {"on": []}), "no/off")

    def test_loop_variable_shadows_and_nests(self):
        source = "{% for g in groups %}{% for x in g.items %}{{ g.name }}{{ x }} {% endfor %}{% endfor %}"
        context = {"groups": [{"name": "a", "items": ["1", "2"]}, {"name": "b", "items": ["3"]}]}
        self.assertEqual(render_template(source, context), "a1 a2 b3 ")

    def test_escape_only_when_asked(self):
        self.assertEqual(render_template("{{ v }}", {"v": "<b>&"}), "<b>&")
        self.assertEqual(render_template("{{ v }}", {"v": "<b>&"}, escape=True), "&lt;b&gt;&amp;")

    def test_errors(self):
        for bad in ("{{ missing }}", "{% for x in items %}", "{% endif %}", "{% wat %}", "{{ a.nope }}",
                    "{% for x in a %}{% endif %}"):
            with self.assertRaises(TemplateError, msg=bad):
                render_template(bad, {"items": [], "a": {}})


class OutputTests(unittest.TestCase):
    def test_markdown_structure_for_each_room(self):
        for room in ROOMS:
            scope = build_scope(Intake.from_file(EXAMPLES / f"{room}.json"))
            text = render_markdown(scope, company="Test Co")
            self.assertTrue(text.startswith(f"# Scope of Work: {room.capitalize()} Remodel\n"))
            for number, section in enumerate(scope.sections, start=1):
                self.assertIn(f"### {number}. {section.trade}\n", text)
                for line in section.inclusions + section.exclusions + section.assumptions:
                    self.assertIn(f"- {line}\n", text)
            for heading in ("## Project summary", "## Scope by trade", "## General exclusions",
                            "## General assumptions", "## Allowance summary"):
                self.assertIn(heading, text)
            self.assertIn(f"**${scope.allowance_total:,}**", text)
            self.assertNotIn("\n\n\n", text)
            self.assertNotIn("{{", text)
            self.assertNotIn("{%", text)

    def test_html_structure_for_each_room(self):
        for room in ROOMS:
            scope = build_scope(Intake.from_file(EXAMPLES / f"{room}.json"))
            text = render_html(scope, company="Test Co")
            self.assertTrue(text.startswith("<!DOCTYPE html>"))
            self.assertTrue(text.rstrip().endswith("</html>"))
            self.assertEqual(text.count('<section class="trade">'), len(scope.sections))
            self.assertEqual(text.count("<ul>"), text.count("</ul>"))
            self.assertEqual(text.count("<table>"), text.count("</table>"))
            self.assertNotIn("{{", text)
            self.assertNotIn("{%", text)

    def test_html_escapes_intake_text(self):
        scope = scope_for("bathroom", client_label="<script>alert(1)</script> & Co")
        text = render_html(scope)
        self.assertNotIn("<script>", text)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; Co", text)

    def test_review_section_only_when_flags_exist(self):
        self.assertNotIn("Review before sending", render_markdown(scope_for("bathroom")))
        self.assertIn("Review before sending", render_markdown(scope_for("bathroom", year_built=1950)))

    def test_trade_with_only_exclusions_says_so(self):
        text = render_markdown(scope_for("basement"))
        self.assertIn("### 4. Plumbing\n\nNo work is included under this trade.\n", text)

    def test_same_intake_gives_identical_output(self):
        for room in ROOMS:
            path = EXAMPLES / f"{room}.json"
            first = render_markdown(build_scope(Intake.from_file(path)))
            second = render_markdown(build_scope(Intake.from_file(path)))
            self.assertEqual(first, second)

    def test_company_name_comes_from_environment(self):
        with mock.patch.dict(os.environ, {"SOWGEN_COMPANY_NAME": "Placeholder Builders"}):
            self.assertIn("Placeholder Builders", render_markdown(scope_for("kitchen")))
        with mock.patch.dict(os.environ, {"SOWGEN_COMPANY_NAME": ""}):
            self.assertIn("Example Remodeling Co", render_markdown(scope_for("kitchen")))

    def test_every_option_combination_renders(self):
        """Sweep each room's full option space: nothing crashes and nothing is left unrendered."""
        areas = {"bathroom": 50, "kitchen": 150, "basement": 600}
        count = 0
        for room, spec in ROOM_OPTIONS.items():
            names = list(spec)
            choices = []
            for kind, _default in spec.values():
                if kind is bool:
                    choices.append((False, True))
                elif isinstance(kind, range):
                    choices.append((kind.start, kind.stop - 1))
                else:
                    choices.append(kind)
            for combo in itertools.product(*choices):
                data = {"project_id": "SWEEP", "room_type": room, "area_sqft": areas[room],
                        "options": dict(zip(names, combo))}
                try:
                    intake = Intake.from_dict(data)
                except ValueError:
                    continue  # combinations the intake rejects on purpose
                scope = build_scope(intake)
                text = render_markdown(scope) + render_html(scope)
                self.assertNotIn(EM_DASH, text)
                self.assertGreaterEqual(len(scope.sections), 8)
                count += 1
        self.assertGreater(count, 500)


class CliTests(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_markdown_to_stdout(self):
        code, out, _ = self.run_cli(str(EXAMPLES / "kitchen.json"))
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("# Scope of Work: Kitchen Remodel"))

    def test_json_format(self):
        code, out, _ = self.run_cli(str(EXAMPLES / "basement.json"), "--format", "json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["project_id"], "DEMO-BSMT-003")

    def test_both_formats_written_to_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = self.run_cli(str(EXAMPLES / "bathroom.json"), "--format", "both", "--out", tmp)
            self.assertEqual(code, 0)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                             ["DEMO-BATH-001.html", "DEMO-BATH-001.md"])

    def test_invalid_intake_exits_2_and_lists_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"project_id": "X", "room_type": "attic", "area_sqft": 10}),
                            encoding="utf-8")
            code, out, err = self.run_cli(str(path))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("room_type must be one of", err)

    def test_missing_file_exits_2(self):
        code, _, err = self.run_cli("no-such-file.json")
        self.assertEqual(code, 2)
        self.assertIn("not found", err)

    def test_describe(self):
        code, out, _ = self.run_cli("--describe")
        self.assertEqual(code, 0)
        self.assertIn("Options for basement", out)


class RepoHygieneTests(unittest.TestCase):
    def test_no_em_dashes_in_repo_text_files(self):
        suffixes = {".py", ".md", ".tmpl", ".json", ".yml", ".txt", ".html", ".example", ".gitignore"}
        skip = {".venv", "venv", "__pycache__", ".git", "node_modules"}
        for path in ROOT.rglob("*"):
            if path.is_file() and not skip & set(path.parts) and (path.suffix in suffixes or path.name.startswith(".")):
                self.assertNotIn(EM_DASH, path.read_text(encoding="utf-8"), str(path))

    def test_readme_excerpts_are_real_demo_output(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        captured = (ROOT / "demo" / "output.txt").read_text(encoding="utf-8")
        blocks = re.findall(r"```(?:text|markdown)\n(.*?)```", readme, re.S)
        self.assertEqual(len(blocks), 3)
        for block in blocks:
            self.assertIn(block, captured)

    def test_committed_samples_match_current_rules(self):
        samples = ROOT / "demo" / "sample_output"
        for room in ROOMS:
            scope = build_scope(Intake.from_file(EXAMPLES / f"{room}.json"))
            pid = scope.intake.project_id
            self.assertEqual((samples / f"{pid}.md").read_text(encoding="utf-8"),
                             render_markdown(scope, company="Example Remodeling Co"))
            self.assertEqual((samples / f"{pid}.html").read_text(encoding="utf-8"),
                             render_html(scope, company="Example Remodeling Co"))


if __name__ == "__main__":
    unittest.main()
