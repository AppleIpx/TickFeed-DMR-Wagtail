from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from django.conf import settings
from redis.asyncio import Redis

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from pytest_django.fixtures import Settings


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client: Redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def consumer_stream_key(settings: Settings) -> str:
    """Ключ стрима для `tests/pipeline/test_consume_market_data_stream.py`."""
    key = f"test-market-data-trades-{uuid.uuid4()}"
    settings.MARKET_DATA_TRADE_STREAM_KEY = key
    return key


@pytest.fixture
def moex_trade_stream_key() -> str:
    """Ключ стрима для `tests/pipeline/test_moex_trade_stream.py`."""
    return f"test-moex-trade-stream-{uuid.uuid4()}"


@pytest.fixture
def retention_stream_key() -> str:
    """Ключ стрима для `tests/pipeline/test_trade_stream_retention.py`."""
    return f"test-retention-{uuid.uuid4()}"


@pytest.fixture
def stream_reader_stream_key() -> str:
    """Ключ стрима для `tests/pipeline/test_stream_reader.py`."""
    return f"test-stream-reader-{uuid.uuid4()}"
