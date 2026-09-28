"""
ML-Based Prompt Injection Detector

Project:
Prompt Injection Detection and Defence for LLM-Based Applications

Model:
    TF-IDF + Logistic Regression

Training datasets:
    1. Synthetic attacks:
       datasets/prompt_injection_500.csv

    2. Synthetic benign:
       datasets/benign_500.csv

    3. Optional Garak attacks:
       datasets/garak_attacks.csv

Evaluation:
    Held-out evaluation dataset should NOT be used during training.

    Example:
        datasets/eval_dataset_v2.csv

Expected evaluation columns:
    id
    text
    label
    attack_type
    difficulty
    language
    source
    notes

Labels:
    0 = Benign
    1 = Prompt Injection Attack

Commands:

Train on synthetic data:
    python src/ml_detector.py train --dataset synthetic

Train on synthetic + Garak:
    python src/ml_detector.py train --dataset combined

Evaluate on held-out evaluation dataset:
    python src/ml_detector.py evaluate --dataset datasets/eval_dataset_v2.csv

Evaluate with custom threshold:
    python src/ml_detector.py evaluate --dataset datasets/eval_dataset_v2.csv --threshold 0.50

Interactive testing:
    python src/ml_detector.py test
"""

import argparse
import json

# pickle load path is hash-verified against the manifest in load_model()
import pickle  # nosec B403
import platform
import sys
import time
import warnings
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sklearn.exceptions import InconsistentVersionWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split

# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATASETS_DIR = BASE_DIR / "datasets"

MODELS_DIR = BASE_DIR / "experiments" / "models"

RESULTS_DIR = BASE_DIR / "experiments" / "results"

MODELS_DIR.mkdir(parents=True, exist_ok=True)

RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# MODEL FILES
# ============================================================

VECTORIZER_PATH = MODELS_DIR / "vectorizer.pkl"

CLASSIFIER_PATH = MODELS_DIR / "classifier.pkl"


# ============================================================
# RESULT FILES
# ============================================================

TRAINING_METRICS_PATH = RESULTS_DIR / "ml_detector_training_results.json"

EVALUATION_METRICS_PATH = RESULTS_DIR / "ml_detector_eval_results.json"


# ============================================================
# DATASET FILES
# ============================================================

SYNTHETIC_ATTACKS = DATASETS_DIR / "prompt_injection_500.csv"

SYNTHETIC_BENIGN = DATASETS_DIR / "benign_500.csv"


# ============================================================
# HELPER: EMPTY DATAFRAME
# ============================================================


def empty_dataset():

    return pd.DataFrame(columns=["text", "label"])


# ============================================================
# HELPER: CLEAN TRAINING DATA
# ============================================================


def clean_dataset(df):
    """
    Clean a binary classification dataset.

    Required columns:
        text
        label

    Labels:
        0 = benign
        1 = attack
    """

    required_columns = {"text", "label"}

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    df = df[["text", "label"]].copy()

    df = df.dropna(subset=["text"])

    df["text"] = df["text"].astype(str).str.strip()

    df = df[df["text"] != ""]

    df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)

    invalid_labels = set(df["label"].unique()) - {0, 1}

    if invalid_labels:
        raise ValueError(f"Invalid labels found: {invalid_labels}. Labels must be 0 or 1.")

    before = len(df)

    df = df.drop_duplicates(subset=["text"])

    after = len(df)

    print(f"Removed duplicates: {before - after}")

    df = df.sample(frac=1, random_state=42).reset_index(drop=True)

    return df


# ============================================================
# LOAD SYNTHETIC DATASET
# ============================================================


def _missing_training_data_message(path):
    """Precise, actionable error for absent training data (audit B2, Step 6.6)."""
    return (
        f"Training dataset not found:\n  {path}\n\n"
        "This file is NOT in the repository or its git history and cannot be "
        "auto-recovered. Fabricating a replacement is prohibited.\n"
        "To restore training (and unblock model regeneration + leakage checks):\n"
        "  1. Provide the original CSV with columns: text,label (0=benign,1=attack).\n"
        "  2. Record its provenance in datasets/README.md using the required\n"
        "     provenance schema (name, source, license, creation method,\n"
        "     generator version, random seed, record count, class/language\n"
        "     distribution, SHA-256, known limitations).\n"
        "  3. Use group-aware, template-family-held-out splits (see src/eval_checks.py)."
    )


