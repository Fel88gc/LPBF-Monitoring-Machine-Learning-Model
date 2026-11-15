"""Analytical checks of fixed image descriptors, independent of project data."""

import math
import unittest

import numpy as np

from extract_features import FEATURE_NAMES, extract_sensor_features


class SensorFeatureTests(unittest.TestCase):
    def test_constants_and_endpoints(self):
        image = np.empty((1, 3, 24, 24), dtype=np.float32)
        image[:, 0] = 0
        image[:, 1] = 1
        image[:, 2] = 0.5
        observed = extract_sensor_features(image)[0].reshape(3, 14)
        for row, value in zip(observed, (0, 1, 0.5)):
            np.testing.assert_allclose(row[[0, 2, 3, 4, 5, 6, 7]], value, atol=0)
            np.testing.assert_array_equal(row[[1, 10, 11, 12, 13]], 0)
        np.testing.assert_array_equal(observed[:, 8], (1, 0, 0))
        np.testing.assert_array_equal(observed[:, 9], (0, 1, 0))

    def test_horizontal_and_vertical_linear_ramps(self):
        image = np.empty((1, 3, 24, 24), dtype=np.float32)
        ramp = np.arange(24, dtype=np.float32) / 23
        image[:, 0] = ramp[None, :]
        image[:, 1] = ramp[:, None]
        image[:, 2] = 0
        observed = extract_sensor_features(image)[0].reshape(3, 14)
        np.testing.assert_allclose(observed[:2, 0], 0.5, atol=3e-8)
        np.testing.assert_allclose(observed[:2, 1], math.sqrt(575 / (12 * 23**2)), atol=3e-8)
        np.testing.assert_allclose(observed[0, 10:13], (1/23, 0, 1/(23*math.sqrt(2))), atol=3e-8)
        np.testing.assert_allclose(observed[1, 10:13], (0, 1/23, 1/(23*math.sqrt(2))), atol=3e-8)
        np.testing.assert_allclose(observed[:2, 5], 0.5, atol=3e-8)
        np.testing.assert_allclose(observed[:2, 8:10], 1/24, atol=3e-8)

    def test_binary_checkerboard_entropy_and_gradient(self):
        checkerboard = (np.indices((24, 24)).sum(axis=0) % 2).astype(np.float32)
        image = np.broadcast_to(checkerboard, (1, 3, 24, 24))
        observed = extract_sensor_features(image)[0].reshape(3, 14)
        # Two equally probable bins give one bit; normalization by four gives .25.
        np.testing.assert_allclose(observed[:, [0, 1, 5, 8, 9]], 0.5, atol=0)
        np.testing.assert_array_equal(observed[:, 10:13], 1)
        np.testing.assert_array_equal(observed[:, 13], 0.25)
        np.testing.assert_array_equal(observed[:, 4], 0)
        np.testing.assert_array_equal(observed[:, 6:8], 1)

    def test_uniform_sixteen_bin_entropy_and_last_edge(self):
        # 576/16=36 occurrences in every bin, with exact 1 in final bin.
        levels = np.arange(16, dtype=np.float32) / 16
        levels[-1] = 1
        image = np.broadcast_to(np.repeat(levels, 36).reshape(24, 24), (1, 3, 24, 24))
        observed = extract_sensor_features(image)[0].reshape(3, 14)
        np.testing.assert_array_equal(observed[:, 13], 1)
        np.testing.assert_array_equal(observed[:, 8:10], 1/16)

    def test_channel_isolation_and_sensor_only_schema(self):
        image = np.zeros((2, 3, 24, 24), dtype=np.float32)
        image[1, 1] = 0.75
        observed = extract_sensor_features(image)
        np.testing.assert_array_equal(observed[0, :14], observed[1, :14])
        np.testing.assert_array_equal(observed[0, 28:], observed[1, 28:])
        self.assertEqual(len(FEATURE_NAMES), 42)
        self.assertEqual(len(set(FEATURE_NAMES)), 42)
        self.assertFalse(any(token in name for name in FEATURE_NAMES for token in ("candidate", "label", "flaw", "part_id", "layer", "quality", "coordinate")))
        self.assertEqual(observed.dtype, np.float32)

    def test_invalid_inputs_fail_and_empty_cohort_is_well_defined(self):
        self.assertEqual(extract_sensor_features(np.empty((0, 3, 24, 24), dtype=np.float32)).shape, (0, 42))
        for value in (float("nan"), float("inf"), -0.1, 1.1):
            with self.assertRaises(ValueError):
                extract_sensor_features(np.full((1, 3, 24, 24), value, dtype=np.float32))
        with self.assertRaises(ValueError):
            extract_sensor_features(np.zeros((1, 24, 24, 3), dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
