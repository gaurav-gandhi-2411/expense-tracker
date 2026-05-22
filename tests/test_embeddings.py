from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from app.ml.embeddings import embed_texts, get_embedding_model


class TestEmbedTexts:
    def test_embed_texts_calls_encode_with_normalize(self, mocker) -> None:
        """embed_texts delegates to the model with normalize_embeddings=True."""
        fake_output = np.array([[0.1, 0.2], [0.3, 0.4]], dtype=np.float32)
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_output
        mocker.patch("app.ml.embeddings.get_embedding_model", return_value=mock_model)

        result = embed_texts(["a", "b"])

        mock_model.encode.assert_called_once_with(
            ["a", "b"],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        np.testing.assert_array_equal(result, fake_output)
        assert result.shape == (2, 2)

    def test_embed_texts_empty_input(self, mocker) -> None:
        """embed_texts returns a (0, 0) array and never calls encode on empty input."""
        mock_model = MagicMock()
        mocker.patch("app.ml.embeddings.get_embedding_model", return_value=mock_model)

        result = embed_texts([])

        mock_model.encode.assert_not_called()
        assert result.shape == (0, 0)
        assert result.dtype == np.float32

    def test_get_embedding_model_is_cached(self, mocker) -> None:
        """get_embedding_model instantiates SentenceTransformer exactly once per cache lifetime."""
        get_embedding_model.cache_clear()

        mock_cls = mocker.patch("sentence_transformers.SentenceTransformer")

        _ = get_embedding_model()
        _ = get_embedding_model()

        mock_cls.assert_called_once()

        get_embedding_model.cache_clear()
