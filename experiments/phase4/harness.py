"""
Victim/attacker separation harness for Phase 4.

Design principle: ground truth and attacker-observable state are
structurally separate objects. Attacker-side code should only ever
receive an AttackerObservation, never a GroundTruth instance.
"""
import requests, time
from dataclasses import dataclass, field

URL = "http://localhost:8000/v1/completions"
MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"


@dataclass
class GroundTruth:
    """Only accessible to the experimenter for post-hoc evaluation.
    Never pass this object into attacker-side functions."""
    secret: str
    category: str
    template: str

    def full_prompt(self) -> str:
        return self.template.format(secret=self.secret)


@dataclass
class AttackerObservation:
    """What the attacker is allowed to see: a candidate it chose, and
    the timing result of probing that candidate. No secret field exists
    here by construction."""
    candidate: str
    latency_ms: float
    trial_index: int


def _timed_request(prompt: str, max_tokens: int = 1) -> float:
    payload = {"model": MODEL, "prompt": prompt, "max_tokens": max_tokens, "temperature": 0}
    t0 = time.perf_counter()
    r = requests.post(URL, json=payload)
    r.raise_for_status()
    return (time.perf_counter() - t0) * 1000  # ms


def victim_populate_cache(gt: GroundTruth) -> None:
    """Victim tenant sends its real secret-containing prompt, populating
    the shared prefix cache. This is the only function that touches
    GroundTruth.secret directly."""
    _timed_request(gt.full_prompt())


def attacker_probe(template: str, candidate: str, trial_index: int = 0) -> AttackerObservation:
    """Attacker probes with a guess. Only takes a candidate string it
    generated itself - never receives GroundTruth."""
    prompt = template.format(secret=candidate)
    latency = _timed_request(prompt)
    return AttackerObservation(candidate=candidate, latency_ms=latency, trial_index=trial_index)
