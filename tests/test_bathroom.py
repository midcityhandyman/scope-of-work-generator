import unittest

from sowgen import rules as r

from .helpers import all_lines, allowance, scope_for


class BathroomTests(unittest.TestCase):
    def test_default_bathroom_trades_in_site_order(self):
        scope = scope_for("bathroom")
        self.assertEqual(
            scope.trades(),
            [r.GENERAL, r.DEMO, r.FRAMING, r.PLUMBING, r.ELECTRICAL, r.HVAC, r.DRYWALL,
             r.TILE, r.CABINETS, r.PAINT, r.CLOSEOUT],
        )
        self.assertEqual(scope.title, "Scope of Work: Bathroom Remodel")
        self.assertEqual(scope.review_flags, [])

    def test_every_section_has_content_and_general_lists_exist(self):
        scope = scope_for("bathroom")
        for section in scope.sections:
            self.assertFalse(section.is_empty(), section.trade)
        self.assertTrue(scope.general_exclusions)
        self.assertTrue(scope.general_assumptions)

    def test_tile_allowance_math(self):
        # 50 sq ft floor + 60 sq ft tub surround = 110, plus 10% waste, at $7 standard = 847 -> 850
        scope = scope_for("bathroom")
        self.assertEqual(allowance(scope, r.TILE, "Tile material"), 850)
        # walk in shower uses 90 sq ft of wall; premium rate $12: 140 * 1.1 * 12 = 1848 -> 1850
        scope = scope_for("bathroom", options={"shower": "walk_in_shower"}, finish_tier="premium")
        self.assertEqual(allowance(scope, r.TILE, "Tile material"), 1850)
        self.assertEqual(allowance(scope, r.TILE, "Glass shower enclosure"), 2200)

    def test_tiers_scale_allowances(self):
        totals = [scope_for("bathroom", finish_tier=t).allowance_total for t in ("basic", "standard", "premium")]
        self.assertEqual(totals, sorted(totals))
        self.assertLess(totals[0], totals[2])

    def test_no_layout_change_excludes_relocation(self):
        scope = scope_for("bathroom")
        self.assertIn("Relocating drains or supply lines.", scope.section(r.PLUMBING).exclusions)
        self.assertIn("Moving walls, doors or windows.", scope.section(r.FRAMING).exclusions)

    def test_layout_change_includes_relocation_and_flags_review(self):
        scope = scope_for("bathroom", options={"layout_change": True})
        plumbing = scope.section(r.PLUMBING)
        self.assertTrue(any("Relocate supply and drain" in line for line in plumbing.inclusions))
        self.assertNotIn("Relocating drains or supply lines.", plumbing.exclusions)
        self.assertEqual(len(scope.review_flags), 1)

    def test_lvp_floor_without_shower_drops_tile_trade(self):
        scope = scope_for("bathroom", options={"floor": "lvp", "shower": "none"})
        self.assertNotIn(r.TILE, scope.trades())
        self.assertIn(r.FLOORING, scope.trades())
        # 50 * 1.1 * 4.5 = 247.5 -> 250
        self.assertEqual(allowance(scope, r.FLOORING, "Vinyl plank material"), 250)

    def test_heated_floor_adds_circuit_assumption(self):
        scope = scope_for("bathroom", options={"heated_floor": True})
        electrical = scope.section(r.ELECTRICAL)
        self.assertIn("Existing panel has space and capacity for one new circuit.", electrical.assumptions)
        # 180 + 50 * 11 = 730
        self.assertEqual(allowance(scope, r.ELECTRICAL, "Floor warming mat and thermostat"), 730)

    def test_fan_keep_is_an_exclusion_with_no_allowance(self):
        hvac = scope_for("bathroom", options={"exhaust_fan": "keep"}).section(r.HVAC)
        self.assertEqual(hvac.inclusions, [])
        self.assertEqual(hvac.allowances, [])
        self.assertEqual(len(hvac.exclusions), 1)

    def test_double_vanity_doubles_vanity_allowance(self):
        one = allowance(scope_for("bathroom"), r.CABINETS, "Vanity with top")
        two = allowance(scope_for("bathroom", options={"vanity_count": 2}), r.CABINETS, "Vanity with top")
        self.assertEqual(two, 2 * one)

    def test_pre_1978_home_adds_lead_safe_language(self):
        old = scope_for("bathroom", year_built=1960)
        new = scope_for("bathroom", year_built=1990)
        self.assertTrue(any("lead safe" in line for line in all_lines(old)))
        self.assertFalse(any("lead" in line for line in all_lines(new)))
        self.assertEqual(len(old.review_flags), 1)

    def test_owner_demo_and_owner_permit(self):
        scope = scope_for("bathroom", demo_by_owner=True, permit_by="owner")
        demo = scope.section(r.DEMO)
        self.assertFalse(any("Remove toilet" in line for line in demo.inclusions))
        self.assertTrue(any("by owner" in line for line in demo.exclusions))
        general = scope.section(r.GENERAL)
        self.assertEqual(general.allowances, [])
        self.assertTrue(any("by owner" in line for line in general.exclusions))


if __name__ == "__main__":
    unittest.main()
