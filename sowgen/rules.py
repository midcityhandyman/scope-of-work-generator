"""Deterministic scope rules.

Each room type has one function that reads the intake and writes inclusions,
exclusions, assumptions and allowances into trade sections. There is no model
call and no randomness: the same intake always yields the same scope.

Allowance figures are illustrative placeholders, not market pricing.
"""

from __future__ import annotations

import math

from .intake import Intake
from .model import Allowance, Scope, TradeSection

GENERAL = "General conditions"
DEMO = "Site protection and demolition"
FRAMING = "Framing and carpentry"
PLUMBING = "Plumbing"
ELECTRICAL = "Electrical"
HVAC = "HVAC and ventilation"
DRYWALL = "Insulation and drywall"
TILE = "Tile and waterproofing"
CABINETS = "Cabinets and countertops"
APPLIANCES = "Appliances"
FLOORING = "Flooring"
EGRESS = "Egress window"
PAINT = "Paint, trim and finish"
CLOSEOUT = "Cleanup and closeout"

# Fixed order: roughly the order the work happens on site. The egress window
# comes right after demolition because the foundation is cut before walls are framed.
TRADES = (GENERAL, DEMO, EGRESS, FRAMING, PLUMBING, ELECTRICAL, HVAC, DRYWALL, TILE,
          CABINETS, APPLIANCES, FLOORING, PAINT, CLOSEOUT)

BASEMENT_BATH_FLOOR_SQFT = 40  # tiled bathroom floor, taken out of the main flooring area

TIER_INDEX = {"basic": 0, "standard": 1, "premium": 2}
WASTE = 1.10  # ten percent overage on sheet and tile goods


class ScopeBuilder:
    def __init__(self, intake: Intake):
        self.intake = intake
        self.sections = {trade: TradeSection(trade) for trade in TRADES}
        self.general_exclusions: list[str] = []
        self.general_assumptions: list[str] = []
        self.review_flags: list[str] = []

    def include(self, trade: str, *lines: str) -> None:
        self.sections[trade].inclusions.extend(lines)

    def exclude(self, trade: str, *lines: str) -> None:
        self.sections[trade].exclusions.extend(lines)

    def assume(self, trade: str, *lines: str) -> None:
        self.sections[trade].assumptions.extend(lines)

    def allow(self, trade: str, item: str, basis: str, amount: float) -> None:
        self.sections[trade].allowances.append(Allowance(item, basis, round_up_10(amount)))

    def flag(self, line: str) -> None:
        self.review_flags.append(line)

    def tier(self, basic: float, standard: float, premium: float) -> float:
        return (basic, standard, premium)[TIER_INDEX[self.intake.finish_tier]]

    def finish(self) -> Scope:
        i = self.intake
        return Scope(
            intake=i,
            title=f"Scope of Work: {i.room_type.capitalize()} Remodel",
            sections=[s for s in self.sections.values() if not s.is_empty()],
            general_exclusions=self.general_exclusions,
            general_assumptions=self.general_assumptions,
            review_flags=self.review_flags,
        )


def round_up_10(amount: float) -> int:
    """Round an allowance up to the next ten dollars."""
    return int(math.ceil(round(amount, 2) / 10.0) * 10)


def sqft(value: float) -> str:
    return f"{value:g} sq ft"


def build_scope(intake: Intake) -> Scope:
    b = ScopeBuilder(intake)
    _common_start(b)
    {"bathroom": _bathroom, "kitchen": _kitchen, "basement": _basement}[intake.room_type](b)
    _common_end(b)
    return b.finish()


# ---------------------------------------------------------------- common rules


