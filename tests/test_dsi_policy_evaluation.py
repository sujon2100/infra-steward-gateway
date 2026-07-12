from evaluation.dsi_policy_accuracy import confusion_matrix, run_dataset
from evaluation.dsi_policy_dataset import build_dataset


def test_dsi_policy_matches_labeled_dataset_with_no_false_positives_or_negatives() -> None:
    results = run_dataset(build_dataset())
    mismatches = [r for r in results if not r.matched]

    assert mismatches == []

    cm = confusion_matrix(results)
    assert cm["fp"] == 0
    assert cm["fn"] == 0
