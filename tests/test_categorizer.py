"""Tests for app.ml.categorizer — zero-shot, trained, and LLM-fallback paths.

All tests mock ``app.ml.categorizer.embed_texts`` so no real SentenceTransformer
is ever instantiated.  Tests that exercise the trained path also mock
``app.ml.categorizer.joblib.load`` to avoid touching the real filesystem.
LLM-fallback tests mock ``app.ml.categorizer.extract_category`` so no real
API call is ever made.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.ml.categorizer import (
    DEFAULT_PROTOTYPES,
    _clear_trained_cache,
    suggest_category,
    train_categorizer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NONEXISTENT = Path("/nonexistent/categorizer.joblib")


def _make_settings_mock(tmp_path: Path, fallback_threshold: float = 0.30) -> MagicMock:
    """Return a mock that looks like Settings with models_dir == tmp_path."""
    mock_settings = MagicMock()
    mock_settings.models_dir = str(tmp_path)
    mock_settings.min_train_per_category = 30
    mock_settings.embedding_model = "all-MiniLM-L6-v2"
    mock_settings.categorizer_fallback_threshold = fallback_threshold
    return mock_settings


# ---------------------------------------------------------------------------
# Zero-shot tests
# ---------------------------------------------------------------------------


class TestSuggestCategoryZeroShot:
    def test_picks_closest_prototype(self, mocker: MagicMock) -> None:
        """Zero-shot: prototype with highest cosine similarity is selected.

        The input text is index 0, prototypes are indices 1-3.
        We construct embeddings so that dot(text_emb, transport_emb) > others.
        """
        # text embedding: [1, 0, 0]
        # food:      [0, 1, 0]  -> similarity 0.0
        # transport: [1, 0, 0]  -> similarity 1.0  <- should win
        # groceries: [0, 0, 1]  -> similarity 0.0
        fake_embs = np.array(
            [
                [1.0, 0.0, 0.0],  # text
                [0.0, 1.0, 0.0],  # food
                [1.0, 0.0, 0.0],  # transport
                [0.0, 0.0, 1.0],  # groceries
            ],
            dtype=np.float32,
        )
        mocker.patch("app.ml.categorizer.embed_texts", return_value=fake_embs)
        mocker.patch("app.ml.categorizer._model_path", return_value=_NONEXISTENT)
        _clear_trained_cache()

        result = suggest_category("uber to airport", ["food", "transport", "groceries"])

        assert result.category == "transport"
        assert result.mode == "zero-shot"
        assert result.score > 0.0

    def test_uses_defaults_when_prototypes_empty(self, mocker: MagicMock) -> None:
        """Zero-shot: when prototypes=[], DEFAULT_PROTOTYPES are used as labels."""
        n_defaults = len(DEFAULT_PROTOTYPES)
        # text + n_defaults labels; we make "food" (index 0) the winner
        rows = np.zeros((1 + n_defaults, 4), dtype=np.float32)
        rows[0] = [1.0, 0.0, 0.0, 0.0]  # text
        rows[1] = [1.0, 0.0, 0.0, 0.0]  # food (index 0 in DEFAULT_PROTOTYPES)
        mocker.patch("app.ml.categorizer.embed_texts", return_value=rows)
        mocker.patch("app.ml.categorizer._model_path", return_value=_NONEXISTENT)
        _clear_trained_cache()

        result = suggest_category("dinner at restaurant", [])

        assert result.category in DEFAULT_PROTOTYPES
        assert result.mode == "zero-shot"

    def test_empty_text_returns_other_without_calling_embed(
        self, mocker: MagicMock
    ) -> None:
        """Empty text: return safe default 'other' without invoking embed_texts."""
        mock_embed = mocker.patch("app.ml.categorizer.embed_texts")
        mocker.patch("app.ml.categorizer._model_path", return_value=_NONEXISTENT)
        _clear_trained_cache()

        result = suggest_category("", ["food", "transport"])

        mock_embed.assert_not_called()
        assert result.category == "other"
        assert result.mode == "zero-shot"
        assert result.score == 0.0

    def test_whitespace_only_text_returns_other(self, mocker: MagicMock) -> None:
        """Whitespace-only text is treated the same as empty text."""
        mock_embed = mocker.patch("app.ml.categorizer.embed_texts")
        mocker.patch("app.ml.categorizer._model_path", return_value=_NONEXISTENT)
        _clear_trained_cache()

        result = suggest_category("   ", ["food", "transport"])

        mock_embed.assert_not_called()
        assert result.category == "other"
        assert result.score == 0.0


# ---------------------------------------------------------------------------
# Trained path tests
# ---------------------------------------------------------------------------


class TestSuggestCategoryTrainedPath:
    def test_trained_path_taken_when_file_exists(
        self, mocker: MagicMock, tmp_path: Path
    ) -> None:
        """When the categorizer.joblib file exists, mode='trained' is used."""
        model_file = tmp_path / "categorizer.joblib"
        model_file.write_bytes(b"dummy")

        mocker.patch("app.ml.categorizer._model_path", return_value=model_file)
        _clear_trained_cache()

        mock_clf = MagicMock()
        mock_clf.predict_proba.return_value = np.array([[0.1, 0.9]])
        mock_clf.classes_ = ["food", "transport"]
        fake_artifact = {"classifier": mock_clf, "classes": ["food", "transport"]}
        mocker.patch("app.ml.categorizer.joblib.load", return_value=fake_artifact)

        mocker.patch(
            "app.ml.categorizer.embed_texts",
            return_value=np.array([[0.5, 0.5]], dtype=np.float32),
        )

        result = suggest_category("uber", [])

        assert result.mode == "trained"
        assert result.category == "transport"
        assert result.score == pytest.approx(0.9)

    def test_trained_cache_invalidates_on_new_mtime(
        self, mocker: MagicMock, tmp_path: Path
    ) -> None:
        """Cache miss occurs when the file is replaced (mtime changes)."""
        model_file = tmp_path / "categorizer.joblib"
        model_file.write_bytes(b"v1")

        mocker.patch("app.ml.categorizer._model_path", return_value=model_file)
        _clear_trained_cache()

        mock_clf_v1 = MagicMock()
        mock_clf_v1.predict_proba.return_value = np.array([[0.8, 0.2]])
        artifact_v1 = {"classifier": mock_clf_v1, "classes": ["food", "transport"]}

        mock_clf_v2 = MagicMock()
        mock_clf_v2.predict_proba.return_value = np.array([[0.1, 0.9]])
        artifact_v2 = {"classifier": mock_clf_v2, "classes": ["food", "transport"]}

        mock_load = mocker.patch(
            "app.ml.categorizer.joblib.load", side_effect=[artifact_v1, artifact_v2]
        )
        mocker.patch(
            "app.ml.categorizer.embed_texts",
            return_value=np.array([[0.5, 0.5]], dtype=np.float32),
        )

        r1 = suggest_category("lunch", [])
        assert r1.category == "food"

        # Simulate file replacement: overwrite + update mtime so cache misses.
        model_file.write_bytes(b"v2")
        original_mtime = model_file.stat().st_mtime
        os.utime(str(model_file), (original_mtime + 1.0, original_mtime + 1.0))

        r2 = suggest_category("taxi", [])
        assert r2.category == "transport"
        assert mock_load.call_count == 2


# ---------------------------------------------------------------------------
# train_categorizer tests
# ---------------------------------------------------------------------------


class TestTrainCategorizer:
    def test_refuses_below_per_category_threshold(
        self, mocker: MagicMock, tmp_path: Path
    ) -> None:
        """Refuses when no category meets min_train_per_category (default 30)."""
        mocker.patch(
            "app.ml.categorizer.get_settings",
            return_value=_make_settings_mock(tmp_path),
        )
        mocker.patch(
            "app.ml.categorizer._model_path",
            return_value=tmp_path / "categorizer.joblib",
        )
        mock_embed = mocker.patch("app.ml.categorizer.embed_texts")
        _clear_trained_cache()

        labeled: list[tuple[str, str]] = [("a", "food")] * 5 + [("b", "transport")] * 5

        result = train_categorizer(labeled)

        assert result.status == "refused-insufficient-data"
        assert result.metrics is None
        assert result.n_examples == 10
        assert result.n_categories == 2
        mock_embed.assert_not_called()
        assert not (tmp_path / "categorizer.joblib").exists()

    def test_refuses_only_one_category(
        self, mocker: MagicMock, tmp_path: Path
    ) -> None:
        """Refuses when there is only 1 distinct category regardless of count."""
        mocker.patch(
            "app.ml.categorizer.get_settings",
            return_value=_make_settings_mock(tmp_path),
        )
        mocker.patch(
            "app.ml.categorizer._model_path",
            return_value=tmp_path / "categorizer.joblib",
        )
        mock_embed = mocker.patch("app.ml.categorizer.embed_texts")
        _clear_trained_cache()

        labeled: list[tuple[str, str]] = [("a", "food")] * 50

        result = train_categorizer(labeled)

        assert result.status == "refused-insufficient-data"
        assert result.n_categories == 1
        mock_embed.assert_not_called()

    def test_trains_above_threshold_and_writes_file(
        self, mocker: MagicMock, tmp_path: Path
    ) -> None:
        """Trains successfully with perfectly separable data; accuracy == 1.0."""
        mocker.patch(
            "app.ml.categorizer.get_settings",
            return_value=_make_settings_mock(tmp_path),
        )
        mocker.patch(
            "app.ml.categorizer._model_path",
            return_value=tmp_path / "categorizer.joblib",
        )
        _clear_trained_cache()

        labeled: list[tuple[str, str]] = (
            [("food text " + str(i), "food") for i in range(30)]
            + [("transport text " + str(i), "transport") for i in range(30)]
        )

        # Perfectly separable 2-D embeddings: food -> [1,0], transport -> [0,1]
        food_embs = np.tile(np.array([1.0, 0.0], dtype=np.float32), (30, 1))
        transport_embs = np.tile(np.array([0.0, 1.0], dtype=np.float32), (30, 1))
        fake_embs = np.vstack([food_embs, transport_embs])
        mocker.patch("app.ml.categorizer.embed_texts", return_value=fake_embs)

        result = train_categorizer(labeled)

        assert result.status == "trained"
        assert result.n_examples == 60
        assert result.n_categories == 2
        assert result.metrics is not None
        assert result.metrics["accuracy"] == pytest.approx(1.0)
        assert (tmp_path / "categorizer.joblib").exists()

    def test_trained_result_has_informative_reason(
        self, mocker: MagicMock, tmp_path: Path
    ) -> None:
        """TrainResult.reason mentions example count and category count."""
        mocker.patch(
            "app.ml.categorizer.get_settings",
            return_value=_make_settings_mock(tmp_path),
        )
        mocker.patch(
            "app.ml.categorizer._model_path",
            return_value=tmp_path / "categorizer.joblib",
        )
        _clear_trained_cache()

        labeled: list[tuple[str, str]] = (
            [("food text " + str(i), "food") for i in range(30)]
            + [("transport text " + str(i), "transport") for i in range(30)]
        )
        food_embs = np.tile(np.array([1.0, 0.0], dtype=np.float32), (30, 1))
        transport_embs = np.tile(np.array([0.0, 1.0], dtype=np.float32), (30, 1))
        mocker.patch(
            "app.ml.categorizer.embed_texts",
            return_value=np.vstack([food_embs, transport_embs]),
        )

        result = train_categorizer(labeled)

        assert "60" in result.reason
        assert "2" in result.reason

    def test_refuses_when_only_one_category_qualifies(
        self, mocker: MagicMock, tmp_path: Path
    ) -> None:
        """Refuses when two categories exist but only one meets the threshold."""
        mocker.patch(
            "app.ml.categorizer.get_settings",
            return_value=_make_settings_mock(tmp_path),
        )
        mocker.patch(
            "app.ml.categorizer._model_path",
            return_value=tmp_path / "categorizer.joblib",
        )
        mock_embed = mocker.patch("app.ml.categorizer.embed_texts")
        _clear_trained_cache()

        # food has 35 (>=30), transport has only 5 (<30) — only 1 qualifies
        labeled: list[tuple[str, str]] = (
            [("food text", "food")] * 35 + [("transport text", "transport")] * 5
        )

        result = train_categorizer(labeled)

        assert result.status == "refused-insufficient-data"
        assert result.metrics is None
        mock_embed.assert_not_called()
        assert not (tmp_path / "categorizer.joblib").exists()


# ---------------------------------------------------------------------------
# LLM-fallback tests
# ---------------------------------------------------------------------------


class TestSuggestCategoryLLMFallback:
    def test_suggest_category_uses_llm_fallback_below_threshold(
        self, mocker: MagicMock, tmp_path: Path
    ) -> None:
        """When zero-shot best_score < threshold, LLM fallback is called and its
        category is returned with mode='llm-fallback'."""
        # All embeddings identical → every cosine similarity == 1.0 except we
        # manufacture a low score by making text orthogonal to all prototypes.
        # text_emb: [0, 0, 1]
        # all prototypes: [1, 0, 0]  → similarity == 0.0 < 0.30
        n_prototypes = 3  # food, transport, groceries
        prototype_emb = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        text_emb = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        rows = np.vstack([text_emb] + [prototype_emb] * n_prototypes)

        mocker.patch("app.ml.categorizer.embed_texts", return_value=rows)
        mocker.patch("app.ml.categorizer._model_path", return_value=_NONEXISTENT)
        mocker.patch(
            "app.ml.categorizer.get_settings",
            return_value=_make_settings_mock(tmp_path, fallback_threshold=0.30),
        )
        mocker.patch("app.ml.categorizer.extract_category", return_value="food")
        _clear_trained_cache()

        result = suggest_category("swiggy order 480", ["food", "transport", "groceries"])

        assert result.category == "food"
        assert result.mode == "llm-fallback"

    def test_suggest_category_llm_fallback_failure_returns_zero_shot_with_note(
        self, mocker: MagicMock, tmp_path: Path
    ) -> None:
        """When LLM fallback raises, the zero-shot result is returned with a
        non-empty confidence_note and mode='zero-shot'."""
        n_prototypes = 3
        prototype_emb = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        text_emb = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        rows = np.vstack([text_emb] + [prototype_emb] * n_prototypes)

        mocker.patch("app.ml.categorizer.embed_texts", return_value=rows)
        mocker.patch("app.ml.categorizer._model_path", return_value=_NONEXISTENT)
        mocker.patch(
            "app.ml.categorizer.get_settings",
            return_value=_make_settings_mock(tmp_path, fallback_threshold=0.30),
        )
        mocker.patch(
            "app.ml.categorizer.extract_category",
            side_effect=RuntimeError("rate limit"),
        )
        _clear_trained_cache()

        result = suggest_category("swiggy order 480", ["food", "transport", "groceries"])

        assert result.mode == "zero-shot"
        assert result.confidence_note is not None
        assert len(result.confidence_note) > 0
        note_lower = result.confidence_note.lower()
        assert "fallback" in note_lower or "failed" in note_lower
        # Category must still be one of the provided prototypes (best zero-shot guess).
        assert result.category in ["food", "transport", "groceries"]

    def test_default_prototypes_contain_brand_keywords(self) -> None:
        """DEFAULT_PROTOTYPES includes Indian brand keywords; 'subscription' is absent."""
        assert "swiggy" in DEFAULT_PROTOTYPES["food"]
        assert "uber" in DEFAULT_PROTOTYPES["transport"]
        assert "netflix" in DEFAULT_PROTOTYPES["entertainment"]
        assert "subscription" not in DEFAULT_PROTOTYPES
