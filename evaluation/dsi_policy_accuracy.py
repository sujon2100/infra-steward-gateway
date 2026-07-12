"""
Confusion-matrix accuracy report for the DSI transparency policy, same
shape as evaluation/phi_policy_accuracy.py: positive class is "should be
blocked," metrics are precision, recall, accuracy, and F1.

Run directly: PYTHONPATH=. python evaluation/dsi_policy_accuracy.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.policy.service import PolicyService
from evaluation.dsi_policy_dataset import DSIPolicyCase, build_dataset


@dataclass
class CaseResult:
    case: DSIPolicyCase
    actual_allowed: bool
    matched: bool


def run_dataset(cases: list[DSIPolicyCase]) -> list[CaseResult]:
    results = []
    for case in cases:
        service = PolicyService()
        if case.attrs is not None:
            service.register_dsi(case.attrs)
        decision = service.evaluate_dsi_output(case.request)
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
        expected_block = not r.case.expected_allowed
        predicted_block = not r.actual_allowed
        if expected_block and predicted_block:
            tp += 1
        elif not expected_block and not predicted_block:
            tn += 1
        elif not expected_block and predicted_block:
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
        "# DSI transparency policy accuracy evaluation",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        f"Cases: {total}",
        "",
        "## Confusion matrix",
        "",
        "Positive class: output should be blocked (a required HTI-1 category 1-3 "
        "attribute missing, or the dsi_id isn't registered at all).",
        "",
        f"- TP (violation, correctly blocked): {tp}",
        f"- TN (complete registration, correctly allowed): {tn}",
        f"- FP (complete registration, wrongly blocked): {fp}",
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
        "constructed case set, not independent third-party validation. It also only "
        "checks whether the required transparency attributes are present and recorded "
        "- it says nothing about whether the underlying model for a given dsi_id is "
        "actually accurate, fair, or clinically safe."
    )

    return "\n".join(lines)


if __name__ == "__main__":
    dataset = build_dataset()
    outcomes = run_dataset(dataset)
    report = render_report(outcomes)
    print(report)

    with open("evaluation/results/dsi_accuracy_report.md", "w") as f:
        f.write(report + "\n")
