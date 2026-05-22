"""Expense category suggestion — zero-shot first, trained classifier optional.

Design:
- Zero-shot is the DEFAULT path.  No model files need to exist at startup.
  ``suggest_category`` embeds the input text and the candidate prototype labels,
  then picks the prototype whose embedding is closest (dot product == cosine
  similarity because both sides are L2-normalised by ``embed_texts``).

- Trained path activates ONLY when ``models/categorizer.joblib`` is present on
  disk.  The module checks for the file on every call and loads it lazily,
  caching the result in ``_TRAINED_CACHE`` keyed by (path, mtime) so the cache
  invalidates automatically when the file is replaced by a fresh training run.

- ``train_categorizer`` refuses to fit if the labeled set does not contain at
  least two categories each with >= ``min_train_per_category`` examples.  This
  guard prevents noisy, over-fitted classifiers from being persisted.

Dependency note:
  ``embed_texts`` is imported at the top of this module but the underlying
  SentenceTransformer is not loaded until the first actual call (lazy init
  inside ``app.ml.embeddings``).  Tests mock ``app.ml.categorizer.embed_texts``
  directly so no real model is ever instantiated in the test suite.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]

from app.config import get_settings
from app.ml.embeddings import embed_texts

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

DEFAULT_PROTOTYPES: list[str] = [
    "food",
    "transport",
    "groceries",
    "utilities",
    "entertainment",
    "health",
    "rent",
    "other",
]

# ---------------------------------------------------------------------------
# Internal cache — keyed by (absolute_path_str, mtime_float)
# Avoids re-deserialising the joblib file on every request while still
# picking up a freshly trained model when the file's mtime changes.
# ---------------------------------------------------------------------------

_TRAINED_CACHE: dict[tuple[str, float], dict[str, Any]] = {}


def _clear_trained_cache() -> None:
    """Evict all entries from the in-process model cache.

    Called from tests to guarantee a clean slate between test cases that
    exercise the trained-model path.
    """
    _TRAINED_CACHE.clear()


def _model_path() -> Path:
    """Return the absolute Path where the trained categorizer is expected."""
    return (Path(get_settings().models_dir) / "categorizer.joblib").resolve()


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CategorySuggestion:
    """Result returned by :func:`suggest_category`."""

    category: str
    score: float
    mode: str  # "zero-shot" | "trained"


@dataclass
class TrainResult:
    """Result returned by :func:`train_categorizer`."""

    status: str  # "trained" | "refused-insufficient-data"
    reason: str
    n_examples: int
    n_categories: int
    metrics: dict[str, float] | None  # None when refused


# ---------------------------------------------------------------------------
# Core public functions
# ---------------------------------------------------------------------------


def suggest_category(text: str, prototypes: list[str]) -> CategorySuggestion:
    """Return the most likely category for *text*.

    Uses the trained classifier when ``models/categorizer.joblib`` exists;
    otherwise falls back to zero-shot prototype matching.

    Args:
        text:       Raw expense description to classify.
        prototypes: Candidate category labels (caller merges DB categories
                    with ``DEFAULT_PROTOTYPES`` before passing in).  When
                    empty and in zero-shot mode, ``DEFAULT_PROTOTYPES`` is used.

    Returns:
        :class:`CategorySuggestion` with ``category``, ``score``, and ``mode``.
    """
    # Edge-case: empty text — return a safe default without calling the model.
    if not text or not text.strip():
        return CategorySuggestion(category="other", score=0.0, mode="zero-shot")

    path = _model_path()

    # ------------------------------------------------------------------
    # Trained path
    # ------------------------------------------------------------------
    if path.exists():
        artifact = _load_trained(path)
        clf: LogisticRegression = artifact["classifier"]
        classes: list[str] = artifact["classes"]

        emb = embed_texts([text])  # shape (1, dim)
        proba = clf.predict_proba(emb)[0]  # shape (n_classes,)
        idx = int(np.argmax(proba))
        return CategorySuggestion(
            category=classes[idx],
            score=float(proba[idx]),
            mode="trained",
        )

    # ------------------------------------------------------------------
    # Zero-shot path
    # ------------------------------------------------------------------
    labels = prototypes if prototypes else DEFAULT_PROTOTYPES

    # Embed text + all prototypes in one batch for efficiency (single model
    # call, same normalisation scale for the dot-product comparison).
    all_texts = [text] + labels
    all_embs = embed_texts(all_texts)  # shape (1 + len(labels), dim)

    text_emb = all_embs[0]  # shape (dim,)
    label_embs = all_embs[1:]  # shape (len(labels), dim)

    similarities = label_embs @ text_emb  # dot product == cosine (L2-normed)
    idx = int(np.argmax(similarities))
    return CategorySuggestion(
        category=labels[idx],
        score=float(similarities[idx]),
        mode="zero-shot",
    )


def train_categorizer(labeled: list[tuple[str, str]]) -> TrainResult:
    """Fit a logistic-regression classifier on *labeled* (text, category) pairs.

    Writes ``models/categorizer.joblib`` on success.  Refuses (without writing
    any file) when the data set is too small.

    Args:
        labeled: List of ``(description, category)`` pairs from the DB.

    Returns:
        :class:`TrainResult` describing the outcome.
    """
    n_examples = len(labeled)
    counts: Counter[str] = Counter(category for _, category in labeled)
    n_categories = len(counts)

    threshold = get_settings().min_train_per_category

    # ------------------------------------------------------------------
    # Refusal guard
    # ------------------------------------------------------------------
    qualifying = {cat: cnt for cat, cnt in counts.items() if cnt >= threshold}

    if n_categories < 2:
        reason = (
            f"need at least 2 distinct categories, found {n_categories}."
        )
        return TrainResult(
            status="refused-insufficient-data",
            reason=reason,
            n_examples=n_examples,
            n_categories=n_categories,
            metrics=None,
        )

    if len(qualifying) < 2:
        worst_cat = min(counts, key=lambda c: counts[c])
        reason = (
            f"need >= {threshold} examples in at least 2 categories; "
            f"'{worst_cat}' has only {counts[worst_cat]}."
        )
        return TrainResult(
            status="refused-insufficient-data",
            reason=reason,
            n_examples=n_examples,
            n_categories=n_categories,
            metrics=None,
        )

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    texts = [t for t, _ in labeled]
    labels_list = [c for _, c in labeled]

    X: np.ndarray = embed_texts(texts)
    y: list[str] = labels_list

    clf = LogisticRegression(max_iter=1000, random_state=42)
    clf.fit(X, y)

    # Training-set accuracy as a sanity metric.
    # Conformal / held-out evaluation is deferred to Phase 3+.
    acc = float((clf.predict(X) == np.array(y)).mean())

    # Persist
    out_path = _model_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {"classifier": clf, "classes": clf.classes_.tolist()}
    joblib.dump(artifact, out_path)

    # Invalidate any stale cache entry so the next request picks up the new
    # model without a process restart.
    _clear_trained_cache()

    reason = (
        f"trained on {n_examples} examples across {n_categories} categories"
    )
    return TrainResult(
        status="trained",
        reason=reason,
        n_examples=n_examples,
        n_categories=n_categories,
        metrics={"accuracy": acc},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_trained(path: Path) -> dict[str, Any]:
    """Load and cache the trained artifact from *path*.

    Keyed by (absolute_path_str, mtime) so a freshly written model file is
    automatically picked up without restarting the process.
    """
    mtime = path.stat().st_mtime
    key = (str(path), mtime)
    if key not in _TRAINED_CACHE:
        _TRAINED_CACHE[key] = joblib.load(path)
    return _TRAINED_CACHE[key]
