"""
Integration tests (Step 14): import safety without optional deps, safe model
loader behavior, and precise failures for missing credentials/artifacts.
"""

import importlib
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- import safety (no groq/torch/transformers installed) ------------------
def test_detection_modules_import():
    for name in ("detection_utils", "provider_outcome", "model_loader", "eval_checks"):
        importlib.import_module(name)


def test_harness_imports_without_groq():
    assert "groq" not in sys.modules or sys.modules.get("groq") is None
    mod = importlib.import_module("test_harness")
    assert hasattr(mod, "run_harness")


def test_interactive_tester_imports_without_groq():
    mod = importlib.import_module("interactive_tester")
    assert hasattr(mod, "main")


# --- safe model loader (Operating Rules 8/9) -------------------------------
def test_manifest_marks_artifacts_untrusted():
    import model_loader

    manifest = model_loader.load_manifest()
    for name in ("classifier.pkl", "vectorizer.pkl"):
        assert manifest[name]["trusted"] is False


def test_loader_refuses_untrusted_artifact():
    import model_loader

    path = os.path.join(REPO, "experiments", "models", "classifier.pkl")
    with pytest.raises(model_loader.ModelIntegrityError):
        model_loader.load_trusted_artifact(path)


def test_loader_verifies_hash_without_deserializing():
    import model_loader

    path = os.path.join(REPO, "experiments", "models", "classifier.pkl")
    entry = model_loader.verify_artifact(path)  # hashing only, no pickle.load
    assert entry["actual_sha256"] == entry["sha256"]


def test_loader_rejects_path_traversal():
    import model_loader

    with pytest.raises(model_loader.ModelIntegrityError):
        model_loader.verify_artifact(os.path.join(REPO, "README.md"))


def test_loader_detects_tampering(tmp_path):
    import model_loader

    # A file inside models/ but not in the manifest (simulates an unknown blob).
    rogue = os.path.join(REPO, "experiments", "models", "artifact_manifest.json")
    with pytest.raises(model_loader.ModelIntegrityError):
        model_loader.verify_artifact(rogue)


# --- precise failures -------------------------------------------------------
def test_harness_requires_api_key(monkeypatch):
    import test_harness

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        test_harness.run_harness([{"prompt": "hi", "triggers": [], "probe": "x"}])


def test_ml_detector_train_fails_precisely_when_data_missing():
    # Training CSVs are absent (blocker B1). build_dataset must fail clearly.
    import ml_detector

    if os.path.exists(os.path.join(REPO, "datasets", "prompt_injection_500.csv")):
        pytest.skip("training data present; missing-data path not exercised")
    with pytest.raises(FileNotFoundError):
        ml_detector.load_synthetic_dataset()
