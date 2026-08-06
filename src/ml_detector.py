"""
ML-Based Prompt Injection Detector (merged / production version)

Project:
    Prompt Injection Detection and Defence for LLM-Based Applications

Model:
    TF-IDF + Logistic Regression

-------------------------------------------------------------------
WHAT THIS FILE IS
-------------------------------------------------------------------
This merges the two prior detector scripts into one implementation:

  - ml_detector.py  (tagged models, augmented datasets, leakage guard,
                      schema-normalizing loaders)   -> kept as the base
  - ml_detector1.py (simpler baseline train/evaluate/test flow)
                      -> functionality folded in, nothing lost

On top of that it adds the two pieces needed for the results table
(Benchmark | System | Accuracy(mean+/-std) | F1 | FPR | McNemar):

  - 5-fold Stratified Cross-Validation  (--command crossval)
  - McNemar's exact test between two prediction files (--command mcnemar)

NOTE ON SECURITY: a previous version of this file (ml_detector.py, as
uploaded) contained commented-out text at the very bottom attempting a
multilingual prompt-injection / "reveal the admin password" payload
aimed at any AI assistant reading the file. That text has been
deliberately removed and NOT carried into this version. If you did not
add that yourself, flag it to your supervisor before this file goes
into the submission repo.

-------------------------------------------------------------------
DATASETS
-------------------------------------------------------------------
Core synthetic:
    datasets/prompt_injection_500.csv   (attacks)
    datasets/benign_500.csv             (benign)

Optional, auto-detected if present:
    datasets/hackaprompt.csv | hackaprompt_dataset.csv | HackAPrompt.csv
    datasets/garak_attacks.csv | garak_prompts.csv
    datasets/synthetic_augmented_train.csv
    datasets/synthetic_augmented_train_v2.csv
    datasets/multilingual*.csv          (any file matching this glob)

Held-out evaluation (never used for training):
    datasets/eval_dataset_v2.csv
    Expected columns: id, text, label, attack_type, difficulty,
                       language, source, notes

Labels:
    0 = Benign
    1 = Prompt Injection Attack

-------------------------------------------------------------------
DATASET MODES (--dataset)
-------------------------------------------------------------------
    synthetic            prompt_injection_500 + benign_500 only (baseline)
    combined             synthetic + HackAPrompt (if present) + Garak (if present)
    augmented            synthetic + synthetic_augmented_train.csv
    augmented_v2         synthetic + synthetic_augmented_train_v2.csv
    augmented_combined   synthetic + both augmented files
    multilingual         synthetic + datasets/multilingual*.csv files
    multilingual_combined  synthetic + augmented v1 + v2 + multilingual*.csv
    all                   every dataset above, merged and de-duplicated

Each mode trains and saves to its OWN tagged model/result files
(experiments/models/vectorizer_<tag>.pkl, classifier_<tag>.pkl,
experiments/results/ml_detector_training_results_<tag>.json) so that
training e.g. "augmented" can never silently overwrite "synthetic".
Use --model-tag to override the tag with a custom name.

-------------------------------------------------------------------
LEAKAGE GUARD
-------------------------------------------------------------------
Before training on any dataset type other than "synthetic", this
script checks (case/whitespace-normalized exact-text match) whether
any training example also appears in datasets/eval_dataset_v2.csv.
If overlap is found, training stops with an error listing the
offending rows, unless --allow-eval-overlap is explicitly passed.
This is a safety net, not a substitute for fuzzy/near-duplicate
checking, which this script does not perform.

-------------------------------------------------------------------
COMMANDS
-------------------------------------------------------------------
Train (baseline):
    python ml_detector.py train --dataset synthetic

Train on everything available:
    python ml_detector.py train --dataset all

Evaluate a tagged model on the held-out set:
    python ml_detector.py evaluate --dataset datasets/eval_dataset_v2.csv --model synthetic
    python ml_detector.py evaluate --dataset datasets/eval_dataset_v2.csv --model all --threshold 0.5

5-fold stratified cross-validation (produces the mean+/-std row for the table):
    python ml_detector.py crossval --dataset synthetic --folds 5
    python ml_detector.py crossval --dataset all --folds 5 --eval-dataset datasets/eval_dataset_v2.csv

McNemar's test between two systems' predictions on the SAME eval set:
    python ml_detector.py mcnemar \
        --pred-a experiments/results/ml_detector_eval_predictions_piguard.csv \
        --pred-b experiments/results/ml_detector_eval_predictions_all.csv \
        --label-a "PIGuard raw" --label-b "HardenedGuard (Ours)"

Interactive testing with a specific tagged model:
    python ml_detector.py test --model all

-------------------------------------------------------------------
REQUIRED PIP INSTALLS
-------------------------------------------------------------------
    pip install pandas scikit-learn statsmodels
"""