def load_synthetic_dataset():

    print("\nLoading synthetic attack dataset...")

    if not SYNTHETIC_ATTACKS.exists():
        raise FileNotFoundError(_missing_training_data_message(SYNTHETIC_ATTACKS))

    attacks = pd.read_csv(SYNTHETIC_ATTACKS)

    print(f"Attack examples loaded: {len(attacks)}")

    print("\nLoading synthetic benign dataset...")

    if not SYNTHETIC_BENIGN.exists():
        raise FileNotFoundError(_missing_training_data_message(SYNTHETIC_BENIGN))

    benign = pd.read_csv(SYNTHETIC_BENIGN)

    print(f"Benign examples loaded: {len(benign)}")

    attacks = attacks[["text"]].copy()

    benign = benign[["text"]].copy()

    attacks["label"] = 1

    benign["label"] = 0

    df = pd.concat([attacks, benign], ignore_index=True)

    df = clean_dataset(df)

    return df


# ============================================================
# LOAD HACKAPROMPT
# ============================================================


def load_hackaprompt():

    print("\nSearching for HackAPrompt dataset...")

    possible_files = [
        DATASETS_DIR / "hackaprompt.csv",
        DATASETS_DIR / "hackaprompt_dataset.csv",
        DATASETS_DIR / "HackAPrompt.csv",
    ]

    file_path = None

    for path in possible_files:
        if path.exists():
            file_path = path

            break

    if file_path is None:
        print("HackAPrompt CSV not found.")

        print("Continuing without HackAPrompt.")

        return empty_dataset()

    print(f"Loading HackAPrompt:\n{file_path}")

    df = pd.read_csv(file_path)

    print(f"Loaded {len(df)} HackAPrompt rows.")

    possible_text_columns = [
        "text",
        "prompt",
        "attack",
        "instruction",
    ]

    text_column = None

    for column in possible_text_columns:
        if column in df.columns:
            text_column = column

            break

    if text_column is None:
        raise ValueError("Could not find a prompt/text column in HackAPrompt dataset.")

    result = pd.DataFrame({"text": df[text_column].astype(str), "label": [1] * len(df)})

    result["label"] = result["label"].astype(int)

    result = clean_dataset(result)

    return result


# ============================================================
# LOAD GARAK
# ============================================================


def load_garak():

    possible_files = [
        DATASETS_DIR / "garak_attacks.csv",
        DATASETS_DIR / "garak_prompts.csv",
    ]

    file_path = None

    for path in possible_files:
        if path.exists():
            file_path = path

            break

    if file_path is None:
        print("\nGarak dataset not found.")

        return empty_dataset()

    print(f"\nLoading Garak:\n{file_path}")

    df = pd.read_csv(file_path)

    possible_text_columns = [
        "text",
        "prompt",
        "attack",
    ]

    text_column = None

    for column in possible_text_columns:
        if column in df.columns:
            text_column = column

            break

    if text_column is None:
        raise ValueError("Could not find a prompt/text column in Garak dataset.")

    result = pd.DataFrame({"text": df[text_column].astype(str), "label": [1] * len(df)})

    result["label"] = result["label"].astype(int)

    result = clean_dataset(result)

    print(f"Loaded {len(result)} Garak attacks.")

    return result


# ============================================================
# BUILD TRAINING DATASET
# ============================================================