def _common_start(b: ScopeBuilder) -> None:
    i = b.intake
    b.include(GENERAL, "Project management, scheduling of trades and one point of contact for the owner.")
    if i.permit_by == "contractor":
        fee = {"bathroom": 250, "kitchen": 400, "basement": 600}[i.room_type]
        b.include(GENERAL, "Permit application and scheduling of required inspections.")
        b.allow(GENERAL, "Permit fees", "flat estimate, billed at actual cost", fee)
    else:
        b.exclude(GENERAL, "Permit applications and fees (by owner).")
        b.assume(GENERAL, "Owner has approved permits in hand before the start date and books inspections.")

    b.include(DEMO, "Floor protection from the entry door to the work area.",
              "Dust barrier with zipper door at the work area.")
    if i.occupied:
        b.include(DEMO, "Broom clean work area and a safe walkway at the end of each work day.")
    if i.demo_by_owner:
        b.exclude(DEMO, "Demolition and debris removal (by owner, complete before the start date).")
        b.assume(DEMO, "Owner demolition leaves framing, subfloor and rough utilities intact and usable.")
    else:
        b.include(DEMO, "Debris haul off and disposal for all demolition listed in this scope.")

    if i.year_built < 1978:
        b.assume(GENERAL, "Home built before 1978: lead safe work practices apply to disturbed painted surfaces.")
        b.exclude(GENERAL, "Testing for and abatement of lead paint or asbestos.")
        b.flag(f"Year built {i.year_built} is before 1978. Confirm lead safe requirements and "
               "ask about suspect flooring, pipe wrap or ceiling texture before pricing.")


def _common_end(b: ScopeBuilder) -> None:
    b.include(CLOSEOUT, "Final construction clean of the work area.",
              "Walkthrough with the owner and one punch list visit.",
              "Product manuals and warranty information handed over at closeout.")
    b.general_exclusions += [
        "Hidden conditions found after surfaces are opened (rot, mold, pests, unsafe wiring or plumbing). "
        "These are priced and approved by written change order before work continues.",
        "Work outside the room named in this scope, including repairs to adjacent finishes "
        "not damaged by this work.",
        "Moving, storing or protecting owner furniture and personal items.",
        "Design, engineering or drawings beyond field layout.",
    ]
    b.general_assumptions += [
        "Work is done on weekdays during normal working hours.",
        "Owner provides water, power, a parking space and clear access to the work area.",
        "All finish selections are final before materials are ordered.",
        "Allowances cover material cost only unless stated. Selections over or under an allowance "
        "are settled by change order.",
    ]


# -------------------------------------------------------------------- bathroom


