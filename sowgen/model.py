"""Plain data structures for a generated scope of work."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .intake import Intake


def money(amount: int) -> str:
    return f"${amount:,}"


@dataclass
class Allowance:
    item: str
    basis: str
    amount: int


@dataclass
class TradeSection:
    trade: str
    inclusions: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    allowances: list[Allowance] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.inclusions or self.exclusions or self.assumptions or self.allowances)


@dataclass
class Scope:
    intake: Intake
    title: str
    sections: list[TradeSection]
    general_exclusions: list[str]
    general_assumptions: list[str]
    review_flags: list[str]

    @property
    def allowance_total(self) -> int:
        return sum(a.amount for s in self.sections for a in s.allowances)

    def section(self, trade: str) -> TradeSection:
        for s in self.sections:
            if s.trade == trade:
                return s
        raise KeyError(trade)

    def trades(self) -> list[str]:
        return [s.trade for s in self.sections]

    def to_context(self, company: str = "Example Remodeling Co") -> dict[str, Any]:
        """Flatten into dicts, lists and strings, which is all the templates understand."""
        i = self.intake
        summary = [
            ("Room type", i.room_type.capitalize()),
            ("Finished area", f"{i.area_sqft:g} sq ft"),
            ("Finish tier", i.finish_tier.capitalize()),
            ("Year built", str(i.year_built)),
            ("Occupied during work", _show(i.occupied)),
            ("Permits by", i.permit_by.capitalize()),
            ("Demolition by", "Owner" if i.demo_by_owner else "Contractor"),
        ]
        summary += [(name.replace("_", " ").capitalize(), _show(value)) for name, value in i.options.items()]

        sections = []
        rollup = []
        for number, s in enumerate(self.sections, start=1):
            rows = [{"item": a.item, "basis": a.basis, "amount": money(a.amount)} for a in s.allowances]
            rollup += [dict(row, trade=s.trade) for row in rows]
            sections.append(
                {
                    "number": str(number),
                    "trade": s.trade,
                    "inclusions": s.inclusions,
                    "exclusions": s.exclusions,
                    "assumptions": s.assumptions,
                    "allowances": rows,
                }
            )
        return {
            "title": self.title,
            "company": company,
            "project_id": i.project_id,
            "client_label": i.client_label,
            "site_label": i.site_label,
            "prepared_date": i.prepared_date,
            "summary": [{"label": label, "value": value} for label, value in summary],
            "sections": sections,
            "general_exclusions": self.general_exclusions,
            "general_assumptions": self.general_assumptions,
            "review_flags": self.review_flags,
            "allowance_rows": rollup,
            "allowance_total": money(self.allowance_total),
        }


def _show(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value).replace("_", " ")