def build_dataset(dataset_type):

    synthetic = load_synthetic_dataset()

    if dataset_type == "synthetic":
        print("\nUsing synthetic dataset only.")

        return synthetic

    if dataset_type == "combined":
        hackaprompt = load_hackaprompt()

        garak = load_garak()

        print("\nCombining datasets...")

        df = pd.concat(
            [
                synthetic,
                hackaprompt,
                garak,
            ],
            ignore_index=True,
        )

        df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)

        invalid_labels = set(df["label"].unique()) - {0, 1}

        if invalid_labels:
            raise ValueError(f"Invalid labels found: {invalid_labels}")

        before = len(df)

        df = df.drop_duplicates(subset=["text"])

        after = len(df)

        print(f"Removed duplicate prompts: {before - after}")

        df = df.sample(frac=1, random_state=42).reset_index(drop=True)

        print(f"\nTotal combined examples: {len(df)}")

        print("\nCombined label distribution:")

        print(df["label"].value_counts().sort_index())

        return df

    raise ValueError(f"Unknown dataset type: {dataset_type}")


# ============================================================
# TRAIN MODEL
# ============================================================


def train_model(dataset_type):

    print("\n" + "=" * 60)

    print("TRAINING ML PROMPT INJECTION DETECTOR")

    print("=" * 60)

    df = build_dataset(dataset_type)

    print("\nDataset distribution:")

    print(df["label"].value_counts().sort_index())

    if df["label"].nunique() < 2:
        raise ValueError("Training requires both benign (0) and attack (1) examples.")

    X = df["text"]

    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    print(f"\nTraining examples: {len(X_train)}")

    print(f"Testing examples: {len(X_test)}")

    print("\nTraining TF-IDF vectorizer...")

    vectorizer = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        sublinear_tf=True,
        max_features=100000,
    )

    X_train_tfidf = vectorizer.fit_transform(X_train)

    X_test_tfidf = vectorizer.transform(X_test)

    print(f"TF-IDF vocabulary size: {len(vectorizer.vocabulary_)}")

    print("\nTraining Logistic Regression...")

    classifier = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)

    classifier.fit(X_train_tfidf, y_train)

    probabilities = classifier.predict_proba(X_test_tfidf)[:, 1]

    threshold = 0.50

    predictions = (probabilities >= threshold).astype(int)

    accuracy = accuracy_score(y_test, predictions)

    precision = precision_score(y_test, predictions, zero_division=0)

    recall = recall_score(y_test, predictions, zero_division=0)

    f1 = f1_score(y_test, predictions, zero_division=0)

    cm = confusion_matrix(y_test, predictions, labels=[0, 1])

    tn, fp, fn, tp = cm.ravel()

    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

    print("\n" + "=" * 60)

    print("MODEL RESULTS")

    print("=" * 60)

    print(f"Accuracy:  {accuracy * 100:.2f}%")

    print(f"Precision: {precision * 100:.2f}%")

    print(f"Recall:    {recall * 100:.2f}%")

    print(f"F1 Score:  {f1 * 100:.2f}%")

    print(f"False Positive Rate: {fpr * 100:.2f}%")

    print(f"False Negative Rate: {fnr * 100:.2f}%")

    print("\nConfusion Matrix:")

    print(cm)

    print("\nClassification Report:")

    print(
        classification_report(
            y_test, predictions, labels=[0, 1], target_names=["Benign", "Attack"], zero_division=0
        )
    )

    with open(VECTORIZER_PATH, "wb") as f:
        pickle.dump(vectorizer, f)

    with open(CLASSIFIER_PATH, "wb") as f:
        pickle.dump(classifier, f)

    metrics = {
        "timestamp": datetime.now(UTC).isoformat(),
        "dataset": dataset_type,
        "total_examples": int(len(df)),
        "training_examples": int(len(X_train)),
        "testing_examples": int(len(X_test)),
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "false_positive_rate": float(fpr),
        "false_negative_rate": float(fnr),
        "threshold": threshold,
        "confusion_matrix": {
            "true_negative": int(tn),
            "false_positive": int(fp),
            "false_negative": int(fn),
            "true_positive": int(tp),
        },
    }

    with open(TRAINING_METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4)

    print(f"\nModel saved to:\n{VECTORIZER_PATH}\n{CLASSIFIER_PATH}")

    print(f"\nMetrics saved to:\n{TRAINING_METRICS_PATH}")


