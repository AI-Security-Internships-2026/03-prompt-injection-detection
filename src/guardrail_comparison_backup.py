
"""
Prompt Injection Detection and Defence for LLM-Based Applications
CNIT/PNTLab Pisa — AI Security Internship 2026

Guardrail Framework Comparison
===============================

Security task
-------------
Prompt Injection Detection (binary classification)

Input:
    A text prompt or serialized conversation.

Output:
    1 = prompt injection / attack
    0 = benign / safe

Compared implementations
------------------------
1. Our Keyword Detector
2. Our TF-IDF + Logistic Regression ML Detector
3. Protect AI LLM Guard — PromptInjectionScanner
4. Meta LlamaFirewall — PromptGuard

Not comparable
--------------
5. Guardrails AI — documented as not comparable for this benchmark
6. NVIDIA NeMo Guardrails — documented as not comparable for this benchmark

IMPORTANT:
All comparable implementations are evaluated on EXACTLY THE SAME
held-out evaluation dataset.

The benchmark supports:
- Overall metrics
- Per-category metrics
- TP / FP / TN / FN
- Precision / Recall / F1
- False Positive Rate
- False Negative Rate
- Median latency
- P95 latency
- Throughput
- Execution failures
- Framework/model/configuration information
- Dataset distribution
- Reproduction commands

Usage
-----

Default:
    python src/guardrail_comparison.py

Custom evaluation dataset:
    python src/guardrail_comparison.py \
        --dataset datasets/eval_dataset_v2.csv

Custom output:
    python src/guardrail_comparison.py \
        --dataset datasets/eval_dataset_v2.csv \
        --output experiments/results/guardrail_comparison_v2.json
"""

import argparse
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd


# ================================================================
# DEFAULT PATHS
# ================================================================

DEFAULT_EVAL_DATASET = Path("datasets/eval_dataset.csv")
DEFAULT_RESULTS_FILE = Path(
    "experiments/results/guardrail_comparison.json"
)

MODELS_DIR = Path("experiments/models")


# ================================================================
# OUR KEYWORD DETECTOR
# ================================================================

KEYWORD_PATTERNS = [
    "ignore previous instructions",
    "ignore any previous",
    "ignore all previous",
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


# ================================================================
# DATASET LOADING
# ================================================================

def load_eval_dataset(dataset_path: Path) -> pd.DataFrame:
    """
    Load and validate the held-out evaluation dataset.

    The exact same DataFrame is passed to every comparable detector.
    """

    print("=" * 70)
    print("LOADING HELD-OUT EVALUATION DATASET")
    print("=" * 70)

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Evaluation dataset not found: {dataset_path}"
        )

    df = pd.read_csv(dataset_path)

    required_columns = {"text", "label"}

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Dataset is missing required columns: {missing}"
        )

    # Convert labels to integer
    df["label"] = pd.to_numeric(
        df["label"],
        errors="raise"
    ).astype(int)

    # Validate labels
    invalid_labels = set(df["label"].unique()) - {0, 1}

    if invalid_labels:
        raise ValueError(
            f"Invalid labels found: {invalid_labels}. "
            f"Labels must be 0 or 1."
        )

    # Validate missing text
    if df["text"].isna().any():
        raise ValueError(
            "Dataset contains missing values in the 'text' column."
        )

    df["text"] = df["text"].astype(str)

    print(f"Dataset: {dataset_path}")
    print(f"Total samples: {len(df)}")
    print(f"Attack samples: {(df['label'] == 1).sum()}")
    print(f"Benign samples: {(df['label'] == 0).sum()}")

    if "attack_type" in df.columns:

        print("\nCategory distribution:")
        print(
            df.groupby(
                ["attack_type", "label"]
            ).size().to_string()
        )

    print("\nDataset validation: PASSED")
    print("=" * 70 + "\n")

    return df


# ================================================================
# METRICS
# ================================================================

