"""
RANA model API — the reproducible prompt-injection classifier (audit B1/B2 fix).

The RANA model is trained by ``scripts/train_rana.py`` on a current (2026),
apache-2.0 public dataset (see ``datasets/rana_train.provenance.json``), with a
mandatory leakage check against the held-out ``eval_dataset_v2.csv``. Its
artifacts are gitignored and regenerable; their SHA-256 + producer versions are
recorded in ``experiments/models/artifact_manifest.json`` (``trusted: true``).

Loading is integrity-gated (hash + trust via ``model_loader``) and FAILS CLOSED
on a scikit-learn version mismatch, so a stale/incompatible artifact can never
silently produce invalid scores.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from sklearn.exceptions import InconsistentVersionWarning

from model_loader import ModelIntegrityError, verify_artifact

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "experiments" / "models"
RANA_VEC_PATH = MODELS_DIR / "rana_vectorizer.joblib"
RANA_CLF_PATH = MODELS_DIR / "rana_classifier.joblib"


def is_available() -> bool:
    """True if both RANA artifacts exist locally (they are gitignored)."""
    return RANA_VEC_PATH.exists() and RANA_CLF_PATH.exists()


def _load_joblib_checked(path: Path) -> Any:
    entry = verify_artifact(path)  # path + SHA-256 vs manifest
    if not entry.get("trusted", False):
        raise ModelIntegrityError(f"Artifact '{path.name}' is not marked trusted.")
    import joblib  # local import; joblib ships with scikit-learn

    with warnings.catch_warnings():
        warnings.simplefilter("error", InconsistentVersionWarning)
        try:
            return joblib.load(path)
        except InconsistentVersionWarning as exc:
            raise RuntimeError(
                f"Refusing to use '{path.name}': built with a different "
                f"scikit-learn version ({exc}). Regenerate with "
                f"`python scripts/fetch_data.py && python scripts/train_rana.py`."
            ) from exc


def load() -> tuple[Any, Any]:
    """Return ``(vectorizer, classifier)`` after integrity + version checks."""
    if not is_available():
        raise FileNotFoundError(
            "RANA model artifacts not found. Build them with "
            "`python scripts/fetch_data.py && python scripts/train_rana.py`."
        )
    return _load_joblib_checked(RANA_VEC_PATH), _load_joblib_checked(RANA_CLF_PATH)


def predict_proba(texts: list[str]) -> list[float]:
    """Return per-text attack probability in [0, 1]."""
    vectorizer, classifier = load()
    matrix = vectorizer.transform(texts)
    return [float(p) for p in classifier.predict_proba(matrix)[:, 1]]
