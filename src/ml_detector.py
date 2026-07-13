"""
Prompt Injection Detection and Defence for LLM-Based Applications
CNIT/PNTLab Pisa — AI Security Internship 2026

Week 4/5: ML-Based Prompt Injection Detector
=============================================

Trains a TF-IDF + Logistic Regression classifier on the HackAPrompt
dataset to detect prompt injection attempts, and benchmarks it
against a rule-based keyword detector.

Design notes
------------
- Train/test splits are persisted to disk so results are reproducible
  across runs and comparable week-over-week.
- The model is evaluated on three slices: the held-out HackAPrompt
  test set (in-domain), Garak-generated attacks, and a hand-written
  custom attack set (both out-of-domain, if present) — this is the
  number that actually matters for real-world generalisation.
- Models are persisted with joblib (the sklearn-recommended format)
  rather than raw pickle.

Usage
-----
    python src/ml_detector.py train                 # train + evaluate + save
    python src/ml_detector.py train --model svm      # train a different model
    python src/ml_detector.py evaluate                # re-evaluate saved model
    python src/ml_detector.py interactive             # interactive CLI testing
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from datasets import load_dataset
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
from sklearn.naive_bayes import MultinomialNB
from sklearn.svm import LinearSVC

# ─────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ml_detector")


# ─────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Config:
    """Central configuration for paths and hyperparameters."""

    results_dir: Path = Path("experiments/results")
    models_dir: Path = Path("experiments/models")
    datasets_dir: Path = Path("datasets")

    garak_prompts_file: Path = Path("experiments/results/garak_prompts.txt")
    custom_attacks_file: Path = Path("datasets/custom_attacks.csv")

    test_size: float = 0.2
    random_state: int = 42

    tfidf_max_features: int = 10_000
    tfidf_ngram_range: tuple = (1, 3)
    tfidf_min_df: int = 2

    @property
    def vectorizer_path(self) -> Path:
        return self.models_dir / "vectorizer.joblib"

    def classifier_path(self, model_name: str) -> Path:
        return self.models_dir / f"classifier_{model_name}.joblib"

    def ensure_dirs(self) -> None:
        for d in (self.results_dir, self.models_dir, self.datasets_dir):
            d.mkdir(parents=True, exist_ok=True)


CONFIG = Config()

KEYWORD_PATTERNS: list[str] = [
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

SUPPORTED_MODELS = {
    "logistic_regression": lambda: LogisticRegression(
        max_iter=1000, C=1.0, class_weight="balanced",
        random_state=CONFIG.random_state, solver="lbfgs",
    ),
    "naive_bayes": lambda: MultinomialNB(),
    "svm": lambda: LinearSVC(class_weight="balanced", random_state=CONFIG.random_state),
}


class DetectorError(Exception):
    """Raised for recoverable detector pipeline failures."""


# ─────────────────────────────────────────────────────────────────
# Keyword baseline detector
# ─────────────────────────────────────────────────────────────────

class KeywordDetector:
    """Rule-based baseline: flags text containing known injection phrases."""

    def __init__(self, patterns: list[str] = KEYWORD_PATTERNS) -> None:
        self.patterns = patterns

    def predict(self, text: str) -> int:
        return 1 if self.matched_patterns(text) else 0

    def matched_patterns(self, text: str) -> list[str]:
        text_lower = text.lower()
        return [p for p in self.patterns if p in text_lower]

    def predict_batch(self, texts: list[str]) -> list[int]:
        return [self.predict(t) for t in texts]


# ─────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────

def load_hackaprompt() -> pd.DataFrame:
    """Loads the HackAPrompt dataset as a labelled DataFrame."""
    logger.info("Loading HackAPrompt dataset...")
    dataset = load_dataset("hackaprompt/hackaprompt-dataset")
    df = dataset["train"].to_pandas()
    df = df.dropna(subset=["user_input", "correct"])
    df = df.rename(columns={"user_input": "text"})
    df["label"] = df["correct"].astype(int)
    df["source"] = "hackaprompt"

    logger.info(
        "HackAPrompt loaded: %d rows | attack=%d safe=%d (%.2f%% attack rate)",
        len(df), df["label"].sum(), (df["label"] == 0).sum(), df["label"].mean() * 100,
    )
    return df[["text", "label", "source"]]


def load_txt_prompts(path: Path, label: int, source: str) -> pd.DataFrame:
    """Loads newline-delimited prompts (e.g. Garak output) as a labelled frame."""
    if not path.exists():
        logger.warning("Prompt file not found, skipping: %s", path)
        return pd.DataFrame(columns=["text", "label", "source"])

    prompts = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#") and not line.startswith("---")
    ]
    logger.info("Loaded %d prompts from %s", len(prompts), path)
    return pd.DataFrame({"text": prompts, "label": label, "source": source})


def load_custom_attacks(path: Path) -> pd.DataFrame:
    """Loads a manually curated CSV with columns: text,label,attack_type,source."""
    if not path.exists():
        logger.warning("Custom attacks file not found, skipping: %s", path)
        return pd.DataFrame(columns=["text", "label", "source"])

    df = pd.read_csv(path)
    df["label"] = df["label"].astype(int)
    df["source"] = "manual"
    logger.info("Loaded %d custom examples from %s", len(df), path)
    return df[["text", "label", "source"]]


def prepare_train_test_split(
    df: pd.DataFrame, config: Config = CONFIG
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Stratified train/test split, persisted to disk for reproducibility."""
    train_df, test_df = train_test_split(
        df,
        test_size=config.test_size,
        random_state=config.random_state,
        stratify=df["label"],
    )
    config.ensure_dirs()
    train_path = config.datasets_dir / "train_split.csv"
    test_path = config.datasets_dir / "test_split.csv"
    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)
    logger.info("Saved split -> train: %s (%d rows) | test: %s (%d rows)",
                train_path, len(train_df), test_path, len(test_df))
    return train_df, test_df


