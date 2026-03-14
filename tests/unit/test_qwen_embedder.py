#!/usr/bin/env python3
"""
Tests for the Qwen (DashScope) embedding integration via qwen3-vl-embedding model.
"""

import os
import sys
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Stub tiktoken before adalflow / api.config is imported.  The cl100k_base
# BPE file requires a network download that is unavailable in this sandbox.
# ---------------------------------------------------------------------------
_mock_enc = MagicMock()
_mock_enc.encode = lambda text: list(range(max(1, len(text.split()))))

import tiktoken as _tiktoken_real  # noqa: E402  (loaded before our stub)
_tiktoken_real.get_encoding = lambda name: _mock_enc         # type: ignore[assignment]
_tiktoken_real.encoding_for_model = lambda name: _mock_enc   # type: ignore[assignment]

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import pytest


def _make_mock_dashscope_response(embeddings=None):
    """Build a minimal mock of dashscope DashScopeAPIResponse for embeddings."""
    if embeddings is None:
        embeddings = [{"text_index": 0, "embedding": [0.1] * 1024}]

    response = MagicMock()
    response.status_code = 200
    response.message = ""
    # response.output is accessed like a dict via .get()
    response.output.get = lambda key, default=None: embeddings if key == "embeddings" else default
    response.usage = MagicMock()
    return response


class TestQwenEmbedderConfig:
    """Test that the Qwen/DashScope embedder configuration is present and correct."""

    def test_embedder_dashscope_config_exists(self):
        """embedder_dashscope must be present in configs after loading."""
        from api.config import configs
        assert "embedder_dashscope" in configs, (
            "embedder_dashscope config is missing from configs"
        )

    def test_embedder_dashscope_uses_dashscope_client(self):
        """embedder_dashscope must reference DashscopeClient."""
        from api.config import configs
        cfg = configs["embedder_dashscope"]
        # model_client is the resolved class, client_class is the string name
        client_class = cfg.get("client_class", "")
        model_client = cfg.get("model_client")
        assert client_class == "DashscopeClient" or (
            model_client is not None and model_client.__name__ == "DashscopeClient"
        ), f"embedder_dashscope should use DashscopeClient, got client_class={client_class!r}"

    def test_embedder_dashscope_model_is_qwen3_vl_embedding(self):
        """embedder_dashscope must use the qwen3-vl-embedding model."""
        from api.config import configs
        cfg = configs["embedder_dashscope"]
        model = cfg.get("model_kwargs", {}).get("model")
        assert model == "qwen3-vl-embedding", (
            f"Expected model 'qwen3-vl-embedding', got {model!r}"
        )

    def test_default_embedder_type_is_dashscope(self):
        """Default DEEPWIKI_EMBEDDER_TYPE should be 'dashscope'."""
        import importlib
        import api.config as config_mod

        original = os.environ.get("DEEPWIKI_EMBEDDER_TYPE")
        try:
            # Remove env var so the default kicks in
            if "DEEPWIKI_EMBEDDER_TYPE" in os.environ:
                del os.environ["DEEPWIKI_EMBEDDER_TYPE"]
            importlib.reload(config_mod)
            assert config_mod.EMBEDDER_TYPE == "dashscope", (
                f"Default EMBEDDER_TYPE should be 'dashscope', got {config_mod.EMBEDDER_TYPE!r}"
            )
        finally:
            if original is not None:
                os.environ["DEEPWIKI_EMBEDDER_TYPE"] = original
            elif "DEEPWIKI_EMBEDDER_TYPE" in os.environ:
                del os.environ["DEEPWIKI_EMBEDDER_TYPE"]
            importlib.reload(config_mod)

    def test_is_dashscope_embedder_function_exists(self):
        """is_dashscope_embedder helper must be importable from api.config."""
        from api.config import is_dashscope_embedder
        assert callable(is_dashscope_embedder)

    def test_get_embedder_type_returns_dashscope_when_set(self):
        """get_embedder_type() returns 'dashscope' when DEEPWIKI_EMBEDDER_TYPE=dashscope."""
        import importlib
        import api.config as config_mod

        original = os.environ.get("DEEPWIKI_EMBEDDER_TYPE")
        try:
            os.environ["DEEPWIKI_EMBEDDER_TYPE"] = "dashscope"
            importlib.reload(config_mod)
            embedder_type = config_mod.get_embedder_type()
            assert embedder_type == "dashscope", (
                f"Expected 'dashscope', got {embedder_type!r}"
            )
        finally:
            if original is not None:
                os.environ["DEEPWIKI_EMBEDDER_TYPE"] = original
            elif "DEEPWIKI_EMBEDDER_TYPE" in os.environ:
                del os.environ["DEEPWIKI_EMBEDDER_TYPE"]
            importlib.reload(config_mod)


