"""Offline demo: turn the three example intakes into scopes and show what came out.

    python demo/run_demo.py

Writes Markdown and HTML to demo/sample_output/ and prints a summary, one full
Markdown scope, and what a rejected intake looks like. No network, no keys.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sowgen import Intake, IntakeError, build_scope, render_html, render_markdown  # noqa: E402

COMPANY = "Example Remodeling Co"
OUT = ROOT / "demo" / "sample_output"


def rule(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    bathroom_markdown = ""

    rule("1. Three intakes in, three scopes out")
    for room in ("bathroom", "kitchen", "basement"):
        intake = Intake.from_file(ROOT / "examples" / f"{room}.json")
        scope = build_scope(intake)
        markdown, page = render_markdown(scope, COMPANY), render_html(scope, COMPANY)
        (OUT / f"{intake.project_id}.md").write_text(markdown, encoding="utf-8", newline="\n")
        (OUT / f"{intake.project_id}.html").write_text(page, encoding="utf-8", newline="\n")
        if room == "bathroom":
            bathroom_markdown = markdown

        counts = [sum(len(getattr(s, kind)) for s in scope.sections)
                  for kind in ("inclusions", "exclusions", "assumptions", "allowances")]
        print(f"\n{intake.project_id}  {room}, {intake.area_sqft:g} sq ft, {intake.finish_tier} tier")
        print(f"  trades: {len(scope.sections)}  inclusions: {counts[0]}  exclusions: {counts[1]}  "
              f"assumptions: {counts[2]}  allowances: {counts[3]} (total ${scope.allowance_total:,})")
        for flag in scope.review_flags:
            print(f"  review: {flag}")
        print(f"  wrote demo/sample_output/{intake.project_id}.md and .html "
              f"({len(markdown.splitlines())} and {len(page.splitlines())} lines)")

    rule("2. Full Markdown for the bathroom scope")
    print(bathroom_markdown)

    rule("3. A bad intake is rejected with every problem listed")
    bad = {"project_id": "DEMO-BAD-004", "room_type": "bathroom", "area_sqft": 900,
           "finish_tier": "deluxe", "options": {"floor": "lvp", "heated_floor": True, "sauna": True}}
    try:
        Intake.from_dict(bad)
    except IntakeError as exc:
        for problem in exc.problems:
            print(f"  - {problem}")

    rule("4. Same intake twice gives byte identical output")
    again = render_markdown(build_scope(Intake.from_file(ROOT / "examples" / "bathroom.json")), COMPANY)
    print(f"  identical: {again == bathroom_markdown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
