"""
Ground-truth secret generators for Phase 4, across four entropy categories.
Each function returns a harness.GroundTruth instance.
"""
import random
import string
import uuid
from experiments.phase4.harness import GroundTruth

TEMPLATE = "System context: the confidential value is {secret}. Respond only with OK."


def low_entropy_secret() -> GroundTruth:
    """Small, common-word alphabet. Large timing gaps expected - easy case."""
    secret = random.choice(["yes", "no", "ok", "true", "false"])
    return GroundTruth(secret=secret, category="low_entropy", template=TEMPLATE)


def structured_secret() -> GroundTruth:
    """Fixed-format, small alphabet - e.g. a 6-digit PIN."""
    secret = "".join(random.choice(string.digits) for _ in range(6))
    return GroundTruth(secret=secret, category="structured", template=TEMPLATE)


def predictable_prefix_secret() -> GroundTruth:
    """Known prefix + small variable suffix - e.g. an API-key-like format."""
    suffix = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    secret = f"SK-{suffix}"
    return GroundTruth(secret=secret, category="predictable_prefix", template=TEMPLATE)


def high_entropy_secret() -> GroundTruth:
    """Full random hex string - the hard/likely-infeasible case."""
    secret = uuid.uuid4().hex
    return GroundTruth(secret=secret, category="high_entropy", template=TEMPLATE)


SECRET_GENERATORS = {
    "low_entropy": low_entropy_secret,
    "structured": structured_secret,
    "predictable_prefix": predictable_prefix_secret,
    "high_entropy": high_entropy_secret,
}
