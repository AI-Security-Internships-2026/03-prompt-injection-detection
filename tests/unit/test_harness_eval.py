"""
Offline unit tests for harness evaluation-validity helpers (Step 11).

These exercise the pure sampling/summary logic without Groq or network.
"""

from test_harness import stratified_sample, summarize_outcomes


def _attacks():
    out = []
    for probe, n in [("A", 10), ("B", 6), ("C", 4)]:
        out += [{"prompt": f"{probe}{i}", "triggers": [], "probe": probe} for i in range(n)]
    return out


def test_stratified_sample_is_deterministic():
    a = _attacks()
    assert [x["prompt"] for x in stratified_sample(a, 6, seed=1)] == [
        x["prompt"] for x in stratified_sample(a, 6, seed=1)
    ]


def test_stratified_sample_covers_all_probes():
    a = _attacks()
    sample = stratified_sample(a, 6, seed=1)
    probes = {x["probe"] for x in sample}
    assert probes == {"A", "B", "C"}  # every family represented, not first-N


def test_stratified_sample_not_first_n():
    a = _attacks()
    sample = stratified_sample(a, 6, seed=1)
    assert [x["prompt"] for x in sample] != [x["prompt"] for x in a[:6]]


def test_stratified_sample_respects_cap():
    a = _attacks()
    assert len(stratified_sample(a, 5, seed=1)) == 5
    assert len(stratified_sample(a, 0, seed=1)) == len(a)  # 0 => all
    assert len(stratified_sample(a, 999, seed=1)) == len(a)


def test_summarize_excludes_refusals_from_denominator():
    records = [
        {"local_decision": "block", "provider_outcome": "completed", "attack_succeeded": True},
        {"local_decision": "review", "provider_outcome": "completed", "attack_succeeded": False},
        {"local_decision": "allow", "provider_outcome": "refusal", "attack_succeeded": False},
        {"local_decision": "allow", "provider_outcome": "error", "attack_succeeded": False},
    ]
    s = summarize_outcomes(records)
    c, m = s["counts"], s["metrics"]
    assert c["provider_refused"] == 1
    assert c["provider_error"] == 1
    assert c["excluded_from_metrics"] == 2
    # Denominator is provider_completed (2), not total (4).
    assert m["attack_success_rate_evaluable"] == 0.5
    assert c["locally_blocked"] == 1
    assert c["locally_reviewed"] == 1


def test_summarize_defines_every_metric():
    s = summarize_outcomes(
        [{"local_decision": "allow", "provider_outcome": "completed", "attack_succeeded": False}]
    )
    assert set(s["metrics"]) <= set(s["metric_definitions"]) | {"provider_refusal_rate"}
    for key in s["metrics"]:
        assert key in s["metric_definitions"]
