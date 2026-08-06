"""
Guardrail Framework Comparison
==============================

Purpose:
    Benchmark the repository's current ML prompt-injection detector
    against technically comparable open-source prompt-injection
    detection baselines.

Evaluated comparable systems:
    1. Our ML Detector
       - TF-IDF
       - Logistic Regression

    2. Protect AI LLM Guard
       - PromptInjection scanner

    3. Meta Llama Prompt Guard
       - Local HuggingFace model

Not comparable:
    4. Guardrails AI
    5. NVIDIA NeMo Guardrails

Evaluation dataset:
    datasets/eval_dataset_v2.csv

Model to evaluate:
    Selected via --model-tag (default: synthetic), matching the tag
    used when training with ml_detector.py, e.g.:
        python src/ml_detector.py train --dataset synthetic
        python src/ml_detector.py train --dataset augmented_combined
    Loads experiments/models/vectorizer_<tag>.pkl and
    classifier_<tag>.pkl - these paths are tag-based because
    ml_detector.py never writes an untagged vectorizer.pkl/
    classifier.pkl, only tagged variants (one file set per
    dataset type, so retraining on augmented data never silently
    overwrites the baseline model).

Expected dataset columns:
    id
    text
    label
    attack_type
    difficulty
    language
    source
    notes

Label convention:
    0 = benign
    1 = prompt injection

Output:
    experiments/results/guardrail_comparison_<model-tag>.json
    (one file per tag, so a baseline run and an improved run never
    overwrite each other - run once per tag you want to compare)

Important benchmark rules:
    - Every comparable detector receives exactly the same dataset.
    - No framework-specific dataset tuning.
    - No hosted APIs.
    - No sensitive data is sent externally.
    - Failures are recorded.
    - Latency is measured locally.
    - Per-category metrics are reported.
    - Technically incompatible frameworks are marked not_comparable.
"""

import argparse
import json
import pickle
import platform
import statistics
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent

DEFAULT_DATASET = (
    ROOT_DIR
    / "datasets"
    / "eval_dataset_v2.csv"
)

MODEL_DIR = (
    ROOT_DIR
    / "experiments"
    / "models"
)

RESULTS_DIR = (
    ROOT_DIR
    / "experiments"
    / "results"
)


# ============================================================
# TAGGED MODEL / OUTPUT PATHS
# (must match ml_detector.py's vectorizer_path()/classifier_path()
#  naming exactly, since ml_detector.py never writes an untagged
#  "vectorizer.pkl"/"classifier.pkl" - only tagged variants like
#  "vectorizer_synthetic.pkl", "vectorizer_augmented_combined.pkl")
# ============================================================

def vectorizer_path(tag):
    return MODEL_DIR / f"vectorizer_{tag}.pkl"


def classifier_path(tag):
    return MODEL_DIR / f"classifier_{tag}.pkl"


def comparison_output_path(tag):
    return RESULTS_DIR / f"guardrail_comparison_{tag}.json"


# ============================================================
# OPTIONAL DEPENDENCY: LLM GUARD
# ============================================================

try:

    from llm_guard.input_scanners import PromptInjection

    LLM_GUARD_AVAILABLE = True

    LLM_GUARD_IMPORT_ERROR = None

except Exception as e:

    LLM_GUARD_AVAILABLE = False

    LLM_GUARD_IMPORT_ERROR = str(e)


# ============================================================
# OPTIONAL DEPENDENCY: TRANSFORMERS + PYTORCH
# ============================================================

try:

    from transformers import (
        AutoTokenizer,
        AutoModelForSequenceClassification
    )

    import torch

    TRANSFORMERS_AVAILABLE = True

    TRANSFORMERS_IMPORT_ERROR = None

except Exception as e:

    TRANSFORMERS_AVAILABLE = False

    TRANSFORMERS_IMPORT_ERROR = str(e)


# ============================================================
# CONFIGURATION
# ============================================================

LLAMA_PROMPT_GUARD_MODEL = (
    "meta-llama/Llama-Prompt-Guard-2-86M"
)