# ─────────────────────────────────────────────────────────────────
# Training
# ─────────────────────────────────────────────────────────────────

def build_vectorizer(config: Config = CONFIG) -> TfidfVectorizer:
    return TfidfVectorizer(
        max_features=config.tfidf_max_features,
        ngram_range=config.tfidf_ngram_range,
        sublinear_tf=True,
        strip_accents="unicode",
        analyzer="word",
        min_df=config.tfidf_min_df,
    )


def train_model(
    train_df: pd.DataFrame, model_name: str = "logistic_regression"
) -> tuple[TfidfVectorizer, object]:
    """Fits a TF-IDF vectorizer and the requested classifier."""
    if model_name not in SUPPORTED_MODELS:
        raise DetectorError(
            f"Unknown model '{model_name}'. Choose from {list(SUPPORTED_MODELS)}"
        )

    logger.info("Vectorizing training text (TF-IDF)...")
    vectorizer = build_vectorizer()
    X_train = vectorizer.fit_transform(train_df["text"].astype(str))
    logger.info("Vocabulary size: %d", len(vectorizer.vocabulary_))

    logger.info("Training model: %s", model_name)
    classifier = SUPPORTED_MODELS[model_name]()
    classifier.fit(X_train, train_df["label"])
    logger.info("Training complete.")

    return vectorizer, classifier


# ─────────────────────────────────────────────────────────────────
# Evaluation
# ─────────────────────────────────────────────────────────────────

def evaluate_on_split(
    classifier, vectorizer: TfidfVectorizer, texts: pd.Series, labels: pd.Series
) -> dict:
    """Computes standard classification metrics on a labelled slice."""
    X = vectorizer.transform(texts.astype(str))
    preds = classifier.predict(X)
    cm = confusion_matrix(labels, preds)

    metrics = {
        "accuracy": round(accuracy_score(labels, preds) * 100, 2),
        "precision": round(precision_score(labels, preds, zero_division=0) * 100, 2),
        "recall": round(recall_score(labels, preds, zero_division=0) * 100, 2),
        "f1_score": round(f1_score(labels, preds, zero_division=0) * 100, 2),
        "confusion_matrix": {
            "true_positives": int(cm[1][1]) if cm.shape == (2, 2) else None,
            "true_negatives": int(cm[0][0]) if cm.shape == (2, 2) else None,
            "false_positives": int(cm[0][1]) if cm.shape == (2, 2) else None,
            "false_negatives": int(cm[1][0]) if cm.shape == (2, 2) else None,
        },
        "n": len(labels),
    }
    return metrics


