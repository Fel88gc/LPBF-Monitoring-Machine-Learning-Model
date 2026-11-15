"""Evaluate agreement with supplied binary reference annotations.

These functions do not establish physical flaw validity, registration, coverage,
or pore-prediction performance. Callers must select their documented reference
labels first; unknown candidate label -1 is deliberately rejected.
"""
from __future__ import annotations

import math

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


def _inputs(y_true, scores, threshold):
    labels = np.asarray(y_true)
    try:
        values = np.asarray(scores, dtype=np.float64)
        cutoff = float(threshold)
    except (TypeError, ValueError) as exc:
        raise ValueError("Scores and threshold must be numeric") from exc
    if labels.ndim != 1 or values.ndim != 1:
        raise ValueError("Labels and scores must be one-dimensional")
    if len(labels) != len(values):
        raise ValueError("Labels and scores must have the same length")
    if not np.isin(labels, [0, 1]).all():
        raise ValueError("Reference labels must be binary 0/1; filter unknown targets explicitly")
    if not np.isfinite(values).all() or not math.isfinite(cutoff):
        raise ValueError("Scores and threshold must be finite")
    return labels.astype(np.uint8, copy=False), values, cutoff


def _ratio(numerator: int, denominator: int) -> float | None:
    return float(numerator / denominator) if denominator else None


def binary_metrics(y_true, scores, threshold=0.5) -> dict:
    """Return JSON-safe binary metrics using ``scores >= threshold``.

    Scores may be probabilities or other finite decision scores; they are not
    required to lie in [0, 1]. Average precision is sklearn's non-interpolated
    AP, not trapezoidal PR AUC. AP, ROC AUC and balanced accuracy are reported
    only when both reference classes are present. Other ratios are None when
    their denominator is zero. Empty input has zero counts and None rates.
    """
    labels, values, cutoff = _inputs(y_true, scores, threshold)
    predicted = values >= cutoff
    positive_mask = labels == 1
    n = int(labels.size)
    positive = int(np.count_nonzero(positive_mask))
    negative = n - positive
    tp = int(np.count_nonzero(positive_mask & predicted))
    fn = positive - tp
    fp = int(np.count_nonzero(~positive_mask & predicted))
    tn = negative - fp
    both_classes = bool(positive and negative)
    return {
        "n": n,
        "positive": positive,
        "negative": negative,
        "prevalence": _ratio(positive, n),
        "accuracy": _ratio(tp + tn, n),
        "balanced_accuracy": float((tp / positive + tn / negative) / 2) if both_classes else None,
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, positive),
        "f1": _ratio(2 * tp, 2 * tp + fp + fn),
        "average_precision": float(average_precision_score(labels, values)) if both_classes else None,
        "roc_auc": float(roc_auc_score(labels, values)) if both_classes else None,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
    }


def _part_id(value) -> int | str:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bool):
        raise ValueError("Boolean group IDs are not specimen identifiers")
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        return value
    raise ValueError("Group IDs must be finite whole numbers or nonempty strings")


def per_group_metrics(y_true, scores, groups, threshold=0.5) -> list[dict]:
    """Return ``[{part_id: native_id, ...binary_metrics}, ...]``.

    Integer IDs sort numerically, followed by string IDs in lexical order.
    Empty input returns an empty list. Missing/nonintegral group identifiers
    are rejected rather than silently omitting rows from specimen metrics.
    """
    labels, values, cutoff = _inputs(y_true, scores, threshold)
    group_array = np.asarray(groups, dtype=object)
    if group_array.ndim != 1 or len(group_array) != len(labels):
        raise ValueError("Groups must be one-dimensional and match the label length")
    indices = {}
    for index, value in enumerate(group_array):
        ident = _part_id(value)
        indices.setdefault(ident, []).append(index)
    order = sorted(indices, key=lambda ident: (0, ident) if isinstance(ident, int) else (1, ident))
    return [{"part_id": ident, **binary_metrics(labels[indices[ident]], values[indices[ident]], cutoff)}
            for ident in order]
