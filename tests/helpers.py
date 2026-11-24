from pathlib import Path

from sowgen import Intake, build_scope

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"

AREAS = {"bathroom": 50, "kitchen": 150, "basement": 600}


def scope_for(room, area=None, options=None, **fields):
    """Build a scope from a minimal intake; anything not given uses the defaults."""
    data = {"project_id": "TEST-001", "room_type": room, "area_sqft": area or AREAS[room]}
    data.update(fields)
    if options:
        data["options"] = options
    return build_scope(Intake.from_dict(data))


def allowance(scope, trade, item):
    for a in scope.section(trade).allowances:
        if a.item == item:
            return a.amount
    raise AssertionError(f"no allowance {item!r} under {trade!r}")


def all_lines(scope):
    lines = list(scope.general_exclusions) + list(scope.general_assumptions)
    for s in scope.sections:
        lines += s.inclusions + s.exclusions + s.assumptions
    return lines