def evaluate_detection_rate(
    classifier, vectorizer: TfidfVectorizer, texts: pd.Series
) -> dict:
    """For unlabelled-as-safe-assumed attack sets: reports raw detection rate."""
    if len(texts) == 0:
        return {}
    X = vectorizer.transform(texts.astype(str))
    ml_preds = classifier.predict(X)
    kw_preds = KeywordDetector().predict_batch(list(texts))

    ml_rate = sum(ml_preds) / len(texts) * 100
    kw_rate = sum(kw_preds) / len(texts) * 100
    return {
        "n": len(texts),
        "ml_detected": int(sum(ml_preds)),
        "ml_detection_rate": round(ml_rate, 2),
        "keyword_detected": int(sum(kw_preds)),
        "keyword_detection_rate": round(kw_rate, 2),
    }


def compare_with_keyword_baseline(
    classifier, vectorizer: TfidfVectorizer, texts: pd.Series, labels: pd.Series
) -> dict:
    """Head-to-head ML vs keyword detector on a labelled test slice."""
    kw = KeywordDetector()
    ml_preds = classifier.predict(vectorizer.transform(texts.astype(str)))
    kw_preds = kw.predict_batch(list(texts))

    ml_f1 = f1_score(labels, ml_preds, zero_division=0)
    kw_f1 = f1_score(labels, kw_preds, zero_division=0)

    result = {
        "keyword": {
            "precision": round(precision_score(labels, kw_preds, zero_division=0) * 100, 2),
            "recall": round(recall_score(labels, kw_preds, zero_division=0) * 100, 2),
            "f1_score": round(kw_f1 * 100, 2),
        },
        "ml": {
            "precision": round(precision_score(labels, ml_preds, zero_division=0) * 100, 2),
            "recall": round(recall_score(labels, ml_preds, zero_division=0) * 100, 2),
            "f1_score": round(ml_f1 * 100, 2),
        },
        "winner": "ml" if ml_f1 > kw_f1 else "keyword",
    }
    return result


def top_predictive_terms(classifier, vectorizer: TfidfVectorizer, n: int = 15) -> list[dict]:
    """Returns the top-N terms most associated with the attack class, if supported."""
    if not hasattr(classifier, "coef_"):
        return []
    feature_names = vectorizer.get_feature_names_out()
    coef = classifier.coef_[0]
    top_idx = coef.argsort()[-n:][::-1]
    return [{"term": feature_names[i], "weight": round(float(coef[i]), 3)} for i in top_idx]


# ─────────────────────────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────────────────────────

def save_model(vectorizer, classifier, model_name: str, config: Config = CONFIG) -> None:
    config.ensure_dirs()
    joblib.dump(vectorizer, config.vectorizer_path)
    joblib.dump(classifier, config.classifier_path(model_name))
    logger.info("Model saved: %s, %s", config.vectorizer_path, config.classifier_path(model_name))


def load_model(model_name: str, config: Config = CONFIG) -> tuple[Optional[object], Optional[object]]:
    vec_path, clf_path = config.vectorizer_path, config.classifier_path(model_name)
    if not vec_path.exists() or not clf_path.exists():
        return None, None
    return joblib.load(vec_path), joblib.load(clf_path)


def save_report(report: dict, filename: str, config: Config = CONFIG) -> Path:
    config.ensure_dirs()
    path = config.results_dir / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info("Report saved: %s", path)
    return path


# ─────────────────────────────────────────────────────────────────
# Interactive CLI
# ─────────────────────────────────────────────────────────────────