def _bathroom(b: ScopeBuilder) -> None:
    i = b.intake
    shower, vanities = i.opt("shower"), i.opt("vanity_count")
    has_wet_wall = shower in ("tub_shower", "walk_in_shower")

    if not i.demo_by_owner:
        b.include(DEMO, "Remove toilet, vanity, existing tub or shower, flooring and wet wall finishes.")

    b.include(FRAMING, "Blocking for vanity, accessories and future grab bars.")
    if shower == "walk_in_shower":
        b.include(FRAMING, "Frame shower curb and one recessed niche.")
    if i.opt("layout_change"):
        b.include(FRAMING, "Reframe partition walls for the new layout, up to 12 linear feet.")
        b.include(PLUMBING, "Relocate supply and drain lines to new fixture locations inside the room.")
        b.assume(PLUMBING, "Floor framing allows new drain runs without structural changes.")
        b.flag("Layout change: confirm joist direction and drain slope before committing fixture locations.")
    else:
        b.exclude(FRAMING, "Moving walls, doors or windows.")
        b.include(PLUMBING, "Fixtures set in their existing locations.")
        b.exclude(PLUMBING, "Relocating drains or supply lines.")

    b.include(PLUMBING, "New shutoff valves at each fixture.", "Install toilet.",
              f"Install {vanities} vanity faucet(s) and drain(s).")
    if shower != "none":
        b.include(PLUMBING, "New pressure balanced valve and trim at the tub or shower.")
    if shower in ("tub_shower", "tub_only"):
        b.include(PLUMBING, "Install new tub with drain and overflow.")
    if shower == "walk_in_shower":
        b.include(PLUMBING, "Install shower drain set to the new pan.")
    valve = "" if shower == "none" else ", valve trim"
    b.allow(PLUMBING, "Plumbing fixtures and trim", f"toilet{valve} and {vanities} faucet(s)",
            b.tier(500, 950, 1900) + vanities * b.tier(90, 180, 350))
    if shower in ("tub_shower", "tub_only"):
        b.allow(PLUMBING, "Bathtub", "one standard alcove tub", b.tier(350, 650, 1500))
    b.assume(PLUMBING, "Existing supply and drain lines beyond the room are serviceable.")
    b.exclude(PLUMBING, "Work on the main stack, water heater or water service.")

    b.include(ELECTRICAL, f"{vanities} GFCI protected receptacle(s) at the vanity.",
              f"Install {vanities} vanity light fixture(s) on existing switching.")
    b.allow(ELECTRICAL, "Light fixtures", f"{vanities} vanity light(s)", vanities * b.tier(60, 120, 250))
    b.exclude(ELECTRICAL, "Panel upgrades or service changes.")
    if i.opt("heated_floor"):
        b.include(ELECTRICAL, "Electric floor warming mat under tile with thermostat on a dedicated circuit.")
        b.allow(ELECTRICAL, "Floor warming mat and thermostat", f"{sqft(i.area_sqft)} of floor",
                180 + i.area_sqft * b.tier(9, 11, 14))
        b.assume(ELECTRICAL, "Existing panel has space and capacity for one new circuit.")

    fan = i.opt("exhaust_fan")
    if fan == "replace":
        b.include(HVAC, "Replace exhaust fan using the existing duct and switch.")
        b.assume(HVAC, "Existing fan duct terminates outdoors and is in usable condition.")
    elif fan == "new":
        b.include(HVAC, "Install new exhaust fan ducted to the exterior, up to 15 feet of duct.")
    else:
        b.exclude(HVAC, "Exhaust fan work (existing fan to remain).")
    if fan != "keep":
        b.allow(HVAC, "Exhaust fan", "one unit", b.tier(90, 160, 320))

    b.include(DRYWALL, "Moisture resistant drywall on walls outside the wet area, finished ready for paint.")
    wall_sqft = 0
    if has_wet_wall:
        wall_sqft = 90 if shower == "walk_in_shower" else 60
        b.include(DRYWALL, "Cement backer board on tub or shower walls.")
        b.include(TILE, f"Waterproof membrane on wet walls, about {sqft(wall_sqft)}.",
                  "Wall tile at the tub or shower to ceiling height.")
        if shower == "walk_in_shower":
            b.include(TILE, "Waterproofed shower pan with flood test before tile.")
            b.allow(TILE, "Glass shower enclosure", "one standard size panel and door, installed",
                    b.tier(900, 1400, 2200))

    floor_tile = i.area_sqft if i.opt("floor") == "tile" else 0
    if floor_tile:
        b.include(TILE, f"Floor tile over uncoupling membrane, about {sqft(floor_tile)}.")
    else:
        b.include(FLOORING, f"Luxury vinyl plank flooring, about {sqft(i.area_sqft)}.")
        b.allow(FLOORING, "Vinyl plank material", f"{sqft(i.area_sqft)} plus 10% waste",
                i.area_sqft * WASTE * b.tier(3, 4.5, 6.5))
    tile_total = floor_tile + wall_sqft
    if tile_total:
        b.allow(TILE, "Tile material", f"{sqft(tile_total)} plus 10% waste",
                tile_total * WASTE * b.tier(4, 7, 12))
        b.assume(TILE, "Tile areas are estimated from the room size and confirmed by field measure.")
        b.exclude(TILE, "Natural stone, mosaic or patterned layouts unless priced separately.")

    b.include(CABINETS, f"Install {vanities} vanity cabinet(s) with top and sink.")
    b.allow(CABINETS, "Vanity with top", f"{vanities} unit(s)", vanities * b.tier(450, 900, 1800))

    b.include(PAINT, "Prime and two finish coats on walls and ceiling.",
              "New baseboard, painted, and touch up of door casing.",
              "Install mirror and up to five owner supplied accessories.")
    b.exclude(PAINT, "Replacing the entry door or window.")


# --------------------------------------------------------------------- kitchen