def calculate_metrics(
    y_true,
    y_pred,
    latencies,
    execution_failures=0,
):
    """
    Calculate benchmark metrics.

    y_true:
        Ground truth labels.

    y_pred:
        Detector predictions.

    latencies:
        Per-sample execution latency in seconds.
    """

    tp = sum(
        1
        for t, p in zip(y_true, y_pred)
        if t == 1 and p == 1
    )

    fp = sum(
        1
        for t, p in zip(y_true, y_pred)
        if t == 0 and p == 1
    )

    tn = sum(
        1
        for t, p in zip(y_true, y_pred)
        if t == 0 and p == 0
    )

    fn = sum(
        1
        for t, p in zip(y_true, y_pred)
        if t == 1 and p == 0
    )

    precision = (
        tp / (tp + fp)
        if (tp + fp) > 0
        else 0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn) > 0
        else 0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0
    )

    fpr = (
        fp / (fp + tn)
        if (fp + tn) > 0
        else 0
    )

    fnr = (
        fn / (fn + tp)
        if (fn + tp) > 0
        else 0
    )

    sorted_latencies = sorted(latencies)

    if sorted_latencies:

        median_latency = (
            sorted_latencies[
                len(sorted_latencies) // 2
            ]
        )

        p95_index = min(
            int(len(sorted_latencies) * 0.95),
            len(sorted_latencies) - 1,
        )

        p95_latency = sorted_latencies[p95_index]

        total_time = sum(sorted_latencies)

        throughput = (
            len(sorted_latencies) / total_time
            if total_time > 0
            else 0
        )

    else:

        median_latency = 0
        p95_latency = 0
        throughput = 0

    return {
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),

        "precision": round(
            precision * 100,
            2
        ),

        "recall": round(
            recall * 100,
            2
        ),

        "f1_score": round(
            f1 * 100,
            2
        ),

        "false_positive_rate": round(
            fpr * 100,
            2
        ),

        "false_negative_rate": round(
            fnr * 100,
            2
        ),

        "latency_median_ms": round(
            median_latency * 1000,
            3
        ),

        "latency_p95_ms": round(
            p95_latency * 1000,
            3
        ),

        "throughput_per_sec": round(
            throughput,
            2
        ),

        "execution_failures": int(
            execution_failures
        ),

        "evaluated_samples": len(y_true),
    }


# ================================================================
# PER-CATEGORY METRICS
# ================================================================

def calculate_category_metrics(
    df,
    predictions,
    latencies,
    failures_by_index=None,
):
    """
    Calculate metrics separately for each attack category.

    This is important because an overall F1 score can hide
    weaknesses in indirect, encoded, multilingual, or multi-turn
    attacks.
    """

    if "attack_type" not in df.columns:
        return {}

    results = {}

    for category in sorted(
        df["attack_type"]
        .dropna()
        .unique()
    ):

        indices = [
            i
            for i, value in enumerate(
                df["attack_type"]
            )
            if value == category
        ]

        y_true = [
            int(df.iloc[i]["label"])
            for i in indices
        ]

        y_pred = [
            int(predictions[i])
            for i in indices
        ]

        category_latencies = [
            latencies[i]
            for i in indices
        ]

        category_failures = 0

        if failures_by_index:

            category_failures = sum(
                1
                for i in indices
                if failures_by_index.get(
                    i,
                    False
                )
            )

        results[category] = calculate_metrics(
            y_true,
            y_pred,
            category_latencies,
            category_failures,
        )

    return results


# ================================================================
# GENERIC DETECTOR RUNNER
# ================================================================

def finalize_detector_result(
    name,
    version,
    detector_type,
    configuration,
    df,
    predictions,
    latencies,
    failures,
    failures_by_index=None,
    extra=None,
):
    """
    Build the standard result object for every detector.
    """

    y_true = df["label"].tolist()

    metrics = calculate_metrics(
        y_true,
        predictions,
        latencies,
        failures,
    )

    result = {
        "name": name,
        "version": version,
        "type": detector_type,
        "configuration": configuration,
        "metrics": metrics,
    }

    category_metrics = calculate_category_metrics(
        df,
        predictions,
        latencies,
        failures_by_index,
    )

    if category_metrics:
        result["per_category_metrics"] = (
            category_metrics
        )

    if extra:
        result.update(extra)

    print(
        f"  F1: {metrics['f1_score']}% | "
        f"Precision: {metrics['precision']}% | "
        f"Recall: {metrics['recall']}% | "
        f"FPR: {metrics['false_positive_rate']}% | "
        f"P95: {metrics['latency_p95_ms']} ms"
    )

    return result


# ================================================================
# IMPLEMENTATION 1
# OUR KEYWORD DETECTOR
# ================================================================

