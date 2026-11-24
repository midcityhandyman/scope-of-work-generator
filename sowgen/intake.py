"""Structured intake: the short form an estimator fills in before a scope is drafted.

The intake is a flat set of common fields plus a small options block that depends
on the room type. Everything is validated up front so the rules never have to
guess at a missing or misspelled answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOM_TYPES = ("bathroom", "kitchen", "basement")
TIERS = ("basic", "standard", "premium")
PERMIT_BY = ("contractor", "owner")

# Plausible finished floor areas per room type, in square feet.
AREA_LIMITS = {"bathroom": (20, 200), "kitchen": (60, 500), "basement": (150, 2500)}

# option name -> (kind, default). kind is bool, a tuple of allowed strings,
# or a range of allowed integers.
ROOM_OPTIONS: dict[str, dict[str, tuple[Any, Any]]] = {
    "bathroom": {
        "layout_change": (bool, False),
        "shower": (("tub_shower", "walk_in_shower", "tub_only", "none"), "tub_shower"),
        "vanity_count": (range(1, 3), 1),
        "floor": (("tile", "lvp"), "tile"),
        "heated_floor": (bool, False),
        "exhaust_fan": (("replace", "new", "keep"), "replace"),
    },
    "kitchen": {
        "layout_change": (bool, False),
        "cabinets": (("replace", "reface", "keep"), "replace"),
        "cabinet_run_ft": (range(8, 61), 20),
        "countertop": (("laminate", "butcher_block", "quartz", "keep"), "quartz"),
        "backsplash": (bool, True),
        "flooring": (("lvp", "tile", "keep"), "lvp"),
        "island": (bool, False),
        "gas_range": (bool, False),
        "appliances_by_owner": (bool, True),
    },
    "basement": {
        "add_bathroom": (bool, False),
        "bedroom": (bool, False),
        "egress_window": (bool, False),
        "ceiling": (("drywall", "drop"), "drywall"),
        "flooring": (("lvp", "carpet"), "lvp"),
        "moisture_history": (bool, False),
        "wet_bar": (bool, False),
    },
}


class IntakeError(ValueError):
    """Raised with every problem found, not just the first one."""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclass(frozen=True)
class Intake:
    project_id: str
    room_type: str
    area_sqft: float
    finish_tier: str = "standard"
    year_built: int = 2000
    occupied: bool = True
    permit_by: str = "contractor"
    demo_by_owner: bool = False
    client_label: str = "Sample Client"
    site_label: str = "Sample Site"
    prepared_date: str = ""
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Intake":
        problems: list[str] = []
        if not isinstance(data, dict):
            raise IntakeError(["intake must be a JSON object"])

        known = set(cls.__dataclass_fields__)
        for key in sorted(set(data) - known):
            problems.append(f"unknown field: {key}")

        project_id = data.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            problems.append("project_id is required")

        room = data.get("room_type")
        if room not in ROOM_TYPES:
            problems.append(f"room_type must be one of {', '.join(ROOM_TYPES)}")

        area = data.get("area_sqft")
        if isinstance(area, bool) or not isinstance(area, (int, float)):
            problems.append("area_sqft must be a number")
        elif room in AREA_LIMITS:
            low, high = AREA_LIMITS[room]
            if not low <= area <= high:
                problems.append(f"area_sqft for a {room} must be between {low} and {high}")

        if data.get("finish_tier", "standard") not in TIERS:
            problems.append(f"finish_tier must be one of {', '.join(TIERS)}")

        if data.get("permit_by", "contractor") not in PERMIT_BY:
            problems.append(f"permit_by must be one of {', '.join(PERMIT_BY)}")

        year = data.get("year_built", 2000)
        if isinstance(year, bool) or not isinstance(year, int) or not 1800 <= year <= 2100:
            problems.append("year_built must be a year between 1800 and 2100")

        for name in ("occupied", "demo_by_owner"):
            if name in data and not isinstance(data[name], bool):
                problems.append(f"{name} must be true or false")

        for name in ("client_label", "site_label", "prepared_date"):
            if name in data and not isinstance(data[name], str):
                problems.append(f"{name} must be text")

        options = _check_options(room, data.get("options", {}), problems)

        if problems:
            raise IntakeError(problems)

        values = {k: v for k, v in data.items() if k in known}
        values["options"] = options
        return cls(**values)

    @classmethod
    def from_file(cls, path: str | Path) -> "Intake":
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise IntakeError([f"{path}: not valid JSON ({exc.msg}, line {exc.lineno})"]) from exc
        return cls.from_dict(data)

    def opt(self, name: str) -> Any:
        return self.options[name]


def _check_options(room: Any, raw: Any, problems: list[str]) -> dict[str, Any]:
    """Validate the room specific options and fill in defaults."""
    if not isinstance(raw, dict):
        problems.append("options must be an object")
        return {}
    spec = ROOM_OPTIONS.get(room) if isinstance(room, str) else None
    if spec is None:
        return {}

    for key in sorted(set(raw) - set(spec)):
        problems.append(f"unknown {room} option: {key}")

    resolved: dict[str, Any] = {}
    for name, (kind, default) in spec.items():
        value = raw.get(name, default)
        if kind is bool:
            if not isinstance(value, bool):
                problems.append(f"options.{name} must be true or false")
        elif isinstance(kind, range):
            if isinstance(value, bool) or not isinstance(value, int) or value not in kind:
                problems.append(f"options.{name} must be a whole number from {kind.start} to {kind.stop - 1}")
        elif not isinstance(value, str) or value not in kind:
            problems.append(f"options.{name} must be one of {', '.join(kind)}")
        resolved[name] = value

    # Cross field checks: combinations that cannot be built as described.
    if room == "bathroom" and resolved.get("heated_floor") is True and resolved.get("floor") == "lvp":
        problems.append("options.heated_floor requires options.floor to be tile")
    if room == "kitchen" and resolved.get("cabinets") == "replace" and resolved.get("countertop") == "keep":
        problems.append("options.countertop cannot be keep when cabinets are replaced")
    return resolved


def describe_schema() -> str:
    """Plain text description of the intake, for the CLI."""
    lines = [
        "Common fields:",
        "  project_id (text, required)",
        f"  room_type ({' | '.join(ROOM_TYPES)}, required)",
        "  area_sqft (number, required)",
        f"  finish_tier ({' | '.join(TIERS)}, default standard)",
        "  year_built (year, default 2000)",
        "  occupied (true | false, default true)",
        f"  permit_by ({' | '.join(PERMIT_BY)}, default contractor)",
        "  demo_by_owner (true | false, default false)",
        "  client_label, site_label, prepared_date (text, optional)",
    ]
    for room, spec in ROOM_OPTIONS.items():
        low, high = AREA_LIMITS[room]
        lines.append(f"\nOptions for {room} (area {low} to {high} sq ft):")
        for name, (kind, default) in spec.items():
            if kind is bool:
                shown, default = "true | false", str(default).lower()
            elif isinstance(kind, range):
                shown = f"{kind.start} to {kind.stop - 1}"
            else:
                shown = " | ".join(kind)
            lines.append(f"  {name} ({shown}, default {default})")
    return "\n".join(lines)
