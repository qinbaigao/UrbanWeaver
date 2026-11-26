import unittest

from cityg.planning.programs import FloorProfile


class FloorCycleContractTests(unittest.TestCase):
    def profile(self, cycle):
        return FloorProfile.from_dict({
            "function": "commercial", "layout": "office_core",
            "corridor_ratio": 0.2, "room_function_cycle": cycle,
        })

    def test_role_keyed_cycle_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "flat array.*role-keyed"):
            self.profile({"ground": ["shop"], "typical": ["office"]})

    def test_flat_cycle_and_legacy_string_remain_supported(self):
        self.assertEqual(self.profile(["office", "meeting_room"]).room_function_cycle,
                         ("office", "meeting_room"))
        self.assertEqual(self.profile("office, meeting_room").room_function_cycle,
                         ("office", "meeting_room"))
