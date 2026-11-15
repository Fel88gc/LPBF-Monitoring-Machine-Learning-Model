"""Small regression tests for consequential crop-boundary conventions."""
import unittest
from compare_spatial import crop_bounds


class CoordinatePolicyTests(unittest.TestCase):
    def test_recorded_positive_example(self):
        scale = 13752 / 2844
        self.assertEqual(crop_bounds(1997, 1994, 24, scale, scale, "pilot_round"),
                         (9656, 9772, 9642, 9758))
        self.assertEqual(crop_bounds(1997, 1994, 24, scale, scale, "audit_floor_ceil"),
                         (9656, 9773, 9641, 9758))
        self.assertEqual(crop_bounds(1997, 1994, 24, scale, scale, "export_floor"),
                         (9656, 9772, 9641, 9757))

    def test_adjacent_pilot_crops_share_boundary_not_pixels(self):
        scale = 13752 / 2844
        first = crop_bounds(1997, 1994, 24, scale, scale, "pilot_round")
        adjacent = crop_bounds(2021, 1994, 24, scale, scale, "pilot_round")
        self.assertEqual(first[1], adjacent[0])
        self.assertEqual(set(range(first[0], first[1])) & set(range(adjacent[0], adjacent[1])), set())

    def test_independent_x_and_y_scales(self):
        self.assertEqual(crop_bounds(3, 5, 2, 2, 3, "pilot_round"), (6, 10, 15, 21))

    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError):
            crop_bounds(0, 0, 24, 1, 1, "unrecorded")


if __name__ == "__main__":
    unittest.main()