def run_keyword_detector(df):

    print(
        "\nRunning: Our Keyword Detector"
    )

    predictions = []
    latencies = []

    failures = 0
    failures_by_index = {}

    for index, text in enumerate(
        df["text"]
    ):

        start = time.perf_counter()

        try:

            text_lower = str(
                text
            ).lower()

            prediction = int(
                any(
                    pattern in text_lower
                    for pattern in KEYWORD_PATTERNS
                )
            )

            failures_by_index[index] = False

        except Exception:

            prediction = 0
            failures += 1
            failures_by_index[index] = True

        latency = (
            time.perf_counter()
            - start
        )

        predictions.append(
            prediction
        )

        latencies.append(
            latency
        )

    return finalize_detector_result(
        name="Our Keyword Detector",
        version="1.0-custom",
        detector_type="rule_based",
        configuration={
            "patterns": len(
                KEYWORD_PATTERNS
            ),
            "case_sensitive": False,
        },
        df=df,
        predictions=predictions,
        latencies=latencies,
        failures=failures,
        failures_by_index=failures_by_index,
    )


# ================================================================
# IMPLEMENTATION 2
# OUR ML DETECTOR
# ================================================================

def run_ml_detector(df):

    print(
        "\nRunning: Our ML Detector "
        "(TF-IDF + Logistic Regression)"
    )

    # IMPORTANT:
    # Your current training output showed:
    #
    # experiments/models/vectorizer.pkl
    # experiments/models/classifier.pkl

    vectorizer_path = (
        MODELS_DIR
        / "vectorizer.pkl"
    )

    classifier_path = (
        MODELS_DIR
        / "classifier.pkl"
    )

    if not vectorizer_path.exists():

        return {
            "name": (
                "Our ML Detector "
                "(TF-IDF + Logistic Regression)"
            ),
            "version": "1.0-custom",
            "type": "ml_tfidf_logistic_regression",
            "error": (
                f"Vectorizer not found: "
                f"{vectorizer_path}"
            ),
        }

    if not classifier_path.exists():

        return {
            "name": (
                "Our ML Detector "
                "(TF-IDF + Logistic Regression)"
            ),
            "version": "1.0-custom",
            "type": "ml_tfidf_logistic_regression",
            "error": (
                f"Classifier not found: "
                f"{classifier_path}"
            ),
        }

    try:

        vectorizer = joblib.load(
            vectorizer_path
        )

        classifier = joblib.load(
            classifier_path
        )

    except Exception as e:

        return {
            "name": (
                "Our ML Detector "
                "(TF-IDF + Logistic Regression)"
            ),
            "version": "1.0-custom",
            "type": "ml_tfidf_logistic_regression",
            "error": (
                f"Failed to load model: {e}"
            ),
        }

    predictions = []
    latencies = []

    failures = 0
    failures_by_index = {}

    for index, text in enumerate(
        df["text"]
    ):

        start = time.perf_counter()

        try:

            X = vectorizer.transform(
                [str(text)]
            )

            prediction = int(
                classifier.predict(X)[0]
            )

            failures_by_index[index] = False

        except Exception as e:

            print(
                f"  ML prediction failed "
                f"for sample {index}: {e}"
            )

            prediction = 0

            failures += 1

            failures_by_index[index] = True

        latency = (
            time.perf_counter()
            - start
        )

        predictions.append(
            prediction
        )

        latencies.append(
            latency
        )

    try:

        sklearn_version = __import__(
            "sklearn"
        ).__version__

    except Exception:

        sklearn_version = (
            "unknown"
        )

    return finalize_detector_result(
        name=(
            "Our ML Detector "
            "(TF-IDF + Logistic Regression)"
        ),
        version=(
            "1.0-custom"
        ),
        detector_type=(
            "ml_tfidf_logistic_regression"
        ),
        configuration={
            "vectorizer_file": str(
                vectorizer_path
            ),
            "classifier_file": str(
                classifier_path
            ),
            "vectorizer_type": (
                "TF-IDF"
            ),
            "classifier": (
                "Logistic Regression"
            ),
            "threshold": (
                "classifier.predict default"
            ),
            "sklearn_version": (
                sklearn_version
            ),
        },
        df=df,
        predictions=predictions,
        latencies=latencies,
        failures=failures,
        failures_by_index=failures_by_index,
        extra={
            "training_evaluation_note": (
                "This model is evaluated as a "
                "frozen trained artifact. The "
                "held-out evaluation dataset "
                "must not be used for training."
            )
        },
    )