class TestQwenEmbedderFactory:
    """Test that get_embedder can create a DashScope embedder."""

    def test_get_embedder_dashscope_explicit(self):
        """get_embedder(embedder_type='dashscope') must succeed."""
        from api.tools.embedder import get_embedder

        # DashscopeClient requires DASHSCOPE_API_KEY; mock the init
        with patch("api.dashscope_client.DashscopeClient.init_sync_client") as mock_init:
            mock_init.return_value = MagicMock()
            embedder = get_embedder(embedder_type="dashscope")
        assert embedder is not None, "Dashscope embedder should be created"

    def test_get_embedder_auto_detects_dashscope(self):
        """When DEEPWIKI_EMBEDDER_TYPE=dashscope, auto-detection returns dashscope embedder."""
        import importlib
        import api.config as config_mod

        original = os.environ.get("DEEPWIKI_EMBEDDER_TYPE")
        try:
            os.environ["DEEPWIKI_EMBEDDER_TYPE"] = "dashscope"
            importlib.reload(config_mod)

            from api.tools.embedder import get_embedder
            with patch("api.dashscope_client.DashscopeClient.init_sync_client") as mock_init:
                mock_init.return_value = MagicMock()
                embedder = get_embedder()
            assert embedder is not None, "Auto-detected dashscope embedder should be created"
        finally:
            if original is not None:
                os.environ["DEEPWIKI_EMBEDDER_TYPE"] = original
            elif "DEEPWIKI_EMBEDDER_TYPE" in os.environ:
                del os.environ["DEEPWIKI_EMBEDDER_TYPE"]
            importlib.reload(config_mod)


class TestQwenEmbedderClient:
    """Test DashscopeClient embedding call with qwen3-vl-embedding (mocked)."""

    def test_convert_inputs_to_api_kwargs_formats_dashscope_input(self):
        """convert_inputs_to_api_kwargs should produce [{'text': ...}] dicts for EMBEDDER."""
        from api.dashscope_client import DashscopeClient
        from adalflow.core.types import ModelType

        with patch("api.dashscope_client.DashscopeClient.init_sync_client") as mock_init:
            mock_init.return_value = MagicMock()
            client = DashscopeClient()

        api_kwargs = client.convert_inputs_to_api_kwargs(
            input=["测试文本", "second text"],
            model_kwargs={"model": "qwen3-vl-embedding"},
            model_type=ModelType.EMBEDDER,
        )
        assert api_kwargs.get("model") == "qwen3-vl-embedding"
        assert api_kwargs["input"] == [{"text": "测试文本"}, {"text": "second text"}]

    def test_dashscope_embedding_call_uses_multimodal_embedding(self):
        """DashscopeClient.call() for EMBEDDER should use dashscope.MultiModalEmbedding.call()."""
        from api.dashscope_client import DashscopeClient
        from adalflow.core.types import ModelType

        mock_response = _make_mock_dashscope_response()

        with patch("api.dashscope_client.DashscopeClient.init_sync_client") as mock_init:
            mock_init.return_value = MagicMock()
            client = DashscopeClient()

        api_kwargs = client.convert_inputs_to_api_kwargs(
            input="测试文本",
            model_kwargs={"model": "qwen3-vl-embedding"},
            model_type=ModelType.EMBEDDER,
        )
        assert api_kwargs.get("model") == "qwen3-vl-embedding"

        with patch("api.dashscope_client.MultiModalEmbedding.call", return_value=mock_response) as mock_call:
            result = client.call(api_kwargs, ModelType.EMBEDDER)
            mock_call.assert_called_once()
            call_kwargs = mock_call.call_args[1]
            assert call_kwargs.get("model") == "qwen3-vl-embedding"
            assert call_kwargs["input"] == [{"text": "测试文本"}]

    def test_dashscope_embedding_response_parsed(self):
        """parse_embedding_response must return EmbedderOutput with non-empty data."""
        from api.dashscope_client import DashscopeClient

        mock_response = _make_mock_dashscope_response()

        with patch("api.dashscope_client.DashscopeClient.init_sync_client") as mock_init:
            mock_init.return_value = MagicMock()
            client = DashscopeClient()

        result = client.parse_embedding_response(mock_response)
        assert result is not None
        assert result.data is not None
        assert len(result.data) > 0, "Parsed response should have at least one embedding"
        assert result.error is None
        assert len(result.data[0].embedding) == 1024

    def test_dashscope_embedding_error_response(self):
        """parse_embedding_response should return error EmbedderOutput on non-200 status."""
        from api.dashscope_client import DashscopeClient

        error_response = MagicMock()
        error_response.status_code = 400
        error_response.message = "Bad Request"

        with patch("api.dashscope_client.DashscopeClient.init_sync_client") as mock_init:
            mock_init.return_value = MagicMock()
            client = DashscopeClient()

        result = client.parse_embedding_response(error_response)
        assert result is not None
        assert result.error is not None
        assert result.data == []


class TestQwenCountTokens:
    """Test that count_tokens handles the 'dashscope' embedder type."""

    def test_count_tokens_dashscope(self):
        """count_tokens with embedder_type='dashscope' should return a positive int."""
        from api.data_pipeline import count_tokens

        count = count_tokens("Hello, world!", embedder_type="dashscope")
        assert isinstance(count, int)
        assert count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