def _kitchen(b: ScopeBuilder) -> None:
    i = b.intake
    cabinets, top, run = i.opt("cabinets"), i.opt("countertop"), i.opt("cabinet_run_ft")
    flooring, layout = i.opt("flooring"), i.opt("layout_change")
    top_sqft = round(run * 2.1, 1)  # standard 25 inch deep tops

    if not i.demo_by_owner:
        removed = [name for name, gone in (("cabinets", cabinets == "replace"),
                                           ("countertops", top != "keep"),
                                           ("flooring", flooring != "keep")) if gone]
        if removed:
            b.include(DEMO, f"Remove existing {', '.join(removed)}.")
        b.include(DEMO, "Disconnect and set aside appliances that are staying.")

    if layout:
        b.include(FRAMING, "Reframe one partition or opening for the new layout, non load bearing only.")
        b.exclude(FRAMING, "Removing or altering load bearing walls.")
        b.include(PLUMBING, "Relocate sink supply and drain up to 6 feet from the existing location.")
        b.include(HVAC, "New range hood duct to the exterior, up to 10 feet.")
        b.flag("Layout change: confirm which walls are load bearing before the scope is issued.")
    else:
        b.exclude(FRAMING, "Moving walls, doors or windows.")
        b.include(PLUMBING, "Sink set in its existing location.")
        b.exclude(PLUMBING, "Relocating supply or drain lines.")
        b.include(HVAC, "Reconnect range hood to the existing duct.")
        b.assume(HVAC, "Existing hood duct terminates outdoors.")
    if cabinets == "replace":
        b.include(FRAMING, "Wall blocking for upper cabinets where walls are open.")

    b.include(PLUMBING, "Install sink, faucet and new shutoff valves.",
              "Reconnect disposal and dishwasher.")
    b.allow(PLUMBING, "Sink and faucet", "one sink and one faucet", b.tier(350, 700, 1400))
    if i.opt("gas_range"):
        b.include(PLUMBING, "Reconnect gas range in its existing location with new connector and shutoff.")
        b.exclude(PLUMBING, "Extending or relocating gas piping.")
        if layout:
            b.flag("Gas range with a layout change: gas piping is excluded. Confirm the range stays put "
                   "or add a licensed gas fitter line item.")

    if cabinets == "replace" or layout:
        b.include(ELECTRICAL, "GFCI protected countertop receptacles at current spacing where walls are open.",
                  "Dedicated circuits for dishwasher, disposal and microwave.")
        b.assume(ELECTRICAL, "Existing panel has space and capacity for up to three new circuits.")
    else:
        b.include(ELECTRICAL, "Replace existing countertop receptacles with GFCI protected devices.")
        b.exclude(ELECTRICAL, "New circuits or added receptacle locations.")
    if i.finish_tier == "premium":
        b.include(ELECTRICAL, "Under cabinet LED lighting on a wall switch.")
    b.exclude(ELECTRICAL, "Panel upgrades or service changes.")

    b.include(DRYWALL, "Patch drywall at removed cabinets, backsplash and any opened walls, ready for paint.")

    if cabinets == "replace":
        b.include(CABINETS, f"Supply and install new base and upper cabinets, about {run} linear feet.",
                  "Cabinet hardware, fillers, toe kicks and crown as selected.")
        b.allow(CABINETS, "Cabinets", f"{run} linear feet", run * b.tier(180, 320, 550))
    elif cabinets == "reface":
        b.include(CABINETS, "Reface existing cabinet boxes with new doors, drawer fronts and veneer, "
                            f"about {run} linear feet.")
        b.allow(CABINETS, "Refacing materials", f"{run} linear feet", run * b.tier(90, 150, 240))
        b.assume(CABINETS, "Existing cabinet boxes are sound, square and dry.")
    else:
        b.exclude(CABINETS, "Cabinet replacement, refacing or painting (existing cabinets to remain).")

    island_sqft = 15 if i.opt("island") else 0
    if island_sqft:
        b.include(CABINETS, "Island base cabinets, about 6 linear feet, with finished back panel.")
        b.allow(CABINETS, "Island cabinets", "6 linear feet", 6 * b.tier(180, 320, 550))
        b.include(ELECTRICAL, "One receptacle at the island fed through the floor.")
        b.assume(ELECTRICAL, "Basement or crawlspace below allows a feed to the island.")
    if top != "keep":
        rate = {"laminate": 30, "butcher_block": 55, "quartz": 85}[top]
        name = top.replace("_", " ")
        total = round(top_sqft + island_sqft, 1)
        b.include(CABINETS, f"Template, fabricate and install {name} countertops, "
                            f"about {sqft(total)}, with one sink cutout.")
        b.allow(CABINETS, f"Countertops ({name})", f"{sqft(total)}, installed", total * rate)
    else:
        b.exclude(CABINETS, "Countertop replacement (existing tops to remain).")
        b.assume(CABINETS, "Existing countertops can be worked around without removal.")
        if island_sqft:
            b.exclude(CABINETS, "Countertop for the new island (no countertop material is selected).")
            b.flag("Island added while existing countertops stay: the island has no top in this scope. "
                   "Choose a countertop material or add the island top as a line item.")

    if i.opt("backsplash"):
        splash = round(run * 1.5, 1)  # 18 inches between counter and uppers
        b.include(TILE, f"Tile backsplash from countertop to upper cabinets, about {sqft(splash)}.")
        b.allow(TILE, "Backsplash tile", f"{sqft(splash)} plus 10% waste", splash * WASTE * b.tier(4, 7, 12))
    else:
        b.exclude(TILE, "Backsplash tile.")

    if i.opt("appliances_by_owner"):
        b.include(APPLIANCES, "Install owner supplied range, dishwasher and hood or microwave; "
                              "set refrigerator in place.")
        b.exclude(APPLIANCES, "Supplying appliances.")
        b.assume(APPLIANCES, "Appliances are on site, undamaged and sized to the cabinet plan before install day.")
    else:
        b.include(APPLIANCES, "Supply and install range, dishwasher, hood or microwave and refrigerator.")
        b.allow(APPLIANCES, "Appliance package", "four pieces", b.tier(2800, 5200, 9500))

    if flooring == "keep":
        b.exclude(FLOORING, "New flooring (existing floor to remain).")
        if cabinets == "replace":
            b.flag("Cabinets are replaced but flooring stays: confirm the old floor runs under "
                   "the existing cabinet footprint.")
    else:
        rate = b.tier(3, 4.5, 6.5) if flooring == "lvp" else b.tier(4, 7, 12)
        label = "Luxury vinyl plank" if flooring == "lvp" else "Floor tile"
        b.include(FLOORING, f"{label} flooring, about {sqft(i.area_sqft)}, with transitions at doorways.")
        b.allow(FLOORING, f"{label} material", f"{sqft(i.area_sqft)} plus 10% waste", i.area_sqft * WASTE * rate)
        b.exclude(FLOORING, "Subfloor replacement or leveling beyond minor patching.")

    b.include(PAINT, "Prime and two finish coats on walls and ceiling.",
              "Baseboard and casing reinstalled or matched.")


