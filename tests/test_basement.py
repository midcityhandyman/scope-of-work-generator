import unittest

from sowgen import rules as r

from .helpers import allowance, scope_for


class BasementTests(unittest.TestCase):
    def test_default_basement_trades(self):
        scope = scope_for("basement")
        self.assertEqual(
            scope.trades(),
            [r.GENERAL, r.DEMO, r.FRAMING, r.PLUMBING, r.ELECTRICAL, r.HVAC, r.DRYWALL,
             r.FLOORING, r.PAINT, r.CLOSEOUT],
        )
        self.assertEqual(scope.review_flags, [])

    def test_no_fixtures_means_plumbing_is_excluded_entirely(self):
        plumbing = scope_for("basement").section(r.PLUMBING)
        self.assertEqual(plumbing.inclusions, [])
        self.assertEqual(plumbing.exclusions, ["All plumbing work (no fixtures in this scope)."])

    def test_counts_scale_with_area(self):
        scope = scope_for("basement", area=600)
        self.assertTrue(any(line.startswith("15 recessed LED") for line in scope.section(r.ELECTRICAL).inclusions))
        self.assertTrue(any(line.startswith("Extend 4 supply run(s)") for line in scope.section(r.HVAC).inclusions))
        self.assertEqual(allowance(scope, r.ELECTRICAL, "Recessed lights"), 15 * 40)
        big = scope_for("basement", area=1000)
        self.assertTrue(any(line.startswith("25 recessed LED") for line in big.section(r.ELECTRICAL).inclusions))

    def test_bathroom_adds_plumbing_tile_fan_and_review_flag(self):
        scope = scope_for("basement", options={"add_bathroom": True})
        self.assertIn(r.TILE, scope.trades())
        plumbing = scope.section(r.PLUMBING)
        self.assertTrue(any("Three piece bathroom" in line for line in plumbing.inclusions))
        self.assertTrue(any("ejector pump" in line for line in plumbing.exclusions))
        self.assertTrue(any("exhaust fan" in line for line in scope.section(r.HVAC).inclusions))
        self.assertTrue(any("rough in" in flag for flag in scope.review_flags))
        self.assertEqual(allowance(scope, r.TILE, "Tile material"), 770)

    def test_bedroom_without_egress_is_flagged(self):
        scope = scope_for("basement", options={"bedroom": True})
        egress = scope.section(r.EGRESS)
        self.assertEqual(egress.inclusions, [])
        self.assertIn("New egress window or well.", egress.exclusions)
        self.assertTrue(any("egress" in flag for flag in scope.review_flags))

    def test_bedroom_with_egress_window_has_allowance_and_no_flag(self):
        scope = scope_for("basement", options={"bedroom": True, "egress_window": True})
        self.assertEqual(allowance(scope, r.EGRESS, "Egress window, well and cover"), 2400)
        self.assertEqual(scope.review_flags, [])

    def test_door_count_follows_rooms(self):
        plain = scope_for("basement")
        full = scope_for("basement", options={"bedroom": True, "add_bathroom": True})
        self.assertEqual(allowance(plain, r.PAINT, "Interior doors and hardware"), 220)
        self.assertEqual(allowance(full, r.PAINT, "Interior doors and hardware"), 660)
        self.assertIn("Partition walls and door openings for: bedroom, bathroom.",
                      full.section(r.FRAMING).inclusions)

    def test_moisture_history_excludes_waterproofing_and_flags(self):
        wet = scope_for("basement", options={"moisture_history": True})
        dry = scope_for("basement")
        self.assertIn("Waterproofing, drainage, sump or foundation crack repair.",
                      wet.section(r.GENERAL).exclusions)
        self.assertIn("Slab moisture test before flooring is installed.", wet.section(r.FLOORING).inclusions)
        self.assertEqual(len(wet.review_flags), 1)
        self.assertIn("Basement has no history of water entry.", dry.section(r.GENERAL).assumptions)

    def test_ceiling_choice(self):
        drywall = scope_for("basement").section(r.DRYWALL)
        drop = scope_for("basement", options={"ceiling": "drop"}).section(r.DRYWALL)
        self.assertEqual(drywall.allowances, [])
        # 600 * 1.1 * 3 = 1980
        self.assertEqual(drop.allowances[0].amount, 1980)

    def test_flooring_choice(self):
        lvp = scope_for("basement")
        carpet = scope_for("basement", options={"flooring": "carpet"})
        self.assertEqual(allowance(lvp, r.FLOORING, "Vinyl plank material"), 2970)
        self.assertEqual(allowance(carpet, r.FLOORING, "Carpet and pad material"), 2640)

    def test_wet_bar_adds_plumbing_and_cabinets(self):
        scope = scope_for("basement", options={"wet_bar": True})
        self.assertIn(r.CABINETS, scope.trades())
        self.assertTrue(any("Bar sink" in line for line in scope.section(r.PLUMBING).inclusions))
        self.assertEqual(allowance(scope, r.CABINETS, "Wet bar cabinets, top and sink"), 2280)


if __name__ == "__main__":
    unittest.main()
