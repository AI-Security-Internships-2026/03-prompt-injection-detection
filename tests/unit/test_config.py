"""
Dependency-metadata consistency (audit C1, Steps 3-4).

Replaces the old "all deps pinned in requirements.txt" assertion with checks
that the authoritative pyproject.toml declares the tested Python range and that
the generated constraints lock is fully pinned.
"""

import os
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pyproject():
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        return tomllib.load(f)


def test_requires_python_targets_314():
    data = _pyproject()
    assert data["project"]["requires-python"] == ">=3.14,<3.15"


def test_core_deps_declared():
    deps = _pyproject()["project"]["dependencies"]
    names = " ".join(deps).lower()
    for pkg in ("numpy", "pandas", "scikit-learn"):
        assert pkg in names


def test_optional_groups_separate_heavy_deps():
    extras = _pyproject()["project"]["optional-dependencies"]
    assert "groq" in " ".join(extras["llm"]).lower()
    assert "torch" in " ".join(extras["comparison"]).lower()
    assert "garak" in " ".join(extras["garak"]).lower()
    # Heavy provider/comparison deps must NOT be in core.
    core = " ".join(_pyproject()["project"]["dependencies"]).lower()
    for heavy in ("torch", "transformers", "groq", "garak"):
        assert heavy not in core


def test_no_stray_requirements_txt():
    # A leftover requirements.txt would reintroduce a conflicting source.
    assert not os.path.exists(os.path.join(ROOT, "requirements.txt"))
    assert not os.path.exists(os.path.join(ROOT, "requirements-dev.txt"))


def test_constraints_lock_fully_pinned():
    lock = os.path.join(ROOT, "requirements", "constraints-python314.txt")
    assert os.path.exists(lock)
    with open(lock, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    assert lines, "constraints lock is empty"
    unpinned = [ln for ln in lines if "==" not in ln]
    assert not unpinned, f"unpinned lines in constraints lock: {unpinned}"
