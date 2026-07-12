"""
Latency overhead of the PHI consent/purpose-of-use check, benchmarked the
same way as RQ1 in the arXiv paper: per-call wall-clock timing across
configurations, Kruskal-Wallis to check whether the groups differ at all,
then pairwise Mann-Whitney U with a Bonferroni-adjusted alpha.

Three configurations:
  - baseline: PolicyService.evaluate() (the existing banking policy check)
  - phi_allow: evaluate_phi_exchange() on a request that clears every rule
  - phi_deny: evaluate_phi_exchange() on a request that fails on the first
    rule (unknown consent_id), i.e. the cheapest possible PHI call

This is a single-process microbenchmark on a dev laptop, not a load test
against the deployed gateway. GC pauses and OS scheduling noise are part
of the measured signal, not filtered out — the median and IQR reported
below are more meaningful than the raw mean for that reason.

Run directly: PYTHONPATH=. python evaluation/phi_policy_latency.py
"""

from __future__ import annotations

import time

import numpy as np
from scipy import stats

from app.policy.models import ConsentRecord, PHIExchangeRequest
from app.policy.service import PolicyService

ITERATIONS = 3000
WARMUP = 200


def _baseline_call(service: PolicyService) -> None:
    service.evaluate(tenant_id="bank_alpha", scenario="reporting", report_type="standard", jurisdiction="EU")


def _phi_allow_call(service: PolicyService, request: PHIExchangeRequest) -> None:
    service.evaluate_phi_exchange(request)


def _phi_deny_call(service: PolicyService, request: PHIExchangeRequest) -> None:
    service.evaluate_phi_exchange(request)


def _time_calls(fn, iterations: int) -> np.ndarray:
    samples = np.empty(iterations, dtype=np.float64)
    for i in range(iterations):
        start = time.perf_counter()
        fn()
        samples[i] = time.perf_counter() - start
    return samples * 1e6  # microseconds


def run_benchmark() -> dict[str, np.ndarray]:
    service = PolicyService()
    service.register_consent(
        ConsentRecord(
            consent_id="bench-consent",
            patient_id="bench-patient",
            granted_categories={"diagnosis"},
            granted_purposes={"treatment"},
            authorized_recipients={"hie_hospital_north"},
        )
    )
    allow_request = PHIExchangeRequest(
        consent_id="bench-consent",
        patient_id="bench-patient",
        disclosing_org="hie_clinic_riverside",
        receiving_org="hie_hospital_north",
        categories={"diagnosis"},
        purpose_of_use="treatment",
    )
    deny_request = PHIExchangeRequest(
        consent_id="does-not-exist",
        patient_id="bench-patient",
        disclosing_org="hie_clinic_riverside",
        receiving_org="hie_hospital_north",
        categories={"diagnosis"},
        purpose_of_use="treatment",
    )

    for _ in range(WARMUP):
        _baseline_call(service)
        _phi_allow_call(service, allow_request)
        _phi_deny_call(service, deny_request)

    return {
        "baseline": _time_calls(lambda: _baseline_call(service), ITERATIONS),
        "phi_allow": _time_calls(lambda: _phi_allow_call(service, allow_request), ITERATIONS),
        "phi_deny": _time_calls(lambda: _phi_deny_call(service, deny_request), ITERATIONS),
    }


def render_report(samples: dict[str, np.ndarray]) -> str:
    lines = [
        "# PHI policy latency benchmark",
        "",
        f"Iterations per configuration: {ITERATIONS} (after {WARMUP} warmup calls, discarded)",
        "",
        "## Per-configuration summary (microseconds)",
        "",
    ]

    for name, arr in samples.items():
        lines.append(
            f"- {name}: median={np.median(arr):.2f}us, "
            f"IQR=[{np.percentile(arr, 25):.2f}, {np.percentile(arr, 75):.2f}], "
            f"mean={arr.mean():.2f}us, stdev={arr.std():.2f}us"
        )

    h_stat, p_value = stats.kruskal(*samples.values())
    lines += [
        "",
        "## Kruskal-Wallis across all three configurations",
        "",
        f"H = {h_stat:.4f}, p = {p_value:.6g}",
        "",
        "## Pairwise Mann-Whitney U (Bonferroni-adjusted alpha = 0.05 / 3 = 0.0167)",
        "",
    ]

    pairs = [
        ("baseline", "phi_allow"),
        ("baseline", "phi_deny"),
        ("phi_allow", "phi_deny"),
    ]
    alpha = 0.05 / len(pairs)
    for a, b in pairs:
        u_stat, p = stats.mannwhitneyu(samples[a], samples[b], alternative="two-sided")
        significant = "significant" if p < alpha else "not significant"
        median_delta = np.median(samples[b]) - np.median(samples[a])
        lines.append(
            f"- {a} vs {b}: U = {u_stat:.1f}, p = {p:.6g} ({significant}), "
            f"median delta = {median_delta:+.2f}us"
        )

    lines += [
        "",
        "Caveat: single-process microbenchmark, no concurrent load, run on a "
        "dev laptop rather than the deployed gateway. Absolute microsecond "
        "figures will not transfer to production hardware; the comparison "
        "between configurations on the same run is the useful signal.",
    ]

    return "\n".join(lines)


if __name__ == "__main__":
    results = run_benchmark()
    report = render_report(results)
    print(report)

    with open("evaluation/results/latency_report.md", "w") as f:
        f.write(report + "\n")