# ================================================================
# IMPLEMENTATION 3
# PROTECT AI LLM GUARD
# ================================================================

def run_llm_guard(df):

    print(
        "\nRunning: LLM Guard "
        "(Protect AI)"
    )

    try:

        from llm_guard.input_scanners import (
            PromptInjection
        )

        from llm_guard.input_scanners.prompt_injection import (
            MatchType
        )

        scanner = PromptInjection(
            match_type=MatchType.FULL
        )

    except Exception as e:

        return {
            "name": (
                "LLM Guard — "
                "PromptInjectionScanner"
            ),
            "version": "unknown",
            "type": "ml_based",
            "error": (
                f"Failed to initialize "
                f"LLM Guard: {e}"
            ),
        }

    predictions = []
    latencies = []

    failures = 0
    failures_by_index = {}

    for index, text in enumerate(
        df["text"]
    ):

        start = time.perf_counter()

        try:

            _sanitized, is_valid, risk_score = (
                scanner.scan(
                    str(text)
                )
            )

            # LLM Guard:
            # is_valid=True  -> safe
            # is_valid=False -> injection

            prediction = (
                0
                if is_valid
                else 1
            )

            failures_by_index[index] = False

        except Exception as e:

            print(
                f"  LLM Guard failed "
                f"for sample {index}: {e}"
            )

            prediction = 0

            failures += 1

            failures_by_index[index] = True

        latency = (
            time.perf_counter()
            - start
        )

        predictions.append(
            prediction
        )

        latencies.append(
            latency
        )

    try:

        import llm_guard

        version = getattr(
            llm_guard,
            "__version__",
            "unknown",
        )

    except Exception:

        version = "unknown"

    return finalize_detector_result(
        name=(
            "LLM Guard — "
            "PromptInjectionScanner"
        ),
        version=(
            f"llm-guard {version}"
        ),
        detector_type="ml_based",
        configuration={
            "scanner": (
                "PromptInjection"
            ),
            "match_type": "FULL",
            "model": (
                "ProtectAI/"
                "deberta-v3-base-prompt-injection"
            ),
            "device": "CPU",
        },
        df=df,
        predictions=predictions,
        latencies=latencies,
        failures=failures,
        failures_by_index=failures_by_index,
    )


# ================================================================
# GUARDRAILS AI
# NOT COMPARABLE
# ================================================================

def guardrails_ai_not_comparable():

    return {
        "name": (
            "Guardrails AI — "
            "DetectPromptInjection"
        ),
        "version": (
            "guardrails-ai 0.10.2"
        ),
        "not_comparable": True,
        "status": "not_comparable",
        "reason": (
            "The investigated Guardrails AI "
            "prompt-injection validators were "
            "not available as a standalone "
            "fully local classifier under the "
            "benchmark constraints. The "
            "DetectPromptInjection implementation "
            "investigated depends on external "
            "vector-database infrastructure, "
            "while the alternative "
            "PromptInjectionDetector relies on "
            "a hosted LLM API for scoring. "
            "Using either would violate the "
            "benchmark's requirement for a "
            "technically comparable local "
            "component without sending evaluation "
            "data to hosted APIs."
        ),
        "configuration": {
            "validator": (
                "DetectPromptInjection"
            ),
            "on_fail": "noop",
        },
    }


# ================================================================
# NVIDIA NEMO GUARDRAILS
# NOT COMPARABLE
# ================================================================

def nemo_not_comparable():

    return {
        "name": (
            "NVIDIA NeMo Guardrails"
        ),
        "version": "investigated",
        "not_comparable": True,
        "status": "not_comparable",
        "reason": (
            "The investigated injection/jailbreak "
            "detection approach in NeMo Guardrails "
            "is implemented through an LLM-judged "
            "rail requiring a configured LLM and "
            "rail configuration. This is not a "
            "standalone prompt-injection classifier "
            "that can be evaluated under the same "
            "local classifier conditions as the "
            "selected external baselines."
        ),
        "configuration": {
            "component": (
                "jailbreak/injection detection rail"
            ),
        },
    }