import argparse
import glob
import json
import pickle
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)
from sklearn.model_selection import train_test_split, StratifiedKFold

try:
    from statsmodels.stats.contingency_tables import mcnemar as sm_mcnemar
except ImportError:  # pragma: no cover
    sm_mcnemar = None


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent if (
    Path(__file__).resolve().parent.name == "src"
) else Path(__file__).resolve().parent

DATASETS_DIR = BASE_DIR / "datasets"
MODELS_DIR = BASE_DIR / "experiments" / "models"
RESULTS_DIR = BASE_DIR / "experiments" / "results"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# DATASET FILES
# ============================================================

SYNTHETIC_ATTACKS = DATASETS_DIR / "prompt_injection_500.csv"
SYNTHETIC_BENIGN = DATASETS_DIR / "benign_500.csv"

AUGMENTED_V1_PATH = DATASETS_DIR / "synthetic_augmented_train.csv"
AUGMENTED_V2_PATH = DATASETS_DIR / "synthetic_augmented_train_v2.csv"

# Used ONLY for the leakage guard (transient membership check).
# Never loaded into a training frame.
EVAL_DATASET_DEFAULT_PATH = DATASETS_DIR / "eval_dataset_v2.csv"

VALID_DATASET_TYPES = [
    "synthetic",
    "combined",
    "augmented",
    "augmented_v2",
    "augmented_combined",
    "multilingual",
    "multilingual_combined",
    "all",
]


# ============================================================
# TAGGED MODEL / RESULT FILE PATHS
# (prevents one run from overwriting another's outputs)
# ============================================================

def vectorizer_path(tag):
    return MODELS_DIR / f"vectorizer_{tag}.pkl"


def classifier_path(tag):
    return MODELS_DIR / f"classifier_{tag}.pkl"


def training_metrics_path(tag):
    return RESULTS_DIR / f"ml_detector_training_results_{tag}.json"


def eval_metrics_path(tag):
    return RESULTS_DIR / f"ml_detector_eval_results_{tag}.json"


def eval_predictions_path(tag):
    return RESULTS_DIR / f"ml_detector_eval_predictions_{tag}.csv"


def crossval_metrics_path(tag):
    return RESULTS_DIR / f"ml_detector_crossval_results_{tag}.json"


def mcnemar_result_path(label_a, label_b):
    safe_a = "".join(c if c.isalnum() else "_" for c in label_a)
    safe_b = "".join(c if c.isalnum() else "_" for c in label_b)
    return RESULTS_DIR / f"mcnemar_{safe_a}_vs_{safe_b}.json"


# ============================================================
# HELPER: EMPTY DATAFRAME
# ============================================================

def empty_dataset():
    return pd.DataFrame(columns=["text", "label"])


# ============================================================
# HELPER: CLEAN A text/label DATASET
# ============================================================

def clean_dataset(df, source_name="dataset"):
    """
    Clean a binary classification dataset.
    Required columns: text, label. Labels: 0 = benign, 1 = attack.
    """
    required_columns = {"text", "label"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"[{source_name}] Missing required columns: {missing_columns}")

    df = df[["text", "label"]].copy()
    df = df.dropna(subset=["text"])
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"] != ""]

    df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)

    invalid_labels = set(df["label"].unique()) - {0, 1}
    if invalid_labels:
        raise ValueError(
            f"[{source_name}] Invalid labels found: {invalid_labels}. Labels must be 0 or 1."
        )

    before = len(df)
    df = df.drop_duplicates(subset=["text"])
    after = len(df)
    print(f"[{source_name}] Removed duplicate texts within source: {before - after}")

    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    return df


# ============================================================
# HELPER: NORMALIZE AN ARBITRARY FILE'S COLUMN SCHEMA
# ============================================================