# ============================================================
# LOAD TRAINED MODEL
# ============================================================


def load_model():

    if not VECTORIZER_PATH.exists():
        raise FileNotFoundError(
            f"Vectorizer not found:\n"
            f"{VECTORIZER_PATH}\n\n"
            "Train the model first using:\n"
            "python src/ml_detector.py "
            "train --dataset synthetic"
        )

    if not CLASSIFIER_PATH.exists():
        raise FileNotFoundError(
            f"Classifier not found:\n"
            f"{CLASSIFIER_PATH}\n\n"
            "Train the model first using:\n"
            "python src/ml_detector.py "
            "train --dataset synthetic"
        )

    # Integrity gate before deserialization: the artifact's SHA-256 must match
    # the provenance manifest (see src/model_loader.py, Operating Rules 8/9).
    # This does not make pickle safe, but it prevents loading a swapped/tampered
    # blob from the fixed model paths.
    from model_loader import verify_artifact

    verify_artifact(VECTORIZER_PATH)
    verify_artifact(CLASSIFIER_PATH)

    vectorizer = _load_pickle_version_checked(VECTORIZER_PATH)
    classifier = _load_pickle_version_checked(CLASSIFIER_PATH)

    return (vectorizer, classifier)


def _load_pickle_version_checked(path):
    """Load a pickled sklearn object, FAILING CLOSED on a version mismatch.

    Audit B1: the committed artifacts were serialized with a different
    scikit-learn version and produce INVALID predictions when unpickled under
    another version. Rather than silently returning a broken model (and emitting
    meaningless metrics), treat scikit-learn's InconsistentVersionWarning as an
    error and refuse, with an actionable regenerate message.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", InconsistentVersionWarning)
        try:
            with open(path, "rb") as f:
                return pickle.load(f)  # nosec B301
        except InconsistentVersionWarning as exc:
            raise RuntimeError(
                f"Refusing to use '{Path(path).name}': it was serialized with a "
                f"different scikit-learn version and is not reproducible under the "
                f"installed version ({exc}). Regenerate the model with "
                f"`python src/ml_detector.py train --dataset synthetic` "
                f"(requires the training data — see datasets/README.md)."
            ) from exc


# ============================================================
# CALCULATE METRICS
# ============================================================


def calculate_metrics(y_true, y_pred):

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    tn, fp, fn, tp = cm.ravel()

    precision = precision_score(y_true, y_pred, zero_division=0)

    recall = recall_score(y_true, y_pred, zero_division=0)

    f1 = f1_score(y_true, y_pred, zero_division=0)

    accuracy = accuracy_score(y_true, y_pred)

    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0

    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "false_positive_rate": float(fpr),
        "false_negative_rate": float(fnr),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }


# ============================================================
# EVALUATE ON HELD-OUT DATASET
# ============================================================


def evaluate_model(dataset_path, threshold):

    print("\n" + "=" * 70)

    print("EVALUATING ML DETECTOR ON HELD-OUT DATASET")

    print("=" * 70)

    dataset_path = Path(dataset_path)

    if not dataset_path.is_absolute():
        dataset_path = BASE_DIR / dataset_path

    if not dataset_path.exists():
        raise FileNotFoundError(f"Evaluation dataset not found:\n{dataset_path}")

    print(f"Dataset:\n{dataset_path}")

    df = pd.read_csv(dataset_path)

    required_columns = {
        "text",
        "label",
    }

    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(f"Evaluation dataset is missing required columns: {missing}")

    # Keep metadata if available

    evaluation_columns = [
        "id",
        "text",
        "label",
        "attack_type",
        "difficulty",
        "language",
        "source",
        "notes",
    ]

    available_columns = [column for column in evaluation_columns if column in df.columns]

    df = df[available_columns].copy()

    df = df.dropna(subset=["text", "label"])

    df["text"] = df["text"].astype(str).str.strip()

    df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)

    invalid_labels = set(df["label"].unique()) - {0, 1}

    if invalid_labels:
        raise ValueError(f"Invalid labels: {invalid_labels}")

    print(f"\nEvaluation examples: {len(df)}")

    print("\nEvaluation label distribution:")

    print(df["label"].value_counts().sort_index())

    vectorizer, classifier = load_model()

    texts = df["text"].tolist()

    y_true = df["label"].to_numpy()

    print("\nRunning predictions...")

    latencies_ms = []

    probabilities = []

    predictions = []

    for text in texts:
        start = time.perf_counter()

        vector = vectorizer.transform([text])

        probability = classifier.predict_proba(vector)[0][1]

        prediction = int(probability >= threshold)

        end = time.perf_counter()

        latency_ms = (end - start) * 1000

        latencies_ms.append(latency_ms)

        probabilities.append(float(probability))

        predictions.append(prediction)

    y_pred = pd.Series(predictions).to_numpy()

    overall = calculate_metrics(y_true, y_pred)

    # --------------------------------------------------------
    # Latency
    # --------------------------------------------------------

    latency_series = pd.Series(latencies_ms)

    median_latency = latency_series.median()

    p95_latency = latency_series.quantile(0.95)

    total_time_seconds = sum(latencies_ms) / 1000

    throughput = len(texts) / total_time_seconds if total_time_seconds > 0 else 0

    # --------------------------------------------------------
    # Per-category metrics
    # --------------------------------------------------------

    per_category = {}

    if "attack_type" in df.columns:
        for category in sorted(df["attack_type"].dropna().unique()):
            mask = df["attack_type"] == category

            category_true = y_true[mask]

            category_pred = y_pred[mask]

            per_category[category] = {
                "samples": int(mask.sum()),
                **calculate_metrics(category_true, category_pred),
            }

    # --------------------------------------------------------
    # Save row-level predictions
    # --------------------------------------------------------

    prediction_df = df.copy()

    prediction_df["attack_probability"] = probabilities

    prediction_df["predicted_label"] = predictions

    prediction_df["correct"] = prediction_df["label"] == prediction_df["predicted_label"]

    prediction_output_path = RESULTS_DIR / "ml_detector_eval_predictions.csv"

    prediction_df.to_csv(prediction_output_path, index=False)

    # --------------------------------------------------------
    # Build results
    # --------------------------------------------------------

    results = {
        "experiment": {
            "name": "ML Detector Held-Out Evaluation",
            "timestamp": datetime.now(UTC).isoformat(),
            "dataset": str(dataset_path),
            "total_samples": int(len(df)),
            "threshold": float(threshold),
            "model": "TF-IDF + Logistic Regression",
            "vectorizer": "TfidfVectorizer",
            "ngram_range": [1, 2],
            "platform": platform.platform(),
            "python_version": sys.version,
        },
        "overall_metrics": overall,
        "latency_ms": {
            "median": float(median_latency),
            "p95": float(p95_latency),
            "mean": float(latency_series.mean()),
            "min": float(latency_series.min()),
            "max": float(latency_series.max()),
        },
        "throughput": {
            "samples_per_second": float(throughput),
            "total_prediction_time_seconds": float(total_time_seconds),
        },
        "per_category": per_category,
        "prediction_output": str(prediction_output_path),
    }

    with open(EVALUATION_METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    # --------------------------------------------------------
    # Print results
    # --------------------------------------------------------

    print("\n" + "=" * 70)

    print("HELD-OUT EVALUATION RESULTS")

    print("=" * 70)

    print(f"Accuracy:  {overall['accuracy'] * 100:.2f}%")

    print(f"Precision: {overall['precision'] * 100:.2f}%")

    print(f"Recall:    {overall['recall'] * 100:.2f}%")

    print(f"F1 Score:  {overall['f1'] * 100:.2f}%")

    print(f"FPR:       {overall['false_positive_rate'] * 100:.2f}%")

    print(f"FNR:       {overall['false_negative_rate'] * 100:.2f}%")

    print("\nConfusion Matrix:")

    print(f"TN: {overall['true_negative']}")

    print(f"FP: {overall['false_positive']}")

    print(f"FN: {overall['false_negative']}")

    print(f"TP: {overall['true_positive']}")

    print(f"\nMedian latency: {median_latency:.3f} ms")

    print(f"P95 latency: {p95_latency:.3f} ms")

    print(f"Throughput: {throughput:.2f} samples/sec")

    # --------------------------------------------------------
    # Category results
    # --------------------------------------------------------

    if per_category:
        print("\n" + "=" * 70)

        print("PER-CATEGORY RESULTS")

        print("=" * 70)

        for category, metrics in per_category.items():
            print(f"\n{category}")

            print(f"  Samples: {metrics['samples']}")

            print(f"  Precision: {metrics['precision'] * 100:.2f}%")

            print(f"  Recall: {metrics['recall'] * 100:.2f}%")

            print(f"  F1: {metrics['f1'] * 100:.2f}%")

            print(f"  FPR: {metrics['false_positive_rate'] * 100:.2f}%")

            print(f"  FNR: {metrics['false_negative_rate'] * 100:.2f}%")

    print("\nResults saved to:")

    print(EVALUATION_METRICS_PATH)

    print("\nRow-level predictions saved to:")

    print(prediction_output_path)


# ============================================================
# INTERACTIVE TESTING
# ============================================================


def interactive_test():

    print("\nLoading trained model...")

    vectorizer, classifier = load_model()

    print("\n" + "=" * 60)

    print("INTERACTIVE PROMPT INJECTION DETECTOR")

    print("Type 'exit' or 'quit' to stop.")

    print("=" * 60)

    while True:
        try:
            text = input("\nEnter prompt: ")

        except KeyboardInterrupt, EOFError:
            print("\n\nExiting...")

            break

        if text.lower().strip() in ["exit", "quit"]:
            print("\nExiting detector...")

            break

        if not text.strip():
            print("Please enter a prompt.")

            continue

        vector = vectorizer.transform([text])

        probability = classifier.predict_proba(vector)[0][1]

        prediction = probability >= 0.50

        print(f"\nAttack probability: {probability * 100:.2f}%")

        if prediction:
            print("RESULT: PROMPT INJECTION DETECTED")

        else:
            print("RESULT: BENIGN")


# ============================================================
# MAIN
# ============================================================


def main():

    parser = argparse.ArgumentParser(description=("ML-based Prompt Injection Detector"))

    subparsers = parser.add_subparsers(dest="command")

    # ========================================================
    # TRAIN
    # ========================================================

    train_parser = subparsers.add_parser("train", help=("Train the ML detector"))

    train_parser.add_argument(
        "--dataset",
        choices=["synthetic", "combined"],
        default="synthetic",
        help=("Training dataset source"),
    )

    # ========================================================
    # EVALUATE
    # ========================================================

    evaluate_parser = subparsers.add_parser(
        "evaluate", help=("Evaluate trained detector on held-out dataset")
    )

    evaluate_parser.add_argument(
        "--dataset", required=True, help=("Path to held-out evaluation CSV")
    )

    evaluate_parser.add_argument(
        "--threshold",
        type=float,
        default=0.50,
        help=("Attack probability threshold (default: 0.50)"),
    )

    # ========================================================
    # TEST
    # ========================================================

    subparsers.add_parser("test", help=("Run interactive testing"))

    # ========================================================
    # PARSE
    # ========================================================

    args = parser.parse_args()

    # ========================================================
    # EXECUTE
    # ========================================================

    if args.command == "train":
        train_model(args.dataset)

    elif args.command == "evaluate":
        if not (0.0 <= args.threshold <= 1.0):
            raise ValueError("Threshold must be between 0.0 and 1.0.")

        evaluate_model(args.dataset, args.threshold)

    elif args.command == "test":
        interactive_test()

    else:
        parser.print_help()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