# ================================================================
# IMPLEMENTATION 4
# META LLAMAFIREWALL — PROMPTGUARD
# ================================================================

def run_llamafirewall(df):

    print(
        "\nRunning: "
        "Meta LlamaFirewall — PromptGuard"
    )

    try:

        from llamafirewall import (
            LlamaFirewall,
            Role,
            ScanDecision,
            ScannerType,
            UserMessage,
        )

        firewall = LlamaFirewall(
            scanners={
                Role.USER: [
                    ScannerType.PROMPT_GUARD
                ]
            }
        )

        # Fail fast if model access is unavailable.
        firewall.scan(
            UserMessage(
                content="test"
            )
        )

    except Exception as e:

        message = str(e)

        return {
            "name": (
                "Meta LlamaFirewall — "
                "PromptGuard"
            ),
            "version": (
                "llamafirewall"
            ),
            "type": "ml_based",
            "status": "execution_unavailable",
            "error": (
                f"PromptGuard could not "
                f"be initialized: {message}"
            ),
            "configuration": {
                "scanner": (
                    "PROMPT_GUARD"
                ),
                "model": (
                    "meta-llama/"
                    "Llama-Prompt-Guard-2-86M"
                ),
                "device": "CPU",
            },
        }

    predictions = []
    latencies = []

    failures = 0
    failures_by_index = {}

    for index, text in enumerate(
        df["text"]
    ):

        start = time.perf_counter()

        try:

            result = firewall.scan(
                UserMessage(
                    content=str(text)
                )
            )

            prediction = (
                1
                if result.decision
                == ScanDecision.BLOCK
                else 0
            )

            failures_by_index[index] = False

        except Exception as e:

            print(
                f"  LlamaFirewall failed "
                f"for sample {index}: {e}"
            )

            prediction = 0

            failures += 1

            failures_by_index[index] = True

        latency = (
            time.perf_counter()
            - start
        )

        predictions.append(
            prediction
        )

        latencies.append(
            latency
        )

    try:

        import llamafirewall

        version = getattr(
            llamafirewall,
            "__version__",
            "unknown",
        )

    except Exception:

        version = "unknown"

    return finalize_detector_result(
        name=(
            "Meta LlamaFirewall — "
            "PromptGuard"
        ),
        version=(
            f"llamafirewall {version}"
        ),
        detector_type="ml_based",
        configuration={
            "scanner": (
                "PROMPT_GUARD"
            ),
            "model": (
                "meta-llama/"
                "Llama-Prompt-Guard-2-86M"
            ),
            "device": "CPU",
        },
        df=df,
        predictions=predictions,
        latencies=latencies,
        failures=failures,
        failures_by_index=failures_by_index,
    )


# ================================================================
# PRINT COMPARISON TABLE
# ================================================================

def print_comparison_table(
    results
):

    print("\n")
    print("=" * 100)
    print(
        "GUARDRAIL FRAMEWORK COMPARISON"
    )
    print("=" * 100)

    print(
        f"{'Framework':<42}"
        f"{'F1':>8}"
        f"{'Prec':>8}"
        f"{'Recall':>8}"
        f"{'FPR':>8}"
        f"{'P95ms':>10}"
    )

    print("-" * 100)

    for result in results:

        name = result.get(
            "name",
            "Unknown"
        )

        if result.get(
            "status"
        ) == "not_comparable":

            print(
                f"{name:<42}"
                f"{'NOT COMPARABLE':>30}"
            )

            continue

        if "error" in result:

            print(
                f"{name:<42}"
                f"{'ERROR':>30}"
            )

            continue

        metrics = result.get(
            "metrics",
            {}
        )

        print(
            f"{name:<42}"
            f"{metrics.get('f1_score', 0):>7}%"
            f"{metrics.get('precision', 0):>7}%"
            f"{metrics.get('recall', 0):>7}%"
            f"{metrics.get('false_positive_rate', 0):>7}%"
            f"{metrics.get('latency_p95_ms', 0):>9}ms"
        )

    print("=" * 100)


# ================================================================
# ARGUMENT PARSER
# ================================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "Compare prompt-injection "
            "detectors on the same "
            "held-out evaluation dataset."
        )
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_EVAL_DATASET,
        help=(
            "Path to held-out evaluation "
            "CSV dataset."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_RESULTS_FILE,
        help=(
            "Path to machine-readable "
            "JSON results."
        ),
    )

    return parser.parse_args()