# -------------------------------------------------------------------- basement


def _basement(b: ScopeBuilder) -> None:
    i = b.intake
    area = i.area_sqft
    bath, bedroom, egress = i.opt("add_bathroom"), i.opt("bedroom"), i.opt("egress_window")
    doors = 1 + int(bath) + int(bedroom)

    if not i.demo_by_owner:
        b.include(DEMO, "Remove loose wall coverings, old shelving and abandoned framing in the finish area.")

    if i.opt("moisture_history"):
        b.exclude(GENERAL, "Waterproofing, drainage, sump or foundation crack repair.")
        b.assume(GENERAL, "Owner has resolved past water entry. This scope does not warrant a dry basement.")
        b.include(FLOORING, "Slab moisture test before flooring is installed.")
        b.flag("Moisture history reported: get the source and the fix in writing before finishing walls.")
    else:
        b.assume(GENERAL, "Basement has no history of water entry.")

    b.include(FRAMING, "Perimeter walls framed with pressure treated bottom plates, held off the foundation.",
              "Soffits around ducts, beams and drain lines.")
    rooms = [name for name, on in (("bedroom", bedroom), ("bathroom", bath)) if on]
    if rooms:
        b.include(FRAMING, f"Partition walls and door openings for: {', '.join(rooms)}.")
    b.exclude(FRAMING, "Structural changes, post relocation or stair rebuilds.")
    b.assume(FRAMING, "Finished ceiling height meets the local minimum after framing and flooring.")

    if bath:
        b.include(PLUMBING, "Three piece bathroom: toilet, vanity and shower connected to existing rough in.")
        b.allow(PLUMBING, "Bathroom fixtures", "toilet, vanity, faucet and shower trim", b.tier(1400, 2500, 4800))
        b.assume(PLUMBING, "Under slab drain rough in for the bathroom already exists and is usable.")
        b.exclude(PLUMBING, "Cutting the slab, new under slab drains or a sewage ejector pump.")
        b.flag("Basement bathroom: confirm the under slab rough in exists. If not, slab work and "
               "an ejector pump must be added.")
        b.include(HVAC, "Bathroom exhaust fan ducted to the exterior.")
        b.include(TILE, "Shower wall tile over waterproof membrane, about 60 sq ft.",
                  f"Bathroom floor tile, about {BASEMENT_BATH_FLOOR_SQFT} sq ft.")
        b.allow(TILE, "Tile material", "100 sq ft plus 10% waste", 100 * WASTE * b.tier(4, 7, 12))
    if i.opt("wet_bar"):
        b.include(PLUMBING, "Bar sink with supply and drain tied in within 10 feet of existing lines.")
        b.include(CABINETS, "Wet bar: 6 linear feet of base cabinets with laminate top.")
        b.allow(CABINETS, "Wet bar cabinets, top and sink", "6 linear feet", 6 * b.tier(220, 380, 620))
    if not bath and not i.opt("wet_bar"):
        b.exclude(PLUMBING, "All plumbing work (no fixtures in this scope).")

    lights = math.ceil(area / 40)
    b.include(ELECTRICAL, "Receptacles at code spacing on new walls, on new circuits.",
              f"{lights} recessed LED lights on switched zones.",
              "Interconnected smoke and carbon monoxide alarms as required.")
    b.allow(ELECTRICAL, "Recessed lights", f"{lights} fixtures, one per 40 sq ft", lights * b.tier(25, 40, 70))
    b.assume(ELECTRICAL, "Existing panel has space and capacity for the new circuits.")
    b.exclude(ELECTRICAL, "Panel upgrades or service changes.")

    runs = math.ceil(area / 150)
    b.include(HVAC, f"Extend {runs} supply run(s) and one return from the existing trunk line.")
    b.assume(HVAC, "Existing heating and cooling equipment has capacity for the added space.")
    b.exclude(HVAC, "New equipment, zoning or dehumidification.")

    b.include(DRYWALL, "Rigid foam against foundation walls with batt insulation in the framed wall.",
              "Drywall on new walls, finished ready for paint.")
    if i.opt("ceiling") == "drywall":
        b.include(DRYWALL, "Drywall ceiling with access panels at shutoffs and cleanouts.")
    else:
        b.include(DRYWALL, f"Suspended ceiling grid and tile, about {sqft(area)}.")
        b.allow(DRYWALL, "Ceiling tile and grid", f"{sqft(area)} plus 10% waste", area * WASTE * b.tier(2, 3, 4.5))

    if egress:
        b.include(EGRESS, "Cut foundation and install one code compliant egress window with well and cover.")
        b.allow(EGRESS, "Egress window, well and cover", "one opening", b.tier(1800, 2400, 3200))
        b.exclude(EGRESS, "Landscape restoration beyond rough backfill.")
        b.assume(EGRESS, "No buried utilities at the window location; owner arranges utility marking.")
    elif bedroom:
        b.assume(EGRESS, "An existing code compliant egress opening serves the bedroom.")
        b.exclude(EGRESS, "New egress window or well.")
        b.flag("Bedroom without a new egress window: verify the existing opening meets egress size "
               "and sill height, or the room cannot be listed as a bedroom.")

    # The bathroom floor is tiled under the tile trade, so it is not counted again here.
    floor = area - BASEMENT_BATH_FLOOR_SQFT if bath else area
    if i.opt("flooring") == "lvp":
        b.include(FLOORING, f"Luxury vinyl plank flooring over the slab, about {sqft(floor)}.")
        b.allow(FLOORING, "Vinyl plank material", f"{sqft(floor)} plus 10% waste",
                floor * WASTE * b.tier(3, 4.5, 6.5))
    else:
        b.include(FLOORING, f"Carpet and pad over the slab, about {sqft(floor)}.")
        b.allow(FLOORING, "Carpet and pad material", f"{sqft(floor)} plus 10% waste",
                floor * WASTE * b.tier(2.5, 4, 6))
    b.exclude(FLOORING, "Slab grinding, leveling compound or raised subfloor panels.")

    b.include(PAINT, "Prime and two finish coats on walls and drywall ceilings.",
              f"{doors} interior door(s) with casing and hardware.", "Baseboard throughout the finished area.")
    b.allow(PAINT, "Interior doors and hardware", f"{doors} door(s)", doors * b.tier(140, 220, 380))