def normalize_columns(df, source_name):
    """
    Different dataset files (augmented, multilingual, third-party) may use
    different column names than the core pipeline. This maps common
    variants onto standard names rather than assuming a fixed schema.
    Raises a clear error if a required column cannot be found, instead of
    silently guessing labels.
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    text_candidates = ["text", "prompt", "attack", "input", "sample"]
    label_candidates = ["label", "is_attack", "target", "class"]
    attack_type_candidates = ["attack_type", "category", "type"]
    language_candidates = ["language", "lang"]

    def find_column(candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    text_col = find_column(text_candidates)
    label_col = find_column(label_candidates)
    attack_type_col = find_column(attack_type_candidates)
    language_col = find_column(language_candidates)

    if text_col is None:
        raise ValueError(
            f"[{source_name}] Could not find a text column. Expected one of: {text_candidates}"
        )

    if label_col is None:
        raise ValueError(
            f"[{source_name}] Could not find a label column. Expected one of: "
            f"{label_candidates}. Refusing to assume all rows are attacks — add an "
            "explicit label column (0 = benign, 1 = attack) to this file."
        )

    rename_map = {text_col: "text", label_col: "label"}
    if attack_type_col:
        rename_map[attack_type_col] = "attack_type"
    if language_col:
        rename_map[language_col] = "language"

    df = df.rename(columns=rename_map)

    if "attack_type" in df.columns:
        print(f"\n[{source_name}] attack_type distribution:")
        print(df["attack_type"].value_counts())

    if "language" in df.columns:
        print(f"\n[{source_name}] language distribution:")
        print(df["language"].value_counts())

    if "label" in df.columns:
        print(f"\n[{source_name}] label distribution (pre-clean):")
        print(df["label"].value_counts())

    return df


# ============================================================
# HELPER: LEAKAGE GUARD AGAINST HELD-OUT EVAL SET
# ============================================================

def _normalize_text_for_comparison(series):
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", " ", regex=True)
    )


def check_eval_leakage(df, source_name, allow_overlap=False,
                        eval_path=EVAL_DATASET_DEFAULT_PATH):
    """
    Case/whitespace-normalized EXACT text match check against the held-out
    evaluation dataset. This is a safety net, not a full near-duplicate /
    fuzzy detector — it will not catch paraphrased or lightly-edited
    overlaps. eval_dataset_v2.csv is read here ONLY to compare text
    values; it is never merged into any training frame.
    """
    eval_path = Path(eval_path)

    if not eval_path.exists():
        print(
            f"\n[leakage guard] Held-out eval file not found at {eval_path} — "
            f"skipping leakage check for {source_name}. Proceed with caution."
        )
        return

    eval_df = pd.read_csv(eval_path)
    if "text" not in eval_df.columns:
        print(f"\n[leakage guard] {eval_path} has no 'text' column — skipping check.")
        return

    eval_texts = set(_normalize_text_for_comparison(eval_df["text"]))
    candidate_texts = _normalize_text_for_comparison(df["text"])

    overlap_mask = candidate_texts.isin(eval_texts)
    overlap_count = int(overlap_mask.sum())

    if overlap_count == 0:
        print(f"[leakage guard] {source_name}: no exact-text overlap with {eval_path.name}.")
        return

    print(
        f"\n[leakage guard] WARNING: {overlap_count} row(s) in {source_name} exactly "
        f"match text in {eval_path.name} (case/whitespace-normalized)."
    )
    print(df.loc[overlap_mask, "text"].head(10).to_string(index=False))

    if not allow_overlap:
        raise RuntimeError(
            f"Refusing to train: {overlap_count} row(s) in {source_name} overlap with "
            f"the held-out evaluation dataset. Remove these rows from {source_name}, or "
            "re-run with --allow-eval-overlap if you have manually verified this is not "
            "a leakage risk (not recommended)."
        )

    print(
        "[leakage guard] --allow-eval-overlap set: proceeding despite detected overlap. "
        "Results should be treated with caution."
    )


# ============================================================
# LOAD SYNTHETIC DATASET (core, always required)
# ============================================================

def load_synthetic_dataset():
    print("\nLoading synthetic attack dataset...")
    if not SYNTHETIC_ATTACKS.exists():
        raise FileNotFoundError(f"Attack dataset not found:\n{SYNTHETIC_ATTACKS}")
    attacks = pd.read_csv(SYNTHETIC_ATTACKS)
    print(f"Attack examples loaded: {len(attacks)}")

    print("\nLoading synthetic benign dataset...")
    if not SYNTHETIC_BENIGN.exists():
        raise FileNotFoundError(f"Benign dataset not found:\n{SYNTHETIC_BENIGN}")
    benign = pd.read_csv(SYNTHETIC_BENIGN)
    print(f"Benign examples loaded: {len(benign)}")

    attacks = attacks[["text"]].copy()
    benign = benign[["text"]].copy()
    attacks["label"] = 1
    benign["label"] = 0

    df = pd.concat([attacks, benign], ignore_index=True)
    return clean_dataset(df, source_name="synthetic")


# ============================================================
# LOAD HACKAPROMPT (optional)
# ============================================================

def load_hackaprompt():
    print("\nSearching for HackAPrompt dataset...")
    possible_files = [
        DATASETS_DIR / "hackaprompt.csv",
        DATASETS_DIR / "hackaprompt_dataset.csv",
        DATASETS_DIR / "HackAPrompt.csv",
    ]
    file_path = next((p for p in possible_files if p.exists()), None)
    if file_path is None:
        print("HackAPrompt CSV not found. Continuing without it.")
        return empty_dataset()

    print(f"Loading HackAPrompt:\n{file_path}")
    df = pd.read_csv(file_path)
    text_col = next((c for c in ["text", "prompt", "attack", "instruction"] if c in df.columns), None)
    if text_col is None:
        raise ValueError("Could not find a prompt/text column in HackAPrompt dataset.")

    result = pd.DataFrame({"text": df[text_col].astype(str), "label": [1] * len(df)})
    result["label"] = result["label"].astype(int)
    return clean_dataset(result, source_name="hackaprompt")


# ============================================================
# LOAD GARAK (optional)
# ============================================================

def load_garak():
    possible_files = [DATASETS_DIR / "garak_attacks.csv", DATASETS_DIR / "garak_prompts.csv"]
    file_path = next((p for p in possible_files if p.exists()), None)
    if file_path is None:
        print("\nGarak dataset not found.")
        return empty_dataset()

    print(f"\nLoading Garak:\n{file_path}")
    df = pd.read_csv(file_path)
    text_col = next((c for c in ["text", "prompt", "attack"] if c in df.columns), None)
    if text_col is None:
        raise ValueError("Could not find a prompt/text column in Garak dataset.")

    result = pd.DataFrame({"text": df[text_col].astype(str), "label": [1] * len(df)})
    result["label"] = result["label"].astype(int)
    result = clean_dataset(result, source_name="garak")
    print(f"Loaded {len(result)} Garak attacks.")
    return result


# ============================================================
# LOAD A GENERIC SCHEMA-NORMALIZING FILE (augmented / multilingual / other)
# ============================================================

def load_generic_file(path, source_name, allow_overlap=False):
    if not path.exists():
        print(f"\nWARNING: dataset not found: {path}")
        print(f"Continuing without {source_name}.")
        return empty_dataset()

    print(f"\nLoading {source_name}:\n{path}")
    raw_df = pd.read_csv(path)
    print(f"Rows loaded (pre-clean): {len(raw_df)}")

    normalized_df = normalize_columns(raw_df, source_name)

    # Leakage check runs BEFORE dedup/cleaning so nothing slips through.
    check_eval_leakage(normalized_df, source_name, allow_overlap=allow_overlap)

    result = clean_dataset(normalized_df[["text", "label"]].copy(), source_name=source_name)

    print(f"\n{source_name} final label distribution (post-clean):")
    print(result["label"].value_counts().sort_index())
    return result


def load_augmented_v1(allow_overlap=False):
    return load_generic_file(AUGMENTED_V1_PATH, "synthetic_augmented_train.csv", allow_overlap)


def load_augmented_v2(allow_overlap=False):
    return load_generic_file(AUGMENTED_V2_PATH, "synthetic_augmented_train_v2.csv", allow_overlap)


def discover_multilingual_files():
    """Any datasets/multilingual*.csv file is picked up automatically."""
    return sorted(Path(p) for p in glob.glob(str(DATASETS_DIR / "multilingual*.csv")))


def load_multilingual_files(allow_overlap=False):
    files = discover_multilingual_files()
    if not files:
        print("\nNo datasets/multilingual*.csv files found. Continuing without them.")
        return empty_dataset()

    frames = []
    for path in files:
        frame = load_generic_file(path, path.name, allow_overlap=allow_overlap)
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return empty_dataset()

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)
    return df


# ============================================================
# STATS HELPER
# ============================================================

def print_dataset_stats(df, label):
    total = len(df)
    attacks = int((df["label"] == 1).sum())
    benign = int((df["label"] == 0).sum())
    print(f"\n{'=' * 60}")
    print(f"DATASET STATS: {label}")
    print("=" * 60)
    print(f"Total examples:  {total}")
    print(f"Attack examples: {attacks}")
    print(f"Benign examples: {benign}")


# ============================================================
# BUILD TRAINING DATASET
# ============================================================

def build_dataset(dataset_type, allow_overlap=False):
    if dataset_type not in VALID_DATASET_TYPES:
        raise ValueError(
            f"Unknown dataset type: {dataset_type}. Choose from: {', '.join(VALID_DATASET_TYPES)}"
        )

    synthetic = load_synthetic_dataset()

    if dataset_type == "synthetic":
        print_dataset_stats(synthetic, "synthetic")
        return synthetic

    if dataset_type == "combined":
        frames = [synthetic]
        for frame in (load_hackaprompt(), load_garak()):
            if not frame.empty:
                frames.append(frame)
        df = pd.concat(frames, ignore_index=True)
        df = df.drop_duplicates(subset=["text"]).sample(frac=1, random_state=42).reset_index(drop=True)
        print_dataset_stats(df, "combined")
        return df

    frames = [synthetic]
    label_parts = ["synthetic"]

    if dataset_type in ("augmented", "augmented_combined", "all"):
        v1 = load_augmented_v1(allow_overlap=allow_overlap)
        if not v1.empty:
            frames.append(v1)
            label_parts.append("augmented_v1")

    if dataset_type in ("augmented_v2", "augmented_combined", "all"):
        v2 = load_augmented_v2(allow_overlap=allow_overlap)
        if not v2.empty:
            frames.append(v2)
            label_parts.append("augmented_v2")

    if dataset_type in ("multilingual", "multilingual_combined", "all"):
        multi = load_multilingual_files(allow_overlap=allow_overlap)
        if not multi.empty:
            frames.append(multi)
            label_parts.append("multilingual")

    if dataset_type == "all":
        for frame in (load_hackaprompt(), load_garak()):
            if not frame.empty:
                frames.append(frame)
                label_parts.append("hackaprompt_or_garak")

    df = pd.concat(frames, ignore_index=True)
    before = len(df)
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)
    after = len(df)
    print(f"\nRemoved duplicate texts across ({' + '.join(label_parts)}): {before - after}")

    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    print_dataset_stats(df, dataset_type)
    return df


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
# TRAIN MODEL (single train/test split, saves the deployable model)
# ============================================================

def train_model(dataset_type, model_tag=None, allow_overlap=False):
    tag = model_tag or dataset_type
    print("\n" + "=" * 60)
    print(f"TRAINING ML PROMPT INJECTION DETECTOR (tag: {tag})")
    print("=" * 60)

    df = build_dataset(dataset_type, allow_overlap=allow_overlap)
    if df["label"].nunique() < 2:
        raise ValueError("Training requires both benign (0) and attack (1) examples.")

    X, y = df["text"], df["label"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"\nTraining examples: {len(X_train)}")
    print(f"Testing examples:  {len(X_test)}")

    vectorizer = TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2), min_df=2, max_df=0.95,
        sublinear_tf=True, max_features=100000,
    )
    X_train_tfidf = vectorizer.fit_transform(X_train)
    X_test_tfidf = vectorizer.transform(X_test)
    print(f"TF-IDF vocabulary size: {len(vectorizer.vocabulary_)}")

    classifier = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    classifier.fit(X_train_tfidf, y_train)

    probabilities = classifier.predict_proba(X_test_tfidf)[:, 1]
    predictions = (probabilities >= 0.50).astype(int)
    metrics = calculate_metrics(y_test.to_numpy(), predictions)

    print("\n" + "=" * 60)
    print(f"MODEL RESULTS (tag: {tag})")
    print("=" * 60)
    for k in ("accuracy", "precision", "recall", "f1", "false_positive_rate", "false_negative_rate"):
        print(f"{k}: {metrics[k] * 100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test, predictions, labels=[0, 1],
                                 target_names=["Benign", "Attack"], zero_division=0))

    vec_path, clf_path = vectorizer_path(tag), classifier_path(tag)
    with open(vec_path, "wb") as f:
        pickle.dump(vectorizer, f)
    with open(clf_path, "wb") as f:
        pickle.dump(classifier, f)

    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_type": dataset_type,
        "model_tag": tag,
        "total_examples": int(len(df)),
        "training_examples": int(len(X_train)),
        "testing_examples": int(len(X_test)),
        "tfidf_vocabulary_size": int(len(vectorizer.vocabulary_)),
        "threshold": 0.50,
        **metrics,
    }
    metrics_path = training_metrics_path(tag)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=4)

    print(f"\nModel saved to:\n{vec_path}\n{clf_path}")
    print(f"Metrics saved to:\n{metrics_path}")
    print(f"NOTE: saved under tag '{tag}' — other tags are untouched.")


# ============================================================
# LOAD A TRAINED MODEL BY TAG
# ============================================================

def load_model(tag="synthetic"):
    vec_path, clf_path = vectorizer_path(tag), classifier_path(tag)
    if not vec_path.exists() or not clf_path.exists():
        raise FileNotFoundError(
            f"No trained model found for tag '{tag}'.\nExpected:\n{vec_path}\n{clf_path}\n\n"
            f"Train it first: python ml_detector.py train --dataset {tag}"
        )
    with open(vec_path, "rb") as f:
        vectorizer = pickle.load(f)
    with open(clf_path, "rb") as f:
        classifier = pickle.load(f)
    return vectorizer, classifier


# ============================================================
# EVALUATE A TAGGED MODEL ON A HELD-OUT DATASET
# ============================================================

def evaluate_model(dataset_path, threshold, model_tag="synthetic"):
    print("\n" + "=" * 70)
    print(f"EVALUATING ML DETECTOR (tag: {model_tag}) ON HELD-OUT DATASET")
    print("=" * 70)

    dataset_path = Path(dataset_path)
    if not dataset_path.is_absolute():
        dataset_path = BASE_DIR / dataset_path
    if not dataset_path.exists():
        raise FileNotFoundError(f"Evaluation dataset not found:\n{dataset_path}")

    df = pd.read_csv(dataset_path)
    missing = {"text", "label"} - set(df.columns)
    if missing:
        raise ValueError(f"Evaluation dataset is missing required columns: {missing}")

    keep_cols = [c for c in ["id", "text", "label", "attack_type", "difficulty",
                              "language", "source", "notes"] if c in df.columns]
    df = df[keep_cols].copy()
    df = df.dropna(subset=["text", "label"])
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)

    vectorizer, classifier = load_model(tag=model_tag)
    texts = df["text"].tolist()
    y_true = df["label"].to_numpy()

    latencies_ms, probabilities, predictions = [], [], []
    for text in texts:
        start = time.perf_counter()
        vector = vectorizer.transform([text])
        probability = classifier.predict_proba(vector)[0][1]
        prediction = int(probability >= threshold)
        latencies_ms.append((time.perf_counter() - start) * 1000)
        probabilities.append(float(probability))
        predictions.append(prediction)

    y_pred = np.array(predictions)
    overall = calculate_metrics(y_true, y_pred)

    latency_series = pd.Series(latencies_ms)
    per_category = {}
    if "attack_type" in df.columns:
        for category in sorted(df["attack_type"].dropna().unique()):
            mask = (df["attack_type"] == category).to_numpy()
            per_category[category] = {"samples": int(mask.sum()),
                                       **calculate_metrics(y_true[mask], y_pred[mask])}

    prediction_df = df.copy()
    prediction_df["attack_probability"] = probabilities
    prediction_df["predicted_label"] = predictions
    prediction_df["correct"] = prediction_df["label"] == prediction_df["predicted_label"]
    prediction_output_path = eval_predictions_path(model_tag)
    prediction_df.to_csv(prediction_output_path, index=False)

    results = {
        "experiment": {
            "name": "ML Detector Held-Out Evaluation",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dataset": str(dataset_path),
            "model_tag": model_tag,
            "total_samples": int(len(df)),
            "threshold": float(threshold),
            "model": "TF-IDF + Logistic Regression",
            "platform": platform.platform(),
            "python_version": sys.version,
        },
        "overall_metrics": overall,
        "latency_ms": {
            "median": float(latency_series.median()),
            "p95": float(latency_series.quantile(0.95)),
            "mean": float(latency_series.mean()),
        },
        "per_category": per_category,
        "prediction_output": str(prediction_output_path),
    }
    metrics_out_path = eval_metrics_path(model_tag)
    with open(metrics_out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    print(f"\nAccuracy: {overall['accuracy']*100:.2f}%  F1: {overall['f1']*100:.2f}%  "
          f"FPR: {overall['false_positive_rate']*100:.2f}%")
    print(f"Results saved to:\n{metrics_out_path}")
    print(f"Row-level predictions saved to:\n{prediction_output_path}")


# ============================================================
# 5-FOLD STRATIFIED CROSS-VALIDATION
# (produces the "Accuracy mean +/- std" row for the results table)
# ============================================================

def load_csv_for_crossval(csv_path):
    """
    Load an arbitrary external CSV (e.g. a downloaded benchmark like
    deepset_eval.csv) for cross-validation, using the same schema
    normalization as everything else in this script.
    """
    csv_path = Path(csv_path)
    if not csv_path.is_absolute():
        csv_path = BASE_DIR / csv_path
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found:\n{csv_path}")

    raw_df = pd.read_csv(csv_path)
    normalized = normalize_columns(raw_df, csv_path.name)
    return clean_dataset(normalized[["text", "label"]].copy(), source_name=csv_path.name)


def cross_validate_model(dataset_type, folds=5, model_tag=None, allow_overlap=False,
                          benchmark_name=None, dataset_csv=None):
    tag = model_tag or dataset_type
    print("\n" + "=" * 70)
    print(f"{folds}-FOLD STRATIFIED CROSS-VALIDATION (tag: {tag})")
    print("=" * 70)

    if dataset_csv:
        print(f"Running CV directly on external CSV: {dataset_csv}")
        df = load_csv_for_crossval(dataset_csv)
        print_dataset_stats(df, Path(dataset_csv).name)
    else:
        df = build_dataset(dataset_type, allow_overlap=allow_overlap)

    X = df["text"].to_numpy()
    y = df["label"].to_numpy()

    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)

    fold_metrics = []
    for fold_index, (train_idx, test_idx) in enumerate(skf.split(X, y), start=1):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        vectorizer = TfidfVectorizer(
            lowercase=True, ngram_range=(1, 2), min_df=2, max_df=0.95,
            sublinear_tf=True, max_features=100000,
        )
        X_train_tfidf = vectorizer.fit_transform(X_train)
        X_test_tfidf = vectorizer.transform(X_test)

        classifier = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
        classifier.fit(X_train_tfidf, y_train)

        probabilities = classifier.predict_proba(X_test_tfidf)[:, 1]
        predictions = (probabilities >= 0.50).astype(int)

        metrics = calculate_metrics(y_test, predictions)
        metrics["fold"] = fold_index
        fold_metrics.append(metrics)

        print(f"Fold {fold_index}: accuracy={metrics['accuracy']*100:.2f}%  "
              f"f1={metrics['f1']*100:.2f}%  fpr={metrics['false_positive_rate']*100:.2f}%")

    def agg(key):
        values = np.array([m[key] for m in fold_metrics])
        return float(values.mean()), float(values.std())

    acc_mean, acc_std = agg("accuracy")
    f1_mean, f1_std = agg("f1")
    fpr_mean, fpr_std = agg("false_positive_rate")

    total_tn = sum(m["true_negative"] for m in fold_metrics)
    total_fp = sum(m["false_positive"] for m in fold_metrics)
    total_fn = sum(m["false_negative"] for m in fold_metrics)
    total_tp = sum(m["true_positive"] for m in fold_metrics)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "benchmark_name": benchmark_name or dataset_type,
        "dataset_type": dataset_type,
        "model_tag": tag,
        "folds": folds,
        "n_samples": int(len(df)),
        "accuracy_mean": acc_mean,
        "accuracy_std": acc_std,
        "f1_mean": f1_mean,
        "f1_std": f1_std,
        "false_positive_rate_mean": fpr_mean,
        "false_positive_rate_std": fpr_std,
        "aggregate_confusion_matrix": {
            "true_negative": total_tn, "false_positive": total_fp,
            "false_negative": total_fn, "true_positive": total_tp,
        },
        "per_fold": fold_metrics,
        # Ready-to-paste row for the LaTeX/paper table:
        "table_row": {
            "Benchmark": benchmark_name or dataset_type,
            "System": f"HardenedGuard ({tag})",
            "Accuracy (mean±std)": f"{acc_mean:.3f} ± {acc_std:.3f}",
            "F1": f"{f1_mean:.3f}",
            "FPR": f"{fpr_mean:.3f}",
        },
    }

    out_path = crossval_metrics_path(tag)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=4)

    print("\n" + "=" * 70)
    print("CROSS-VALIDATION SUMMARY")
    print("=" * 70)
    print(f"Accuracy: {acc_mean:.3f} ± {acc_std:.3f}")
    print(f"F1:       {f1_mean:.3f}")
    print(f"FPR:      {fpr_mean:.3f}")
    print(f"\nTable row -> {summary['table_row']}")
    print(f"\nSaved to:\n{out_path}")


# ============================================================
# MCNEMAR'S TEST BETWEEN TWO SYSTEMS' PREDICTIONS
# ============================================================

def run_mcnemar_test(pred_path_a, pred_path_b, label_a="System A", label_b="System B"):
    """
    Compares two systems' predictions on the SAME held-out evaluation set.
    Both CSVs must come from evaluate_model() (or contain at minimum
    'text', 'label', 'predicted_label' columns) run on the identical
    eval_dataset_v2.csv, so rows can be matched by text.
    """
    if sm_mcnemar is None:
        raise ImportError(
            "statsmodels is required for McNemar's test. Install with:\n"
            "    pip install statsmodels"
        )

    print("\n" + "=" * 70)
    print(f"MCNEMAR'S TEST: {label_a}  vs  {label_b}")
    print("=" * 70)

    df_a = pd.read_csv(pred_path_a)
    df_b = pd.read_csv(pred_path_b)

    for name, frame in (("pred-a", df_a), ("pred-b", df_b)):
        missing = {"text", "label", "predicted_label"} - set(frame.columns)
        if missing:
            raise ValueError(f"{name} is missing required columns: {missing}")

    df_a = df_a[["text", "label", "predicted_label"]].rename(
        columns={"predicted_label": "pred_a"})
    df_b = df_b[["text", "label", "predicted_label"]].rename(
        columns={"predicted_label": "pred_b"})

    merged = df_a.merge(df_b, on=["text", "label"], how="inner")
    dropped = len(df_a) - len(merged)
    if dropped:
        print(f"WARNING: {dropped} row(s) in pred-a did not have a matching "
              f"text+label in pred-b and were excluded from the test.")
    if len(merged) == 0:
        raise ValueError(
            "No overlapping rows between the two prediction files — "
            "make sure both were evaluated on the same dataset."
        )

    correct_a = (merged["pred_a"] == merged["label"]).to_numpy()
    correct_b = (merged["pred_b"] == merged["label"]).to_numpy()

    n_both_correct = int(np.sum(correct_a & correct_b))
    n_a_only = int(np.sum(correct_a & ~correct_b))
    n_b_only = int(np.sum(~correct_a & correct_b))
    n_both_wrong = int(np.sum(~correct_a & ~correct_b))

    table = [[n_both_correct, n_a_only],
             [n_b_only, n_both_wrong]]

    result = sm_mcnemar(table, exact=(n_a_only + n_b_only) < 25, correction=True)

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label_a": label_a,
        "label_b": label_b,
        "pred_path_a": str(pred_path_a),
        "pred_path_b": str(pred_path_b),
        "n_samples_compared": int(len(merged)),
        "contingency_table": {
            "both_correct": n_both_correct,
            "a_correct_b_wrong": n_a_only,
            "b_correct_a_wrong": n_b_only,
            "both_wrong": n_both_wrong,
        },
        "statistic": float(result.statistic),
        "p_value": float(result.pvalue),
        "significant_at_0_05": bool(result.pvalue < 0.05),
    }

    out_path = mcnemar_result_path(label_a, label_b)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    print(f"\nSamples compared: {output['n_samples_compared']}")
    print(f"Contingency table: {output['contingency_table']}")
    print(f"McNemar statistic: {output['statistic']:.4f}")
    print(f"p-value: {output['p_value']:.6g}")
    print(f"Significant at p<0.05: {output['significant_at_0_05']}")
    print(f"\nSaved to:\n{out_path}")

    return output


# ============================================================
# INTERACTIVE TESTING
# ============================================================

def interactive_test(model_tag="synthetic"):
    print(f"\nLoading trained model (tag: {model_tag})...")
    vectorizer, classifier = load_model(tag=model_tag)

    print("\n" + "=" * 60)
    print(f"INTERACTIVE PROMPT INJECTION DETECTOR (tag: {model_tag})")
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 60)

    while True:
        try:
            text = input("\nEnter prompt: ")
        except (KeyboardInterrupt, EOFError):
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
        print("RESULT: PROMPT INJECTION DETECTED" if prediction else "RESULT: BENIGN")


# ============================================================
# MAIN / CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="ML-based Prompt Injection Detector")
    subparsers = parser.add_subparsers(dest="command")

    # TRAIN
    train_parser = subparsers.add_parser("train", help="Train the ML detector")
    train_parser.add_argument("--dataset", choices=VALID_DATASET_TYPES, default="synthetic")
    train_parser.add_argument("--model-tag", default=None)
    train_parser.add_argument("--allow-eval-overlap", action="store_true")

    # EVALUATE
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate a trained detector")
    eval_parser.add_argument("--dataset", required=True)
    eval_parser.add_argument("--threshold", type=float, default=0.50)
    eval_parser.add_argument("--model", choices=VALID_DATASET_TYPES, default="synthetic")

    # CROSSVAL
    cv_parser = subparsers.add_parser("crossval", help="5-fold stratified cross-validation")
    cv_parser.add_argument("--dataset", choices=VALID_DATASET_TYPES, default="synthetic")
    cv_parser.add_argument("--folds", type=int, default=5)
    cv_parser.add_argument("--model-tag", default=None)
    cv_parser.add_argument("--allow-eval-overlap", action="store_true")
    cv_parser.add_argument("--benchmark-name", default=None,
                            help="Label for the table's Benchmark column, e.g. eval_dataset_v2")
    cv_parser.add_argument("--dataset-csv", default=None,
                            help=(
                                "Run CV directly on an external CSV (e.g. datasets/deepset_eval.csv) "
                                "instead of one of the built-in --dataset modes. When set, --dataset "
                                "is ignored for data loading but still used as a fallback tag."
                            ))

    # MCNEMAR
    mc_parser = subparsers.add_parser("mcnemar", help="McNemar's test between two prediction files")
    mc_parser.add_argument("--pred-a", required=True)
    mc_parser.add_argument("--pred-b", required=True)
    mc_parser.add_argument("--label-a", default="System A")
    mc_parser.add_argument("--label-b", default="System B")

    # TEST
    test_parser = subparsers.add_parser("test", help="Interactive testing")
    test_parser.add_argument("--model", choices=VALID_DATASET_TYPES, default="synthetic")

    args = parser.parse_args()

    if args.command == "train":
        train_model(args.dataset, model_tag=args.model_tag, allow_overlap=args.allow_eval_overlap)
    elif args.command == "evaluate":
        if not (0.0 <= args.threshold <= 1.0):
            raise ValueError("Threshold must be between 0.0 and 1.0.")
        evaluate_model(args.dataset, args.threshold, model_tag=args.model)
    elif args.command == "crossval":
        cross_validate_model(args.dataset, folds=args.folds, model_tag=args.model_tag,
                              allow_overlap=args.allow_eval_overlap,
                              benchmark_name=args.benchmark_name,
                              dataset_csv=args.dataset_csv)
    elif args.command == "mcnemar":
        run_mcnemar_test(args.pred_a, args.pred_b, label_a=args.label_a, label_b=args.label_b)
    elif args.command == "test":
        interactive_test(model_tag=args.model)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
