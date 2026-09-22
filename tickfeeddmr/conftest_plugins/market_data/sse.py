from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings


@pytest.fixture
def fast_crypto_sse_settings(settings: Settings) -> None:
    """Для `tests/api/test_crypto_stream.py`."""
    settings.MARKET_DATA_SSE_WINDOW_SECONDS = 0.05
    settings.MARKET_DATA_SSE_HEARTBEAT_SECONDS = 0.1
    settings.MARKET_DATA_TRADE_STREAM_KEY = f"test-crypto-stream-{uuid.uuid4()}"


@pytest.fixture
def fast_stock_sse_settings(settings: Settings) -> None:
    """Для `tests/api/test_stock_stream.py` (см. `fast_crypto_sse_settings`)."""
    settings.MARKET_DATA_SSE_WINDOW_SECONDS = 0.05
    settings.MARKET_DATA_SSE_HEARTBEAT_SECONDS = 0.1
    settings.MOEX_TRADE_STREAM_KEY = f"test-stock-stream-{uuid.uuid4()}"


@pytest.fixture
def fast_stream_reader_sse_settings(settings: Settings) -> None:
    """Для `tests/pipeline/test_stream_reader.py`."""
    settings.MARKET_DATA_SSE_WINDOW_SECONDS = 0.05
    settings.MARKET_DATA_SSE_HEARTBEAT_SECONDS = 0.2
    settings.MARKET_DATA_SSE_READ_COUNT = 500
