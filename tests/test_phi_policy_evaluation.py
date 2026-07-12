"""
Regression guard tying the accuracy evaluation dataset into the normal
test run — if a future change to PolicyService breaks conformance with
the labeled cases, this fails here rather than only showing up next time
someone happens to rerun evaluation/phi_policy_accuracy.py by hand.
"""

from evaluation.phi_policy_accuracy import confusion_matrix, run_dataset
from evaluation.phi_policy_dataset import build_dataset


def test_phi_policy_matches_labeled_dataset_with_no_false_positives_or_negatives() -> None:
    results = run_dataset(build_dataset())
    mismatches = [r for r in results if not r.matched]

    assert mismatches == []

    cm = confusion_matrix(results)
    assert cm["fp"] == 0
    assert cm["fn"] == 0
