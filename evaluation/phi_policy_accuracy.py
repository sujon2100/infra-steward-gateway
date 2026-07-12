"""
Confusion-matrix accuracy report for the PHI consent/purpose-of-use
policy, over the labeled cases in phi_policy_dataset.py. Same shape as
the RQ2 evaluation in the arXiv paper for the base gateway PolicyService:
positive class is "should be denied," metrics are precision, recall,
accuracy, and F1.

Run directly: PYTHONPATH=. python evaluation/phi_policy_accuracy.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.policy.service import PolicyService
from evaluation.phi_policy_dataset import PHIPolicyCase, build_dataset


@dataclass
class CaseResult:
    case: PHIPolicyCase
    actual_allowed: bool
    matched: bool


def run_dataset(cases: list[PHIPolicyCase]) -> list[CaseResult]:
    results = []
    for case in cases:
        service = PolicyService()
        if case.consent is not None:
            service.register_consent(case.consent)
        decision = service.evaluate_phi_exchange(case.request)
        results.append(
            CaseResult(
                case=case,
                actual_allowed=decision.allowed,
                matched=decision.allowed == case.expected_allowed,
            )
        )
    return results


def confusion_matrix(results: list[CaseResult]) -> dict[str, int]:
    tp = tn = fp = fn = 0
    for r in results:
        expected_violation = not r.case.expected_allowed
        predicted_violation = not r.actual_allowed
        if expected_violation and predicted_violation:
            tp += 1
        elif not expected_violation and not predicted_violation:
            tn += 1
        elif not expected_violation and predicted_violation:
            fp += 1
        else:
            fn += 1
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn}


def render_report(results: list[CaseResult]) -> str:
    cm = confusion_matrix(results)
    tp, tn, fp, fn = cm["tp"], cm["tn"], cm["fp"], cm["fn"]
    total = len(results)

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    accuracy = (tp + tn) / total if total else float("nan")
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else float("nan")

    by_group: dict[str, list[CaseResult]] = {}
    for r in results:
        by_group.setdefault(r.case.group, []).append(r)

    lines = [
        "# PHI policy accuracy evaluation",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        f"Cases: {total}",
        "",
        "## Confusion matrix",
        "",
        "Positive class: request should be denied (a policy violation).",
        "",
        f"- TP (violation, correctly denied): {tp}",
        f"- TN (compliant, correctly allowed): {tn}",
        f"- FP (compliant, wrongly denied): {fp}",
        f"- FN (violation, wrongly allowed): {fn}",
        "",
        f"Precision: {precision:.4f}",
        f"Recall: {recall:.4f}",
        f"Accuracy: {accuracy:.4f}",
        f"F1: {f1:.4f}",
        "",
        "## By case group",
        "",
    ]

    for group in ("TN", "TP", "edge", "adversarial"):
        group_results = by_group.get(group, [])
        mismatches = [r for r in group_results if not r.matched]
        lines.append(f"- {group}: {len(group_results)} cases, {len(mismatches)} mismatched")
        for r in mismatches:
            lines.append(
                f"  - MISMATCH {r.case.name}: expected allowed={r.case.expected_allowed}, "
                f"got allowed={r.actual_allowed} ({r.case.note})"
            )

    lines.append("")
    lines.append(
        "Caveat: expected labels were hand-derived from the same specification the "
        "implementation follows, by the same person who wrote the implementation. "
        "This checks implementation-against-spec conformance across a deliberately "
        "constructed case set; it is not independent third-party validation, and a "
        "deterministic rule engine scoring 100% here says nothing about how it would "
        "generalize to inputs outside this case set."
    )

    return "\n".join(lines)


if __name__ == "__main__":
    dataset = build_dataset()
    outcomes = run_dataset(dataset)
    report = render_report(outcomes)
    print(report)

    with open("evaluation/results/accuracy_report.md", "w") as f:
        f.write(report + "\n")