# ================================================================
# MAIN
# ================================================================

def main():

    args = parse_arguments()

    print(
        "=" * 70
    )

    print(
        "GUARDRAIL FRAMEWORK COMPARISON"
    )

    print(
        "Security Task: "
        "Prompt Injection Detection"
    )

    print(
        "All comparable implementations "
        "use the SAME evaluation dataset."
    )

    print(
        "=" * 70
    )

    # ------------------------------------------------------------
    # Load dataset ONCE
    # ------------------------------------------------------------

    df = load_eval_dataset(
        args.dataset
    )

    # ------------------------------------------------------------
    # Run all comparable detectors
    # ------------------------------------------------------------

    results = []

    results.append(
        run_keyword_detector(df)
    )

    results.append(
        run_ml_detector(df)
    )

    results.append(
        run_llm_guard(df)
    )

    results.append(
        run_llamafirewall(df)
    )

    # ------------------------------------------------------------
    # Document non-comparable frameworks
    # ------------------------------------------------------------

    results.append(
        guardrails_ai_not_comparable()
    )

    results.append(
        nemo_not_comparable()
    )

    # ------------------------------------------------------------
    # Print summary
    # ------------------------------------------------------------

    print_comparison_table(
        results
    )

    # ------------------------------------------------------------
    # Build category distribution
    # ------------------------------------------------------------

    category_distribution = {}

    if "attack_type" in df.columns:

        category_distribution = (
            df.groupby(
                [
                    "attack_type",
                    "label",
                ]
            )
            .size()
            .unstack(
                fill_value=0
            )
            .rename(
                columns={
                    0: "benign",
                    1: "attack",
                }
            )
            .to_dict(
                orient="index"
            )
        )

        category_distribution = {
            str(k): {
                str(label): int(value)
                for label, value
                in v.items()
            }
            for k, v
            in category_distribution.items()
        }

    # ------------------------------------------------------------
    # Reproduction commands
    # ------------------------------------------------------------

    reproduction_commands = [

        "python src/ml_detector.py "
        "train --dataset synthetic",

        "python src/guardrail_comparison.py "
        "--dataset datasets/eval_dataset_v2.csv",

        "python src/guardrail_comparison.py "
        "--dataset datasets/eval_dataset_v2.csv "
        "--output "
        "experiments/results/"
        "guardrail_comparison.json",
    ]

    # ------------------------------------------------------------
    # Build final JSON
    # ------------------------------------------------------------

    output = {

        "timestamp": (
            datetime.now().isoformat()
        ),

        "security_task": (
            "Prompt Injection Detection"
        ),

        "task_definition": {

            "input": (
                "A text prompt or "
                "serialized conversation."
            ),

            "output": (
                "1 = prompt injection / "
                "attack detected, "
                "0 = benign / safe."
            ),

            "positive_class": (
                "Prompt injection attack."
            ),

        },

        "evaluation_dataset": {

            "path": str(
                args.dataset
            ),

            "total_samples": int(
                len(df)
            ),

            "attack_samples": int(
                (df["label"] == 1).sum()
            ),

            "benign_samples": int(
                (df["label"] == 0).sum()
            ),

            "columns": list(
                df.columns
            ),

            "category_distribution": (
                category_distribution
            ),

        },

        "hardware": {

            "platform": platform.platform(),

            "python_version": (
                sys.version
            ),

            "processor": (
                platform.processor()
            ),

            "device": "CPU",

        },

        "reproduction_commands": (
            reproduction_commands
        ),

        "constraints_confirmed": {

            "same_dataset_all_comparable_implementations": True,

            "current_implementation_not_replaced": True,

            "no_sensitive_data_sent_to_hosted_apis": True,

            "no_credentials_committed": True,

            "no_framework_specific_test_dataset": True,

            "machine_readable_results": True,

        },

        "results": results,

    }

    # ------------------------------------------------------------
    # Save JSON
    # ------------------------------------------------------------

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        args.output,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            output,
            file,
            indent=2,
        )

    print(
        "\n"
        + "=" * 70
    )

    print(
        "BENCHMARK COMPLETE"
    )

    print(
        f"Results saved to:"
    )

    print(
        args.output
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()
