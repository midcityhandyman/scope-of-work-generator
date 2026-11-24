import unittest

from sowgen import rules as r

from .helpers import allowance, scope_for


class KitchenTests(unittest.TestCase):
    def test_default_kitchen_trades(self):
        scope = scope_for("kitchen")
        self.assertEqual(
            scope.trades(),
            [r.GENERAL, r.DEMO, r.FRAMING, r.PLUMBING, r.ELECTRICAL, r.HVAC, r.DRYWALL,
             r.TILE, r.CABINETS, r.APPLIANCES, r.FLOORING, r.PAINT, r.CLOSEOUT],
        )
        self.assertEqual(scope.review_flags, [])

    def test_cabinet_and_countertop_allowances(self):
        scope = scope_for("kitchen")  # 20 ft run, standard tier, quartz
        self.assertEqual(allowance(scope, r.CABINETS, "Cabinets"), 20 * 320)
        # 20 ft * 2.1 = 42 sq ft at $85 = 3570
        self.assertEqual(allowance(scope, r.CABINETS, "Countertops (quartz)"), 3570)
        # backsplash 30 sq ft * 1.1 * 7 = 231 -> 240
        self.assertEqual(allowance(scope, r.TILE, "Backsplash tile"), 240)

    def test_island_with_kept_countertops_is_excluded_and_flagged(self):
        scope = scope_for("kitchen", options={"island": True, "cabinets": "keep", "countertop": "keep"})
        cabinets = scope.section(r.CABINETS)
        self.assertTrue(any("Island base cabinets" in line for line in cabinets.inclusions))
        self.assertTrue(any("Countertop for the new island" in line for line in cabinets.exclusions))
        self.assertTrue(any("island has no top" in flag for flag in scope.review_flags))
        with_top = scope_for("kitchen", options={"island": True})
        self.assertFalse(any("island" in flag.lower() for flag in with_top.review_flags))

    def test_island_adds_cabinets_top_area_and_receptacle(self):
        scope = scope_for("kitchen", options={"island": True, "countertop": "laminate"})
        self.assertEqual(allowance(scope, r.CABINETS, "Island cabinets"), 6 * 320)
        # (42 + 15) sq ft at $30 = 1710
        self.assertEqual(allowance(scope, r.CABINETS, "Countertops (laminate)"), 1710)
        self.assertTrue(any("island" in line for line in scope.section(r.ELECTRICAL).inclusions))

    def test_reface_keeps_boxes_and_assumes_they_are_sound(self):
        cabinets = scope_for("kitchen", options={"cabinets": "reface"}).section(r.CABINETS)
        self.assertTrue(any("Reface existing cabinet boxes" in line for line in cabinets.inclusions))
        self.assertIn("Existing cabinet boxes are sound, square and dry.", cabinets.assumptions)
        self.assertEqual(cabinets.allowances[0].amount, 20 * 150)

    def test_keep_everything_is_mostly_exclusions(self):
        scope = scope_for("kitchen", options={
            "cabinets": "keep", "countertop": "keep", "flooring": "keep", "backsplash": False})
        self.assertEqual(scope.section(r.CABINETS).inclusions, [])
        self.assertEqual(len(scope.section(r.CABINETS).exclusions), 2)
        self.assertEqual(scope.section(r.FLOORING).inclusions, [])
        self.assertEqual(scope.section(r.TILE).exclusions, ["Backsplash tile."])
        self.assertIn("New circuits or added receptacle locations.", scope.section(r.ELECTRICAL).exclusions)
        demo = scope.section(r.DEMO)
        self.assertFalse(any(line.startswith("Remove existing") for line in demo.inclusions))

    def test_demo_line_lists_only_what_is_replaced(self):
        demo = scope_for("kitchen", options={"flooring": "keep"}).section(r.DEMO)
        self.assertIn("Remove existing cabinets, countertops.", demo.inclusions)

    def test_keep_floor_with_new_cabinets_is_flagged(self):
        scope = scope_for("kitchen", options={"flooring": "keep"})
        self.assertEqual(len(scope.review_flags), 1)
        self.assertIn("flooring stays", scope.review_flags[0])

    def test_layout_change_and_gas_range_flags(self):
        scope = scope_for("kitchen", options={"layout_change": True, "gas_range": True})
        self.assertEqual(len(scope.review_flags), 2)
        plumbing = scope.section(r.PLUMBING)
        self.assertIn("Extending or relocating gas piping.", plumbing.exclusions)
        self.assertIn("Removing or altering load bearing walls.", scope.section(r.FRAMING).exclusions)
        self.assertTrue(any("New range hood duct" in line for line in scope.section(r.HVAC).inclusions))

    def test_appliances_owner_supplied_versus_package(self):
        owner = scope_for("kitchen").section(r.APPLIANCES)
        self.assertEqual(owner.allowances, [])
        self.assertIn("Supplying appliances.", owner.exclusions)
        package = scope_for("kitchen", options={"appliances_by_owner": False}, finish_tier="basic")
        self.assertEqual(allowance(package, r.APPLIANCES, "Appliance package"), 2800)

    def test_premium_tier_adds_under_cabinet_lighting(self):
        def has_lighting(tier):
            lines = scope_for("kitchen", finish_tier=tier).section(r.ELECTRICAL).inclusions
            return any("Under cabinet LED" in line for line in lines)
        self.assertTrue(has_lighting("premium"))
        self.assertFalse(has_lighting("standard"))

    def test_tile_floor_uses_tile_rate(self):
        scope = scope_for("kitchen", options={"flooring": "tile"})
        # 150 * 1.1 * 7 = 1155 -> 1160
        self.assertEqual(allowance(scope, r.FLOORING, "Floor tile material"), 1160)

    def test_allowance_total_matches_sum_of_rows(self):
        scope = scope_for("kitchen", options={"island": True})
        rows = [a.amount for s in scope.sections for a in s.allowances]
        self.assertEqual(scope.allowance_total, sum(rows))
        self.assertTrue(all(amount % 10 == 0 for amount in rows))


if __name__ == "__main__":
    unittest.main()
