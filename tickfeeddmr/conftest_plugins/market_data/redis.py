from __future__ import annotations

import uuid
from contextlib import suppress
from typing import TYPE_CHECKING

import pytest
import redis
from django.conf import settings
from redis.asyncio import Redis
from redis.exceptions import RedisError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

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


_CLEANUP_TIMEOUT_SECONDS = 0.5


@pytest.fixture(autouse=True)
def crypto_asset_changes_stream_key(settings: Settings) -> Iterator[str]:
    """Свой ключ стрима изменений `CryptoAsset` на каждый тест.

    Autouse: сигналы `CryptoAsset` публикуют событие из любого
    transactional-теста, создающего/меняющего/удаляющего актив, — без подмены
    `XADD` уходил бы в боевой `market_data:crypto:asset_changes`, который
    читает живой `stream_binance` на локальном стеке.
    """
    key = f"test-crypto-asset-changes-{uuid.uuid4()}"
    settings.MARKET_DATA_CRYPTO_ASSET_CHANGES_STREAM_KEY = key
    yield key
    client = redis.Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=_CLEANUP_TIMEOUT_SECONDS,
        socket_timeout=_CLEANUP_TIMEOUT_SECONDS,
    )
    try:
        with suppress(RedisError):
            client.delete(key)
    finally:
        client.close()


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