def run_interactive(model_name: str) -> None:
    vectorizer, classifier = load_model(model_name)
    if vectorizer is None:
        logger.error("No saved model found for '%s'. Run `train` first.", model_name)
        return

    kw = KeywordDetector()
    print("=" * 60)
    print(f"PROMPT INJECTION DETECTOR — interactive mode ({model_name})")
    print("Type a prompt to test it. Type 'quit' to exit.")
    print("=" * 60)

    while True:
        try:
            prompt = input("\nPROMPT> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if prompt.lower() == "quit":
            break
        if not prompt:
            continue

        kw_matched = kw.matched_patterns(prompt)
        X = vectorizer.transform([prompt])
        ml_pred = classifier.predict(X)[0]
        ml_score = (
            classifier.predict_proba(X)[0][1] * 100
            if hasattr(classifier, "predict_proba")
            else None
        )

        print(f"  Keyword : {'⚠️ SUSPICIOUS ' + str(kw_matched) if kw_matched else '✅ safe'}")
        if ml_score is not None:
            label = "🔴 ATTACK" if ml_pred == 1 else "✅ SAFE"
            print(f"  ML      : {label} (confidence: {ml_score:.1f}%)")
        else:
            label = "🔴 ATTACK" if ml_pred == 1 else "✅ SAFE"
            print(f"  ML      : {label}")


# ─────────────────────────────────────────────────────────────────
# Pipeline commands
# ─────────────────────────────────────────────────────────────────

def cmd_train(model_name: str, include_garak: bool, include_custom: bool) -> None:
    CONFIG.ensure_dirs()

    frames = [load_hackaprompt()]
    if include_garak:
        frames.append(load_txt_prompts(CONFIG.garak_prompts_file, label=1, source="garak"))
    if include_custom:
        frames.append(load_custom_attacks(CONFIG.custom_attacks_file))

    df = pd.concat([f for f in frames if not f.empty], ignore_index=True)
    logger.info("Combined dataset: %d rows from sources=%s", len(df), df["source"].unique().tolist())

    train_df, test_df = prepare_train_test_split(df)
    vectorizer, classifier = train_model(train_df, model_name)

    # In-domain evaluation
    metrics = evaluate_on_split(classifier, vectorizer, test_df["text"], test_df["label"])
    logger.info("Test set metrics: %s", metrics)

    comparison = compare_with_keyword_baseline(
        classifier, vectorizer, test_df["text"], test_df["label"]
    )
    logger.info("ML vs keyword winner: %s", comparison["winner"])

    # Out-of-domain: Garak (always check regardless of whether it was trained on)
    garak_prompts = load_txt_prompts(CONFIG.garak_prompts_file, label=1, source="garak")
    garak_eval = (
        evaluate_detection_rate(classifier, vectorizer, garak_prompts["text"])
        if not garak_prompts.empty else {}
    )

    save_model(vectorizer, classifier, model_name)

    report = {
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "model": model_name,
        "training_sources": df["source"].unique().tolist(),
        "training_rows": len(train_df),
        "test_rows": len(test_df),
        "test_metrics": metrics,
        "keyword_vs_ml": comparison,
        "garak_generalisation": garak_eval,
        "top_attack_terms": top_predictive_terms(classifier, vectorizer),
    }
    save_report(report, f"ml_detector_{model_name}_results.json")

    print("\nTraining complete. Try it out:")
    print(f"  python src/ml_detector.py interactive --model {model_name}")


def cmd_evaluate(model_name: str) -> None:
    vectorizer, classifier = load_model(model_name)
    if vectorizer is None:
        logger.error("No saved model found for '%s'. Run `train` first.", model_name)
        return

    test_path = CONFIG.datasets_dir / "test_split.csv"
    if not test_path.exists():
        raise DetectorError(f"No test split found at {test_path}. Run `train` first.")

    test_df = pd.read_csv(test_path)
    metrics = evaluate_on_split(classifier, vectorizer, test_df["text"], test_df["label"])
    print(json.dumps(metrics, indent=2))


# ─────────────────────────────────────────────────────────────────
# CLI entrypoint
# ─────────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ML-based prompt injection detector")
    subparsers = parser.add_subparsers(dest="command", required=True)

    train_p = subparsers.add_parser("train", help="Train, evaluate, and save a model")
    train_p.add_argument("--model", choices=list(SUPPORTED_MODELS), default="logistic_regression")
    train_p.add_argument("--no-garak", action="store_true", help="Exclude Garak prompts from training")
    train_p.add_argument("--no-custom", action="store_true", help="Exclude custom_attacks.csv from training")

    eval_p = subparsers.add_parser("evaluate", help="Re-evaluate a saved model on the saved test split")
    eval_p.add_argument("--model", choices=list(SUPPORTED_MODELS), default="logistic_regression")

    interactive_p = subparsers.add_parser("interactive", help="Interactively test prompts")
    interactive_p.add_argument("--model", choices=list(SUPPORTED_MODELS), default="logistic_regression")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "train":
            cmd_train(
                model_name=args.model,
                include_garak=not args.no_garak,
                include_custom=not args.no_custom,
            )
        elif args.command == "evaluate":
            cmd_evaluate(args.model)
        elif args.command == "interactive":
            run_interactive(args.model)
    except DetectorError as e:
        logger.error(str(e))
        return 1
    except Exception:
        logger.exception("Unexpected failure")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())