"""Small deterministic tests for scientific reporting edge cases."""
import json
import unittest
import warnings

import numpy as np

try:
    from .evaluation import binary_metrics, per_group_metrics
except ImportError:
    from evaluation import binary_metrics, per_group_metrics


class EvaluationTests(unittest.TestCase):
    def test_toy_metrics_and_rank_metrics(self):
        result = binary_metrics([0, 0, 1, 1], [.1, .6, .4, .8])
        self.assertEqual({key: result[key] for key in ("tn", "fp", "fn", "tp")}, {"tn": 1, "fp": 1, "fn": 1, "tp": 1})
        for key in ("prevalence", "accuracy", "balanced_accuracy", "precision", "recall", "f1"):
            self.assertEqual(result[key], .5)
        self.assertAlmostEqual(result["average_precision"], 5 / 6)
        self.assertEqual(result["roc_auc"], .75)
        self.assertEqual((result["n"], result["positive"], result["negative"]), (4, 2, 2))
        json.dumps(result, allow_nan=False)

    def test_threshold_is_inclusive(self):
        result = binary_metrics([0, 1], [.4999, .5])
        self.assertEqual((result["tn"], result["tp"]), (1, 1))
        self.assertEqual(result["accuracy"], 1.)
        result = binary_metrics([0, 1], [.5, .49])
        self.assertEqual((result["fp"], result["fn"]), (1, 1))

    def test_single_negative_class_has_no_ranking_or_balanced_metric(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = binary_metrics([0, 0], [.1, .9])
        self.assertEqual(caught, [])
        for key in ("average_precision", "roc_auc", "balanced_accuracy", "recall"):
            self.assertIsNone(result[key])
        self.assertEqual((result["accuracy"], result["precision"], result["f1"]), (.5, 0., 0.))
        json.dumps(result, allow_nan=False)

    def test_single_positive_class(self):
        result = binary_metrics([1, 1], [.4, .6])
        for key in ("average_precision", "roc_auc", "balanced_accuracy"):
            self.assertIsNone(result[key])
        self.assertEqual((result["precision"], result["recall"]), (1., .5))
        self.assertAlmostEqual(result["f1"], 2 / 3)

    def test_empty_subset_is_json_safe(self):
        result = binary_metrics([], [])
        for key in ("n", "positive", "negative", "tn", "fp", "fn", "tp"):
            self.assertEqual(result[key], 0)
            self.assertIs(type(result[key]), int)
        for key in ("prevalence", "accuracy", "balanced_accuracy", "precision", "recall", "f1", "average_precision", "roc_auc"):
            self.assertIsNone(result[key])
        self.assertEqual(per_group_metrics([], [], []), [])
        json.dumps(result, allow_nan=False)

    def test_no_predicted_positives(self):
        result = binary_metrics([0, 1], [.1, .2])
        self.assertIsNone(result["precision"])
        self.assertEqual((result["recall"], result["f1"]), (0., 0.))
        all_negative = binary_metrics([0, 0], [.1, .2])
        self.assertIsNone(all_negative["precision"])
        self.assertIsNone(all_negative["recall"])
        self.assertIsNone(all_negative["f1"])

    def test_group_order_metrics_and_native_types(self):
        result = per_group_metrics(np.array([0, 1, 0, 1]), np.array([.9, .6, .1, .7]), np.array([9, 9, 2, 2], dtype=np.int32))
        self.assertEqual([row["part_id"] for row in result], [2, 9])
        self.assertTrue(all(type(row["part_id"]) is int for row in result))
        self.assertEqual(result[0]["accuracy"], 1.)
        self.assertEqual(result[1]["accuracy"], .5)
        self.assertEqual(result[1]["roc_auc"], 0.)
        json.dumps(result, allow_nan=False)
        named = per_group_metrics([0, 1], [.1, .9], ["P9", "P2"])
        self.assertEqual([row["part_id"] for row in named], ["P2", "P9"])

    def test_invalid_inputs_do_not_silently_drop_unknown_rows(self):
        invalid = [([-1, 1], [.1, .9]), ([0, 1], [.1]), ([[0], [1]], [.1, .9]),
                   ([0, 1], [[.1], [.9]]), ([0, 1], [.1, np.nan]), ([0, 1], [.1, np.inf])]
        for labels, scores in invalid:
            with self.subTest(labels=labels, scores=scores), self.assertRaises(ValueError):
                binary_metrics(labels, scores)
        for groups in ([2], [2, None], [2, np.nan], [2, 1.5], [2, True]):
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                per_group_metrics([0, 1], [.1, .9], groups)
        with self.assertRaises(ValueError):
            binary_metrics([0, 1], [.1, .9], threshold=np.nan)

    def test_finite_decision_scores_are_supported(self):
        result = binary_metrics([0, 1], [-2., 1.], threshold=0.)
        self.assertEqual(result["accuracy"], 1.)
        self.assertEqual(result["roc_auc"], 1.)


if __name__ == "__main__":
    unittest.main()
