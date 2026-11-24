import json
import tempfile
import unittest
from pathlib import Path

from sowgen import Intake, IntakeError
from sowgen.intake import ROOM_OPTIONS, describe_schema

from .helpers import EXAMPLES


def base(room="bathroom", area=50, **extra):
    return {"project_id": "T-1", "room_type": room, "area_sqft": area, **extra}


class IntakeTests(unittest.TestCase):
    def problems(self, data):
        with self.assertRaises(IntakeError) as ctx:
            Intake.from_dict(data)
        return ctx.exception.problems

    def test_defaults_are_filled_for_every_room(self):
        for room, area in (("bathroom", 50), ("kitchen", 150), ("basement", 600)):
            intake = Intake.from_dict(base(room, area))
            self.assertEqual(set(intake.options), set(ROOM_OPTIONS[room]))
            self.assertEqual(intake.finish_tier, "standard")

    def test_example_files_load(self):
        for name in ("bathroom", "kitchen", "basement"):
            self.assertEqual(Intake.from_file(EXAMPLES / f"{name}.json").room_type, name)

    def test_unknown_room_type(self):
        self.assertIn("room_type must be one of bathroom, kitchen, basement", self.problems(base("garage")))

    def test_missing_required_fields_reported_together(self):
        problems = self.problems({})
        self.assertEqual(len(problems), 3)

    def test_unknown_field_and_unknown_option(self):
        problems = self.problems(base(colour="blue", options={"sauna": True}))
        self.assertIn("unknown field: colour", problems)
        self.assertIn("unknown bathroom option: sauna", problems)

    def test_area_out_of_range_for_room(self):
        self.assertIn("area_sqft for a bathroom must be between 20 and 200", self.problems(base(area=900)))
        Intake.from_dict(base("basement", 900))

    def test_type_checks(self):
        self.assertTrue(self.problems(base(area="big")))
        self.assertTrue(self.problems(base(area=True)))
        self.assertTrue(self.problems(base(occupied="yes")))
        self.assertTrue(self.problems(base(options={"layout_change": 1})))
        self.assertTrue(self.problems(base(options={"vanity_count": 3})))
        self.assertTrue(self.problems(base(options={"shower": "steam"})))
        self.assertTrue(self.problems(base(options=["tile"])))
        self.assertTrue(self.problems(base(finish_tier="luxury")))
        self.assertTrue(self.problems(base(year_built=1492)))

    def test_cross_field_rules(self):
        self.assertIn(
            "options.heated_floor requires options.floor to be tile",
            self.problems(base(options={"heated_floor": True, "floor": "lvp"})),
        )
        self.assertIn(
            "options.countertop cannot be keep when cabinets are replaced",
            self.problems(base("kitchen", 150, options={"countertop": "keep"})),
        )

    def test_bad_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(IntakeError):
                Intake.from_file(path)
            path.write_text(json.dumps([1, 2]), encoding="utf-8")
            with self.assertRaises(IntakeError):
                Intake.from_file(path)

    def test_describe_schema_lists_every_option(self):
        text = describe_schema()
        for spec in ROOM_OPTIONS.values():
            for name in spec:
                self.assertIn(name, text)


if __name__ == "__main__":
    unittest.main()
