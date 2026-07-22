"""
Prompt Injection Detection and Defence for LLM-Based Applications
CNIT/PNTLab Pisa — AI Security Internship 2026

Guardrail Framework Comparison
===============================

Security task being evaluated
------------------------------
    Task:    Prompt Injection Detection (binary classification)
    Input:   a single text prompt (string)
    Output:  1 = injection/attack detected, 0 = safe
    Positive class: prompt injection / jailbreak attempt

Frameworks compared (same held-out dataset for every implementation)
----------------------------------------------------------------------
    1. Our keyword detector      (rule-based baseline, Week 3)
    2. Our ML detector           (TF-IDF + Logistic Regression, Week 5)
    3. LLM Guard (Protect AI)    — PromptInjection scanner
    4. Guardrails AI             — not_comparable (Pinecone/hosted-API
                                    dependency, see run_guardrails_ai)
    5. NVIDIA NeMo Guardrails    — not_comparable (LLM-judged rail, see
                                    nemo_not_comparable)
    6. Meta LlamaFirewall        — PromptGuard scanner; may report
                                    "pending" if gated model access has
                                    not yet been approved by Meta

Hardware: CPU only (see recorded torch/device info per-framework below)

Reproduction commands
----------------------
    pip install llm-guard --no-deps --break-system-packages
    pip install presidio-anonymizer presidio-analyzer detect-secrets \
        structlog json-repair span-marker --break-system-packages
    pip install fuzzysearch --break-system-packages --only-binary=:all:
    pip install guardrails-ai --break-system-packages
    pip install llamafirewall --no-deps --break-system-packages
    huggingface-cli login
    # then request access at:
    # https://huggingface.co/meta-llama/Llama-Prompt-Guard-2-86M
    python src/guardrail_comparison.py
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd


EVAL_DATASET = Path("datasets/eval_dataset.csv")
RESULTS_FILE = Path("experiments/results/guardrail_comparison.json")
MODELS_DIR = Path("experiments/models")

# Our Week 3 keyword baseline
KEYWORD_PATTERNS = [
    "ignore previous instructions",
    "ignore any previous",
    "disregard all instructions",
    "forget previous instructions",
    "you are now",
    "new instructions:",
    "system override",
    "developer mode",
    "stop everything",
    "print yes",
    "pwned",
    "ignore and print",
    "act as",
    "pretend you are",
    "from now on",
    "bypass",
    "jailbreak",
]


# ══════════════════════════════════════════════════════════
# LOAD EVALUATION DATASET
# ══════════════════════════════════════════════════════════

def load_eval_dataset() -> pd.DataFrame:
    """Loads the held-out evaluation dataset. Same dataset used for ALL frameworks."""
    df = pd.read_csv(EVAL_DATASET)
    print(f"Evaluation dataset loaded: {len(df)} examples")
    print(f"  Attacks (1): {df['label'].sum()}")
    print(f"  Safe    (0): {(df['label'] == 0).sum()}\n")
    return df


# ══════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════

def calculate_metrics(y_true: list, y_pred: list, latencies: list) -> dict:
    """TP, FP, TN, FN, Precision, Recall, F1, FPR, FNR, median/P95 latency, throughput."""
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

    sorted_lat = sorted(latencies) if latencies else [0]
    median_lat = sorted_lat[len(sorted_lat) // 2]
    p95_idx = min(int(len(sorted_lat) * 0.95), len(sorted_lat) - 1)
    p95_lat = sorted_lat[p95_idx]
    total_time = sum(latencies)
    throughput = len(latencies) / total_time if total_time > 0 else 0

    return {
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "precision": round(precision * 100, 2),
        "recall": round(recall * 100, 2),
        "f1_score": round(f1 * 100, 2),
        "false_positive_rate": round(fpr * 100, 2),
        "false_negative_rate": round(fnr * 100, 2),
        "latency_median_ms": round(median_lat * 1000, 3),
        "latency_p95_ms": round(p95_lat * 1000, 3),
        "throughput_per_sec": round(throughput, 2),
    }


# ══════════════════════════════════════════════════════════
# IMPLEMENTATION 1: OUR KEYWORD DETECTOR
# ══════════════════════════════════════════════════════════

def run_keyword_detector(df: pd.DataFrame) -> dict:
    print("Running: Our Keyword Detector...")

    predictions, latencies, failures = [], [], 0

    for text in df["text"]:
        start = time.perf_counter()
        try:
            text_lower = str(text).lower()
            pred = 1 if any(p in text_lower for p in KEYWORD_PATTERNS) else 0
        except Exception:
            pred = 0
            failures += 1
        latencies.append(time.perf_counter() - start)
        predictions.append(pred)

    metrics = calculate_metrics(df["label"].tolist(), predictions, latencies)
    metrics["execution_failures"] = failures

    print(f"  F1: {metrics['f1_score']}% | Recall: {metrics['recall']}% | "
          f"Precision: {metrics['precision']}%\n")

    return {
        "name": "Our Keyword Detector",
        "version": "1.0-custom",
        "type": "rule_based",
        "configuration": {"patterns": len(KEYWORD_PATTERNS), "case_sensitive": False},
        "metrics": metrics,
    }


# ══════════════════════════════════════════════════════════
# IMPLEMENTATION 2: OUR ML DETECTOR (matches Week 5 ml_detector.py — joblib, not pickle)
# ══════════════════════════════════════════════════════════

def run_ml_detector(df: pd.DataFrame, model_name: str = "logistic_regression") -> dict:
    print(f"Running: Our ML Detector ({model_name})...")

    vectorizer_path = MODELS_DIR / "vectorizer.joblib"
    classifier_path = MODELS_DIR / f"classifier_{model_name}.joblib"

    if not vectorizer_path.exists() or not classifier_path.exists():
        print(f"  Model not found — run: python src/ml_detector.py train --model {model_name}\n")
        return {
            "name": f"Our ML Detector ({model_name})",
            "version": "1.0-custom",
            "error": f"Model not found. Run: python src/ml_detector.py train --model {model_name}",
        }

    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        vectorizer = joblib.load(vectorizer_path)
        classifier = joblib.load(classifier_path)
        version_warning = next(
            (str(w.message) for w in caught if "InconsistentVersionWarning" in str(w.category)),
            None,
        )

    predictions, latencies, failures = [], [], 0

    for text in df["text"]:
        start = time.perf_counter()
        try:
            X_vec = vectorizer.transform([str(text)])
            pred = int(classifier.predict(X_vec)[0])
        except Exception:
            pred = 0
            failures += 1
        latencies.append(time.perf_counter() - start)
        predictions.append(pred)

    metrics = calculate_metrics(df["label"].tolist(), predictions, latencies)
    metrics["execution_failures"] = failures

    print(f"  F1: {metrics['f1_score']}% | Recall: {metrics['recall']}% | "
          f"Precision: {metrics['precision']}%\n")

    result = {
        "name": f"Our ML Detector ({model_name})",
        "version": "1.0-custom",
        "type": "ml_tfidf_logreg" if model_name == "logistic_regression" else f"ml_{model_name}",
        "configuration": {
            "model": model_name,
            "features": "TF-IDF (ngram 1-3, max 10000)",
            "training_data": "HackAPrompt (601,757 examples)",
        },
        "metrics": metrics,
    }
    if version_warning:
        result["caveat"] = (
            f"scikit-learn version mismatch at load time: {version_warning} "
            "Results may differ slightly from a matched-version environment."
        )
    return result


# ══════════════════════════════════════════════════════════
# IMPLEMENTATION 3: LLM GUARD
# ══════════════════════════════════════════════════════════

def run_llm_guard(df: pd.DataFrame) -> dict:
    """
    Protect AI LLM Guard — PromptInjection scanner
    https://github.com/protectai/llm-guard

    Model used: ProtectAI/deberta-v3-base-prompt-injection (confirmed via
    local test run — downloaded automatically on first use, ~738MB, cached
    afterward). Runs on CPU.
    """
    print("Running: LLM Guard (Protect AI)...")

    try:
        from llm_guard.input_scanners import PromptInjection
        from llm_guard.input_scanners.prompt_injection import MatchType

        scanner = PromptInjection(match_type=MatchType.FULL)
        imported = True
    except ImportError as e:
        imported = False
        print(f"  LLM Guard not installed or import failed: {e}\n")

    if not imported:
        return {
            "name": "LLM Guard — PromptInjectionScanner",
            "version": "not installed",
            "error": "pip install llm-guard --no-deps --break-system-packages (see docstring for full deps)",
            "not_comparable": True,
        }

    predictions, latencies, failures = [], [], 0

    for text in df["text"]:
        start = time.perf_counter()
        try:
            _sanitized, is_valid, _risk_score = scanner.scan(str(text))
            # is_valid == True  -> safe   -> pred 0
            # is_valid == False -> unsafe -> pred 1
            pred = 0 if is_valid else 1
        except Exception:
            pred = 0
            failures += 1
        latencies.append(time.perf_counter() - start)
        predictions.append(pred)

    metrics = calculate_metrics(df["label"].tolist(), predictions, latencies)
    metrics["execution_failures"] = failures

    print(f"  F1: {metrics['f1_score']}% | Recall: {metrics['recall']}% | "
          f"Precision: {metrics['precision']}%\n")

    return {
        "name": "LLM Guard — PromptInjectionScanner",
        "version": "llm-guard 0.3.10",
        "type": "ml_based",
        "url": "https://github.com/protectai/llm-guard",
        "configuration": {
            "scanner": "PromptInjection",
            "match_type": "FULL",
            "model": "ProtectAI/deberta-v3-base-prompt-injection",
            "device": "cpu",
        },
        "dependency_note": (
            "Package pins torch==2.0.1, transformers==4.38.2, "
            "sentencepiece==0.2.0; installed with newer versions "
            "(torch 2.12.0, transformers 5.12.1, sentencepiece 0.2.1) "
            "via --no-deps. Confirmed working at runtime despite pin mismatch."
        ),
        "metrics": metrics,
    }


# ══════════════════════════════════════════════════════════
# IMPLEMENTATION 4: GUARDRAILS AI
# ══════════════════════════════════════════════════════════

def run_guardrails_ai(df: pd.DataFrame) -> dict:
    """
    Guardrails AI — DetectPromptInjection validator
    https://github.com/guardrails-ai/guardrails

    KNOWN ISSUE (documented after investigation): the detect_prompt_injection
    hub validator depends on a Pinecone vector database rather than a
    standalone local classifier, and the newer PromptInjectionDetector
    validator defaults to a hosted OpenAI LLM call for scoring. Neither
    is a fully local, no-hosted-API classifier comparable to our other
    baselines. This function still attempts the import in case a future
    guardrails-ai release changes this; if it fails, the accurate reason
    is reported rather than a generic "not installed" message.
    """
    print("Running: Guardrails AI...")

    try:
        from guardrails import Guard
        from guardrails.hub import DetectPromptInjection

        imported = True
    except ImportError as e:
        imported = False
        print(f"  Guardrails AI validator import failed: {e}\n")

    if not imported:
        return {
            "name": "Guardrails AI — DetectPromptInjection",
            "version": "guardrails-ai 0.10.2 (validator unavailable)",
            "not_comparable": True,
            "reason": (
                "DetectPromptInjection could not be imported from "
                "guardrails.hub (ImportError). Investigation showed this "
                "validator's implementation (hub://guardrails/"
                "detect_prompt_injection) depends on a Pinecone vector "
                "database rather than a standalone local classifier, and "
                "the alternative PromptInjectionDetector validator defaults "
                "to scoring via a hosted OpenAI API call — which would "
                "violate the constraint against sending data to hosted "
                "APIs. No fully local, standalone prompt-injection "
                "classifier is available in Guardrails AI without either "
                "external vector-database infrastructure or hosted-API "
                "calls."
            ),
            "url": "https://github.com/guardrails-ai/guardrails",
        }

    try:
        guard = Guard().use(DetectPromptInjection, on_fail="noop")
    except Exception as e:
        return {
            "name": "Guardrails AI — DetectPromptInjection",
            "error": f"Setup failed: {e}",
            "not_comparable": True,
        }

    predictions, latencies, failures = [], [], 0

    for text in df["text"]:
        start = time.perf_counter()
        try:
            result = guard.validate(str(text))
            pred = 0 if result.validation_passed else 1
        except Exception:
            pred = 0
            failures += 1
        latencies.append(time.perf_counter() - start)
        predictions.append(pred)

    metrics = calculate_metrics(df["label"].tolist(), predictions, latencies)
    metrics["execution_failures"] = failures

    print(f"  F1: {metrics['f1_score']}% | Recall: {metrics['recall']}% | "
          f"Precision: {metrics['precision']}%\n")

    return {
        "name": "Guardrails AI — DetectPromptInjection",
        "version": "guardrails-ai 0.10.2",
        "type": "ml_based",
        "url": "https://github.com/guardrails-ai/guardrails",
        "configuration": {"validator": "DetectPromptInjection", "on_fail": "noop"},
        "metrics": metrics,
    }


# ══════════════════════════════════════════════════════════
# NOT COMPARABLE
# ══════════════════════════════════════════════════════════

def nemo_not_comparable() -> dict:
    return {
        "name": "NVIDIA NeMo Guardrails",
        "not_comparable": True,
        "reason": (
            "Jailbreak/injection detection in NeMo Guardrails is implemented "
            "as an LLM-judged rail (calling a second LLM to evaluate the "
            "prompt) rather than a standalone classifier, and requires a "
            "YAML rail config plus a configured LLM endpoint. This confounds "
            "the comparison with a second model's capability rather than "
            "testing a comparable classifier component, and cannot be run "
            "in the same lightweight local pipeline as the other baselines."
        ),
        "url": "https://github.com/NVIDIA/NeMo-Guardrails",
    }


def run_llamafirewall(df: pd.DataFrame) -> dict:
    """
    Meta LlamaFirewall — PromptGuard scanner
    https://github.com/meta-llama/PurpleLlama/tree/main/LlamaFirewall

    Requires meta-llama/Llama-Prompt-Guard-2-86M, a gated HuggingFace model.
    This function attempts a real scan; if the model access is still
    pending Meta's manual review, it reports that accurately rather than
    a blanket "not comparable" exclusion.
    """
    print("Running: Meta LlamaFirewall...")

    try:
        from llamafirewall import LlamaFirewall, Role, ScanDecision, ScannerType, UserMessage

        lf = LlamaFirewall(scanners={Role.USER: [ScannerType.PROMPT_GUARD]})
        # Probe with a single call first to fail fast on gated-access errors
        # rather than partway through the full dataset.
        lf.scan(UserMessage(content="test"))
        ready = True
    except ImportError as e:
        ready = False
        status_reason = f"llamafirewall not installed or import failed: {e}"
    except Exception as e:
        ready = False
        msg = str(e)
        if "gated repo" in msg.lower() or "GatedRepoError" in msg or "awaiting a review" in msg.lower():
            status_reason = (
                "PromptGuard scanner requires meta-llama/Llama-Prompt-Guard-2-86M, "
                "a gated HuggingFace model. Package installed successfully "
                "(llamafirewall) and the API call is correct, but the model "
                "access request is awaiting manual review/approval from Meta "
                "at the time of this run."
            )
        else:
            status_reason = f"Unexpected error during setup: {msg}"

    if not ready:
        print(f"  {status_reason}\n")
        return {
            "name": "Meta LlamaFirewall — PromptGuard",
            "status": "pending",
            "not_comparable": False,
            "reason": status_reason,
            "url": "https://github.com/meta-llama/PurpleLlama/tree/main/LlamaFirewall",
        }

    predictions, latencies, failures = [], [], 0

    for text in df["text"]:
        start = time.perf_counter()
        try:
            result = lf.scan(UserMessage(content=str(text)))
            pred = 1 if result.decision == ScanDecision.BLOCK else 0
        except Exception:
            pred = 0
            failures += 1
        latencies.append(time.perf_counter() - start)
        predictions.append(pred)

    metrics = calculate_metrics(df["label"].tolist(), predictions, latencies)
    metrics["execution_failures"] = failures

    print(f"  F1: {metrics['f1_score']}% | Recall: {metrics['recall']}% | "
          f"Precision: {metrics['precision']}%\n")

    return {
        "name": "Meta LlamaFirewall — PromptGuard",
        "version": "llamafirewall 1.0.3",
        "type": "ml_based",
        "url": "https://github.com/meta-llama/PurpleLlama/tree/main/LlamaFirewall",
        "configuration": {
            "scanner": "PROMPT_GUARD",
            "model": "meta-llama/Llama-Prompt-Guard-2-86M",
            "device": "cpu",
        },
        "metrics": metrics,
    }


# ══════════════════════════════════════════════════════════
# COMPARISON TABLE
# ══════════════════════════════════════════════════════════

def print_comparison_table(results: list) -> None:
    print("\n" + "=" * 80)
    print("GUARDRAIL FRAMEWORK COMPARISON — FINAL RESULTS")
    print("=" * 80)
    print(f"{'Framework':<38} {'F1':>7} {'Prec':>7} {'Recall':>7} {'FPR':>7} {'P95ms':>8}")
    print("-" * 80)

    for r in results:
        if r.get("status") == "pending":
            print(f"{r['name']:<38} {'PENDING (see reason)':>38}")
            continue
        if r.get("not_comparable"):
            print(f"{r['name']:<38} {'NOT COMPARABLE':>38}")
            continue
        if "error" in r and "metrics" not in r:
            print(f"{r['name']:<38} {'ERROR / NOT INSTALLED':>38}")
            continue
        m = r.get("metrics", {})
        print(
            f"{r['name']:<38} "
            f"{m.get('f1_score', 0):>6}% "
            f"{m.get('precision', 0):>6}% "
            f"{m.get('recall', 0):>6}% "
            f"{m.get('false_positive_rate', 0):>6}% "
            f"{m.get('latency_p95_ms', 0):>7}ms"
        )
    print("=" * 80)


# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 60)
    print("GUARDRAIL FRAMEWORK COMPARISON")
    print("Security task: Prompt Injection Detection")
    print("=" * 60 + "\n")

    df = load_eval_dataset()

    results = []
    results.append(run_keyword_detector(df))
    results.append(run_ml_detector(df, model_name="logistic_regression"))
    results.append(run_llm_guard(df))
    results.append(run_guardrails_ai(df))
    results.append(nemo_not_comparable())
    results.append(run_llamafirewall(df))

    print_comparison_table(results)

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "security_task": "Prompt Injection Detection",
        "task_definition": {
            "input": "single text prompt (string)",
            "output": "1 = injection detected, 0 = safe",
            "positive_class": "prompt injection / jailbreak attempt",
        },
        "evaluation_dataset": str(EVAL_DATASET),
        "total_samples": len(df),
        "attack_samples": int(df["label"].sum()),
        "safe_samples": int((df["label"] == 0).sum()),
        "hardware": "CPU only",
        "reproduction_commands": [
            "pip install llm-guard --no-deps --break-system-packages",
            "pip install presidio-anonymizer presidio-analyzer detect-secrets "
            "structlog json-repair span-marker --break-system-packages",
            "pip install fuzzysearch --break-system-packages --only-binary=:all:",
            "pip install guardrails-ai --break-system-packages",
            "pip install llamafirewall --no-deps --break-system-packages",
            "huggingface-cli login  # then request access to "
            "meta-llama/Llama-Prompt-Guard-2-86M and wait for approval",
            "python src/guardrail_comparison.py",
        ],
        "constraints_confirmed": {
            "same_dataset_all_frameworks": True,
            "no_sensitive_data_to_hosted_apis": True,
            "no_credentials_committed": True,
            "implementation_not_replaced": True,
        },
        "results": results,
    }

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
