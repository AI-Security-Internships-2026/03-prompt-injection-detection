"""
Shared timing measurement and hit/miss classification for Phase 4.
Threshold is calibrated per-template via a baseline miss measurement,
since Phase 2/3 showed the hit/miss latency gap depends heavily on
template/prefix length (short templates: ~3ms gap; long templates:
~800ms gap). A single global threshold does not generalize across
template shapes - this was discovered empirically while testing this
module (see git history) rather than assumed in advance.
"""
import statistics, uuid
from experiments.phase4.harness import attacker_probe, AttackerObservation


def calibrate_threshold(template: str, placeholder_candidate: str, n_baseline: int = 10) -> dict:
    """Measure baseline miss latency using a guaranteed-uncached candidate
    that matches the LENGTH/SHAPE of real candidates for this experiment,
    not an arbitrary format - length mismatches here previously caused a
    confound (see git history) where longer baseline candidates produced
    inflated 'miss' latencies unrelated to actual cache status."""
    baseline_latencies = []
    for _ in range(n_baseline):
        obs = attacker_probe(template, placeholder_candidate, trial_index=0)
        baseline_latencies.append(obs.latency_ms)

    mean_miss = statistics.mean(baseline_latencies)
    stdev_miss = statistics.stdev(baseline_latencies) if len(baseline_latencies) > 1 else 0.0

    return {
        "mean_miss_ms": mean_miss,
        "stdev_miss_ms": stdev_miss,
        "threshold_ms": mean_miss - stdev_miss,
    }
def classify_with_confidence(template: str, candidate: str, threshold_ms: float, n_trials: int = 5) -> dict:
    """Probe the same candidate n_trials times, majority-vote hit/miss
    against a pre-calibrated threshold, report confidence."""
    observations: list[AttackerObservation] = [
        attacker_probe(template, candidate, trial_index=i) for i in range(n_trials)
    ]
    latencies = [obs.latency_ms for obs in observations]
    hits = sum(1 for l in latencies if l < threshold_ms)
    confidence = hits / n_trials
    prediction = "hit" if confidence > 0.5 else "miss"

    return {
        "candidate": candidate,
        "prediction": prediction,
        "confidence": confidence,
        "mean_latency_ms": statistics.mean(latencies),
        "stdev_latency_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
        "raw_latencies_ms": latencies,
        "n_trials": n_trials,
        "threshold_used_ms": threshold_ms,
    }