LLM_GUARD_THRESHOLD = 0.5

LLAMA_PROMPT_GUARD_THRESHOLD = 0.5

WARMUP_RUNS = 5


# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def utc_now():

    return datetime.now(
        timezone.utc
    ).isoformat()


def safe_float(value):

    if value is None:

        return None

    try:

        return float(value)

    except Exception:

        return None


def percentile(
    values,
    percentile_value
):

    if not values:

        return None

    return safe_float(
        np.percentile(
            values,
            percentile_value
        )
    )


# ============================================================
# METRIC CALCULATION
# ============================================================

def calculate_metrics(
    y_true,
    y_pred,
    latencies_ms
):

    """
    Calculate binary classification metrics.

    Positive class:
        1 = prompt injection

    Negative class:
        0 = benign
    """

    y_true = np.array(
        y_true,
        dtype=int
    )

    y_pred = np.array(
        y_pred,
        dtype=int
    )

    tp = int(
        np.sum(
            (y_true == 1)
            &
            (y_pred == 1)
        )
    )

    tn = int(
        np.sum(
            (y_true == 0)
            &
            (y_pred == 0)
        )
    )

    fp = int(
        np.sum(
            (y_true == 0)
            &
            (y_pred == 1)
        )
    )

    fn = int(
        np.sum(
            (y_true == 1)
            &
            (y_pred == 0)
        )
    )

    precision = (

        tp / (tp + fp)

        if (tp + fp) > 0

        else 0.0

    )

    recall = (

        tp / (tp + fn)

        if (tp + fn) > 0

        else 0.0

    )

    f1 = (

        2
        * precision
        * recall
        / (precision + recall)

        if (precision + recall) > 0

        else 0.0

    )

    false_positive_rate = (

        fp / (fp + tn)

        if (fp + tn) > 0

        else 0.0

    )

    false_negative_rate = (

        fn / (fn + tp)

        if (fn + tp) > 0

        else 0.0

    )

    accuracy = (

        (tp + tn)
        / len(y_true)

        if len(y_true) > 0

        else 0.0

    )

    median_latency = (

        statistics.median(
            latencies_ms
        )

        if latencies_ms

        else None

    )

    p95_latency = percentile(
        latencies_ms,
        95
    )

    throughput = (

        1000 / median_latency

        if (
            median_latency
            and median_latency > 0
        )

        else None

    )

    return {

        "confusion_matrix": {

            "TP":
                tp,

            "FP":
                fp,

            "TN":
                tn,

            "FN":
                fn

        },

        "metrics": {

            "accuracy":
                round(
                    accuracy,
                    6
                ),

            "precision":
                round(
                    precision,
                    6
                ),

            "recall":
                round(
                    recall,
                    6
                ),

            "f1":
                round(
                    f1,
                    6
                ),

            "false_positive_rate":
                round(
                    false_positive_rate,
                    6
                ),

            "false_negative_rate":
                round(
                    false_negative_rate,
                    6
                )

        },

        "latency_ms": {

            "median":
                (
                    round(
                        median_latency,
                        4
                    )

                    if median_latency
                    is not None

                    else None
                ),

            "p95":
                (
                    round(
                        p95_latency,
                        4
                    )

                    if p95_latency
                    is not None

                    else None
                )

        },

        "throughput_prompts_per_second":
            (
                round(
                    throughput,
                    4
                )

                if throughput
                is not None

                else None
            )

    }


# ============================================================
# DATASET LOADING
# ============================================================

