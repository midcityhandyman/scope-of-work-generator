"""Command line entry point.

    python -m sowgen INTAKE.json [--format md|html|json|both] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .intake import Intake, IntakeError, describe_schema
from .render import company_name, render_html, render_markdown
from .rules import build_scope


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sowgen", description="Generate a remodel scope of work from an intake file."
    )
    parser.add_argument("intake", nargs="?", help="path to an intake JSON file")
    parser.add_argument("--format", choices=("md", "html", "json", "both"), default="md")
    parser.add_argument("--out", help="directory to write files into (required for --format both)")
    parser.add_argument("--describe", action="store_true", help="print the intake fields and exit")
    args = parser.parse_args(argv)

    if args.describe:
        print(describe_schema())
        return 0
    if not args.intake:
        parser.error("an intake file is required")
    if args.format == "both" and not args.out:
        parser.error("--format both needs --out DIR")

    try:
        intake = Intake.from_file(args.intake)
    except FileNotFoundError:
        print(f"error: intake file not found: {args.intake}", file=sys.stderr)
        return 2
    except IntakeError as exc:
        print("error: intake is not valid:", file=sys.stderr)
        for problem in exc.problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2

    scope = build_scope(intake)
    outputs: dict[str, str] = {}
    if args.format in ("md", "both"):
        outputs["md"] = render_markdown(scope)
    if args.format in ("html", "both"):
        outputs["html"] = render_html(scope)
    if args.format == "json":
        outputs["json"] = json.dumps(scope.to_context(company_name()), indent=2) + "\n"

    if args.out:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        for ext, text in outputs.items():
            path = out_dir / f"{intake.project_id}.{ext}"
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {path.as_posix()}")
    else:
        sys.stdout.write(next(iter(outputs.values())))
    return 0
