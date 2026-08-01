"""
Safe, provenance-checked loading of serialized model artifacts
(Operating Rules 8 & 9; audit security §8).

``pickle.load`` (and ``joblib.load`` — it has the **same** executable-
deserialization trust problem) will execute arbitrary code embedded in a
crafted artifact. This module refuses to deserialize any file unless:

  1. the path resolves *inside* the repository's models directory
     (no arbitrary user-supplied path traversal);
  2. the file's SHA-256 matches an entry in the signed manifest; and
  3. that manifest entry is explicitly marked ``"trusted": true``.

The committed artifacts are recorded in the manifest as ``trusted: false``
until their provenance is established, so loading them fails closed. This lets
callers verify integrity/provenance without ever deserializing an untrusted
blob.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = (BASE_DIR / "experiments" / "models").resolve()
MANIFEST_PATH = MODELS_DIR / "artifact_manifest.json"


class ModelIntegrityError(Exception):
    """Raised when an artifact fails path, hash, or trust verification."""


def sha256_of(path: str | Path) -> str:
    """Return the SHA-256 of a file, reading it in chunks (no deserialization)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise ModelIntegrityError(
            f"Artifact manifest not found: {MANIFEST_PATH}. "
            "Refusing to load any model without a provenance manifest."
        )
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


def _resolve_inside_models_dir(path: str | Path) -> Path:
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(MODELS_DIR)
    except ValueError as exc:
        raise ModelIntegrityError(
            f"Refusing to load artifact outside the models directory: {resolved}"
        ) from exc
    return resolved


def verify_artifact(path: str | Path) -> dict[str, Any]:
    """Verify path containment, hash, and trust WITHOUT deserializing.

    Returns the manifest entry on success; raises :class:`ModelIntegrityError`
    otherwise. Safe to call on untrusted files — it only hashes bytes.
    """
    resolved = _resolve_inside_models_dir(path)
    if not resolved.exists():
        raise ModelIntegrityError(f"Artifact does not exist: {resolved}")

    manifest = load_manifest()
    name = resolved.name
    entry = manifest.get(name)
    if entry is None:
        raise ModelIntegrityError(f"No manifest entry for artifact '{name}'.")

    actual = sha256_of(resolved)
    expected = entry.get("sha256")
    if expected in (None, "", "unknown"):
        raise ModelIntegrityError(f"Manifest has no recorded SHA-256 for '{name}'; cannot verify.")
    if actual.lower() != str(expected).lower():
        raise ModelIntegrityError(
            f"SHA-256 mismatch for '{name}': manifest={expected} actual={actual}."
        )

    entry = {**entry, "actual_sha256": actual}
    return entry


def load_trusted_artifact(path: str | Path) -> Any:
    """Deserialize an artifact ONLY after full verification and trust=true.

    Fails closed for the currently-committed artifacts (trust=false), so this
    never deserializes an unverified blob.
    """
    entry = verify_artifact(path)
    if not entry.get("trusted", False):
        raise ModelIntegrityError(
            f"Artifact '{Path(path).name}' is verified by hash but marked "
            "trusted=false in the manifest. Establish provenance and set "
            "trusted=true before loading. Refusing to deserialize."
        )
    # Verified path + hash + explicit trust flag. pickle is still executable
    # deserialization, hence the layered gate above.
    # deserialization is gated by the path+hash+trust checks above
    import pickle  # nosec B403

    with open(_resolve_inside_models_dir(path), "rb") as f:
        return pickle.load(f)  # nosec B301 - gated by path+hash+trust verification