def load_dataset(
    dataset_path
):

    print(
        "\nLoading evaluation dataset..."
    )

    df = pd.read_csv(
        dataset_path
    )

    print(
        f"Dataset shape: {df.shape}"
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Your dataset uses "text", NOT "prompt".
    # --------------------------------------------------------

    required_columns = [

        "text",

        "label"

    ]

    for column in required_columns:

        if column not in df.columns:

            raise ValueError(

                f"Required column "
                f"'{column}' not found."

            )

    df = df.copy()

    # Normalize the repository's "text"
    # column to the internal "text" name.

    df["text"] = (

        df["text"]

        .fillna("")

        .astype(str)

        .str.strip()

    )

    df["label"] = pd.to_numeric(

        df["label"],

        errors="raise"

    ).astype(int)

    invalid_labels = (

        set(
            df["label"].unique()
        )

        - {0, 1}

    )

    if invalid_labels:

        raise ValueError(

            f"Invalid labels found: "
            f"{invalid_labels}. "
            f"Labels must be 0 or 1."

        )

    # Remove empty text

    df = df[
        df["text"] != ""
    ].copy()

    # Do NOT remove duplicates here.
    # The exact held-out evaluation dataset
    # should be evaluated as supplied.

    print(
        "\nLabel distribution:"
    )

    print(
        df["label"]
        .value_counts()
        .sort_index()
    )

    if "attack_type" in df.columns:

        print(
            "\nAttack type distribution:"
        )

        print(
            df["attack_type"]
            .value_counts()
        )

    return df


# ============================================================
# ML DETECTOR
# ============================================================

def load_ml_detector(model_tag):

    print(
        "\nLoading repository ML detector "
        f"(tag: {model_tag})..."
    )

    vec_path = vectorizer_path(model_tag)
    clf_path = classifier_path(model_tag)

    if not vec_path.exists():

        raise FileNotFoundError(

            f"Vectorizer not found for tag '{model_tag}':\n"
            f"{vec_path}\n\n"
            f"Train it first, e.g.:\n"
            f"python src/ml_detector.py train --dataset {model_tag}"

        )

    if not clf_path.exists():

        raise FileNotFoundError(

            f"Classifier not found for tag '{model_tag}':\n"
            f"{clf_path}\n\n"
            f"Train it first, e.g.:\n"
            f"python src/ml_detector.py train --dataset {model_tag}"

        )

    with open(
        vec_path,
        "rb"
    ) as f:

        vectorizer = pickle.load(
            f
        )

    with open(
        clf_path,
        "rb"
    ) as f:

        classifier = pickle.load(
            f
        )

    print(
        f"ML vectorizer loaded from: {vec_path}"
    )

    print(
        f"ML classifier loaded from: {clf_path}"
    )

    return (
        vectorizer,
        classifier
    )


def run_ml_detector(
    vectorizer,
    classifier,
    text
):

    X = vectorizer.transform(
        [text]
    )

    prediction = int(

        classifier.predict(
            X
        )[0]

    )

    probability = None

    if hasattr(
        classifier,
        "predict_proba"
    ):

        probability = float(

            classifier.predict_proba(
                X
            )[0][1]

        )

    return (
        prediction,
        probability
    )


# ============================================================
# LLM GUARD
# ============================================================

def load_llm_guard():

    if not LLM_GUARD_AVAILABLE:

        print(
            "\nLLM Guard unavailable."
        )

        print(
            f"Reason: "
            f"{LLM_GUARD_IMPORT_ERROR}"
        )

        return None

    print(
        "\nLoading Protect AI LLM Guard..."
    )

    scanner = PromptInjection(

        threshold=
            LLM_GUARD_THRESHOLD

    )

    print(
        "LLM Guard PromptInjection scanner loaded."
    )

    return scanner


def run_llm_guard(
    scanner,
    text
):

    if scanner is None:

        raise RuntimeError(

            "LLM Guard scanner unavailable."

        )

    sanitized_text, is_valid, score = (

        scanner.scan(
            text
        )

    )

    # LLM Guard:
    # is_valid=True means benign
    # is_valid=False means detected injection

    prediction = (

        0

        if is_valid

        else 1

    )

    return (

        prediction,

        float(score)

    )


# ============================================================
# META LLAMA PROMPT GUARD
# ============================================================

def load_llama_prompt_guard():

    if not TRANSFORMERS_AVAILABLE:

        print(
            "\nTransformers/PyTorch unavailable."
        )

        print(
            f"Reason: "
            f"{TRANSFORMERS_IMPORT_ERROR}"
        )

        return (
            None,
            None,
            None
        )

    print(
        "\nLoading Meta Llama Prompt Guard..."
    )

    print(
        f"Model: "
        f"{LLAMA_PROMPT_GUARD_MODEL}"
    )

    tokenizer = (

        AutoTokenizer.from_pretrained(

            LLAMA_PROMPT_GUARD_MODEL

        )

    )

    model = (

        AutoModelForSequenceClassification
        .from_pretrained(

            LLAMA_PROMPT_GUARD_MODEL

        )

    )

    if torch.cuda.is_available():

        device = "cuda"

    else:

        device = "cpu"

    model.to(
        device
    )

    model.eval()

    print(
        f"Prompt Guard device: "
        f"{device}"
    )

    return (

        tokenizer,

        model,

        device

    )


def run_llama_prompt_guard(

    tokenizer,

    model,

    device,

    text

):

    if (
        tokenizer is None
        or model is None
    ):

        raise RuntimeError(

            "Llama Prompt Guard unavailable."

        )

    inputs = tokenizer(

        text,

        return_tensors="pt",

        truncation=True

    )

    inputs = {

        key:
            value.to(device)

        for key, value
        in inputs.items()

    }

    with torch.no_grad():

        outputs = model(
            **inputs
        )

        probabilities = torch.softmax(

            outputs.logits,

            dim=-1

        )[0]

    attack_probability = float(

        probabilities[1].item()

    )

    prediction = int(

        attack_probability
        >=
        LLAMA_PROMPT_GUARD_THRESHOLD

    )

    return (

        prediction,

        attack_probability

    )


# ============================================================
# CATEGORY METRICS
# ============================================================

def calculate_per_category_metrics(

    df,

    predictions,

    latencies

):

    if "attack_type" not in df.columns:

        return {}

    category_results = {}

    for category in sorted(

        df["attack_type"]
        .dropna()
        .unique()

    ):

        category_indices = [

            i

            for i in range(
                len(df)
            )

            if (

                df.iloc[i][
                    "attack_type"
                ]

                == category

            )

            and (

                predictions[i]
                is not None

            )

        ]

        if not category_indices:

            continue

        category_true = [

            int(
                df.iloc[i]["label"]
            )

            for i
            in category_indices

        ]

        category_pred = [

            int(
                predictions[i]
            )

            for i
            in category_indices

        ]

        category_latencies = [

            latencies[i]

            for i
            in category_indices

        ]

        category_metrics = (

            calculate_metrics(

                category_true,

                category_pred,

                category_latencies

            )

        )

        category_metrics[

            "samples"

        ] = len(category_indices)

        category_metrics[

            "attack_samples"

        ] = int(

            sum(
                category_true
            )

        )

        category_metrics[

            "benign_samples"

        ] = int(

            len(
                category_true
            )
            -
            sum(
                category_true
            )

        )

        category_results[

            category

        ] = category_metrics

    return category_results


# ============================================================
# BENCHMARK DETECTOR
# ============================================================

def benchmark_detector(

    name,

    df,

    detector_function

):

    print(
        "\n"
        + "=" * 70
    )

    print(
        f"RUNNING: {name}"
    )

    print(
        "=" * 70
    )

    predictions = []

    scores = []

    latencies = []

    failures = []

    # --------------------------------------------------------
    # Warmup
    # --------------------------------------------------------

    print(

        f"Warmup runs: "
        f"{WARMUP_RUNS}"

    )

    for i in range(

        min(
            WARMUP_RUNS,
            len(df)
        )

    ):

        try:

            detector_function(

                df.iloc[i][
                    "text"
                ]

            )

        except Exception:

            pass

    # --------------------------------------------------------
    # Evaluation
    # --------------------------------------------------------

    for index, row in df.iterrows():

        text = row[
            "text"
        ]

        start = time.perf_counter()

        try:

            prediction, score = (

                detector_function(
                    text
                )

            )

            elapsed_ms = (

                time.perf_counter()
                -
                start

            ) * 1000

            predictions.append(

                int(
                    prediction
                )

            )

            scores.append(

                safe_float(
                    score
                )

            )

            latencies.append(

                elapsed_ms

            )

        except Exception as e:

            elapsed_ms = (

                time.perf_counter()
                -
                start

            ) * 1000

            predictions.append(
                None
            )

            scores.append(
                None
            )

            latencies.append(

                elapsed_ms

            )

            failures.append({

                "index":
                    int(index),

                "id":
                    (
                        str(
                            row["id"]
                        )

                        if "id"
                        in df.columns

                        else None
                    ),

                "error":
                    str(e)

            })

    # --------------------------------------------------------
    # Successful samples
    # --------------------------------------------------------

    valid_indices = [

        i

        for i, prediction
        in enumerate(
            predictions
        )

        if prediction
        is not None

    ]

    y_true = [

        int(
            df.iloc[i][
                "label"
            ]
        )

        for i
        in valid_indices

    ]

    y_pred = [

        int(
            predictions[i]
        )

        for i
        in valid_indices

    ]

    valid_latencies = [

        latencies[i]

        for i
        in valid_indices

    ]

    result = calculate_metrics(

        y_true,

        y_pred,

        valid_latencies

    )

    # --------------------------------------------------------
    # Evaluation information
    # --------------------------------------------------------

    result["evaluation"] = {

        "total_samples":
            len(df),

        "successful_samples":
            len(valid_indices),

        "failed_samples":
            len(failures),

        "failure_rate":
            (
                len(failures)
                /
                len(df)

                if len(df) > 0

                else 0.0
            )

    }

    result["failures"] = failures

    # --------------------------------------------------------
    # Per-category metrics
    # --------------------------------------------------------

    result[

        "per_category_results"

    ] = calculate_per_category_metrics(

        df,

        predictions,

        latencies

    )

    result["name"] = name

    # --------------------------------------------------------
    # Console output
    # --------------------------------------------------------

    print(
        f"\n{name}"
    )

    print(

        f"Successful: "
        f"{len(valid_indices)}/{len(df)}"

    )

    print(

        f"Failures: "
        f"{len(failures)}"

    )

    print(

        f"Precision: "
        f"{result['metrics']['precision'] * 100:.2f}%"

    )

    print(

        f"Recall: "
        f"{result['metrics']['recall'] * 100:.2f}%"

    )

    print(

        f"F1: "
        f"{result['metrics']['f1'] * 100:.2f}%"

    )

    print(

        f"FPR: "
        f"{result['metrics']['false_positive_rate'] * 100:.2f}%"

    )

    print(

        f"FNR: "
        f"{result['metrics']['false_negative_rate'] * 100:.2f}%"

    )

    print(

        f"Median latency: "
        f"{result['latency_ms']['median']} ms"

    )

    print(

        f"P95 latency: "
        f"{result['latency_ms']['p95']} ms"

    )

    print(

        f"Throughput: "
        f"{result['throughput_prompts_per_second']} "
        f"prompts/sec"

    )

    return result


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(

        description=(

            "Benchmark repository ML detector "
            "against comparable prompt-injection "
            "guardrail systems."

        )

    )

    parser.add_argument(

        "--dataset",

        type=str,

        default=str(
            DEFAULT_DATASET
        ),

        help=(

            "Path to held-out evaluation CSV."

        )

    )

    parser.add_argument(

        "--model-tag",

        type=str,

        default="synthetic",

        help=(

            "Which trained model to load, identified by the tag used "
            "when it was trained (see ml_detector.py train --model-tag). "
            "Must match an existing vectorizer_<tag>.pkl / "
            "classifier_<tag>.pkl pair in experiments/models/. "
            "Examples: synthetic, combined, augmented, augmented_v2, "
            "augmented_combined, or a custom tag."

        )

    )

    args = parser.parse_args()

    dataset_path = Path(

        args.dataset

    )

    if not dataset_path.is_absolute():

        dataset_path = (

            ROOT_DIR
            /
            dataset_path

        )

    model_tag = args.model_tag

    output_path = comparison_output_path(
        model_tag
    )

    print(

        "\n"
        + "=" * 70

    )

    print(

        "GUARDRAIL FRAMEWORK COMPARISON"

    )

    print(

        "=" * 70

    )

    print(

        f"Dataset: "
        f"{dataset_path}"

    )

    print(

        f"Model tag: "
        f"{model_tag}"

    )

    print(

        f"Output: "
        f"{output_path}"

    )

    print(

        f"Started: "
        f"{utc_now()}"

    )

    # --------------------------------------------------------
    # Load evaluation dataset
    # --------------------------------------------------------

    df = load_dataset(

        dataset_path

    )

    # --------------------------------------------------------
    # Load repository ML detector
    # --------------------------------------------------------

    vectorizer, classifier = (

        load_ml_detector(
            model_tag
        )

    )

    # --------------------------------------------------------
    # Load external baselines
    # --------------------------------------------------------

    llm_guard = (

        load_llm_guard()

    )

    (

        llama_tokenizer,

        llama_model,

        llama_device

    ) = (

        load_llama_prompt_guard()

    )

    results = {}

    # ========================================================
    # 1. OUR ML DETECTOR
    # ========================================================

    results[

        "our_ml_detector"

    ] = benchmark_detector(

        f"Our ML Detector "
        f"(TF-IDF + Logistic Regression, tag: {model_tag})",

        df,

        lambda text:

            run_ml_detector(

                vectorizer,

                classifier,

                text

            )

    )

    # ========================================================
    # 2. PROTECT AI LLM GUARD
    # ========================================================

    if llm_guard is not None:

        results[

            "llm_guard"

        ] = benchmark_detector(

            "Protect AI LLM Guard "
            "(PromptInjection Scanner)",

            df,

            lambda text:

                run_llm_guard(

                    llm_guard,

                    text

                )

        )

    else:

        results[

            "llm_guard"

        ] = {

            "name":
                "Protect AI LLM Guard",

            "status":
                "unavailable",

            "error":
                LLM_GUARD_IMPORT_ERROR

        }

    # ========================================================
    # 3. META LLAMA PROMPT GUARD
    # ========================================================

    if (

        llama_tokenizer is not None

        and

        llama_model is not None

    ):

        results[

            "llama_prompt_guard"

        ] = benchmark_detector(

            "Meta Llama Prompt Guard",

            df,

            lambda text:

                run_llama_prompt_guard(

                    llama_tokenizer,

                    llama_model,

                    llama_device,

                    text

                )

        )

    else:

        results[

            "llama_prompt_guard"

        ] = {

            "name":
                "Meta Llama Prompt Guard",

            "status":
                "unavailable",

            "error":
                TRANSFORMERS_IMPORT_ERROR

        }

    # ========================================================
    # 4. GUARDRAILS AI
    # ========================================================

    results[

        "guardrails_ai"

    ] = {

        "name":
            "Guardrails AI",

        "status":
            "not_comparable",

        "reason":

            (

                "The investigated Guardrails AI "
                "prompt-injection validation approach "
                "was not treated as a technically "
                "equivalent standalone local binary "
                "prompt-injection classifier under "
                "the benchmark constraints."

            )

    }

    # ========================================================
    # 5. NVIDIA NEMO GUARDRAILS
    # ========================================================

    results[

        "nvidia_nemo_guardrails"

    ] = {

        "name":
            "NVIDIA NeMo Guardrails",

        "status":
            "not_comparable",

        "reason":

            (

                "The investigated NeMo Guardrails "
                "approach operates as a conversational "
                "rail system and requires an LLM-based "
                "evaluation path rather than functioning "
                "as a directly equivalent standalone "
                "local prompt-injection classifier."

            )

    }

    # ========================================================
    # ENVIRONMENT
    # ========================================================

    environment = {

        "timestamp_utc":
            utc_now(),

        "python_version":
            sys.version,

        "platform":
            platform.platform(),

        "python_executable":
            sys.executable,

        "dataset":
            str(
                dataset_path
            ),

        "dataset_samples":
            int(
                len(df)
            ),

        "dataset_columns":
            list(
                df.columns
            ),

        "label_distribution":

            {

                str(k):
                    int(v)

                for k, v

                in df[
                    "label"
                ]
                .value_counts()
                .items()

            },

        "attack_categories":

            (

                sorted(

                    df[
                        "attack_type"
                    ]
                    .dropna()
                    .unique()
                    .tolist()

                )

                if "attack_type"
                in df.columns

                else []

            ),

        "models":

            {

                "ml_model_tag":
                    model_tag,

                "ml_vectorizer":
                    str(
                        vectorizer_path(model_tag)
                    ),

                "ml_classifier":
                    str(
                        classifier_path(model_tag)
                    ),

                "llama_prompt_guard":
                    LLAMA_PROMPT_GUARD_MODEL

            },

        "thresholds":

            {

                "ml_detector":
                    0.5,

                "llm_guard":
                    LLM_GUARD_THRESHOLD,

                "llama_prompt_guard":
                    LLAMA_PROMPT_GUARD_THRESHOLD

            },

        "hardware":

            {

                "device":
                    (
                        llama_device

                        if llama_device
                        is not None

                        else "CPU/unknown"
                    ),

                "cuda_available":
                    (

                        bool(
                            torch.cuda.is_available()
                        )

                        if TRANSFORMERS_AVAILABLE

                        else False

                    )

            },

        "warmup_runs":
            WARMUP_RUNS

    }

    # ========================================================
    # REPRODUCTION COMMANDS
    # ========================================================

    reproduction_commands = [

        "python -m venv .venv",

        ".venv\\Scripts\\activate",

        "pip install -r requirements.txt",

        f"python src/ml_detector.py "
        f"train --dataset {model_tag}",

        f"python src/ml_detector.py "
        f"evaluate --dataset "
        f"datasets/eval_dataset_v2.csv --model {model_tag}",

        f"python src/guardrail_comparison.py "
        f"--dataset datasets/eval_dataset_v2.csv "
        f"--model-tag {model_tag}"

    ]

    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    final_output = {

        "benchmark": {

            "title":

                (

                    "Prompt Injection Detection "
                    "and Guardrail Framework "
                    "Comparison"

                ),

            "security_task":

                (

                    "Binary detection of prompt "
                    "injection attacks in text prompts."

                ),

            "positive_label":

                "1 = prompt injection",

            "negative_label":

                "0 = benign",

            "evaluation_dataset":

                str(
                    dataset_path
                ),

            "same_dataset_for_all_comparable_systems":

                True,

            "hosted_api_used":

                False,

            "frameworks_quantitatively_compared":

                [

                    "Our ML Detector",

                    "Protect AI LLM Guard",

                    "Meta Llama Prompt Guard"

                ],

            "frameworks_not_comparable":

                [

                    "Guardrails AI",

                    "NVIDIA NeMo Guardrails"

                ]

        },

        "environment":
            environment,

        "reproduction_commands":
            reproduction_commands,

        "results":
            results,

        "limitations":

            [

                (

                    "The evaluation dataset is synthetic "
                    "and may not fully represent real-world "
                    "prompt injection attacks."

                ),

                (

                    "Results should be interpreted using "
                    "both aggregate and per-category metrics."

                ),

                (

                    "Latency depends on the local hardware "
                    "and software environment."

                ),

                (

                    "The external frameworks were evaluated "
                    "without framework-specific dataset tuning."

                ),

                (

                    "Frameworks marked not_comparable were "
                    "excluded from quantitative comparison."

                ),

                (

                    "A high F1 score on this dataset does not "
                    "guarantee generalization to unseen attack "
                    "strategies."

                )

            ],

        "completed_at_utc":
            utc_now()

    }

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    RESULTS_DIR.mkdir(

        parents=True,

        exist_ok=True

    )

    with open(

        output_path,

        "w",

        encoding="utf-8"

    ) as f:

        json.dump(

            final_output,

            f,

            indent=2,

            ensure_ascii=False

        )

    print(

        "\n"
        + "=" * 70

    )

    print(

        "BENCHMARK COMPLETE"

    )

    print(

        "=" * 70

    )

    print(

        "Results saved to:"

    )

    print(

        output_path

    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()