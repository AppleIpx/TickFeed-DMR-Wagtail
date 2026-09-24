"""Стрим изменений `CryptoAsset`: wire-контракт, publisher, listener, настройки."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from django.core.exceptions import ImproperlyConfigured

from tickfeeddmr.market_data.services.crypto_asset_changes import (
    MALFORMED_ASSET_CHANGE_ERRORS,
    CryptoAssetChange,
    deserialize_crypto_asset_change,
    serialize_crypto_asset_change,
)
from tickfeeddmr.market_data.services.crypto_asset_changes.listener import (
    read_asset_changes,
    resolve_start_id,
)
from tickfeeddmr.market_data.services.crypto_asset_changes.publisher import (
    publish_crypto_asset_change,
)
from tickfeeddmr.market_data.services.crypto_asset_changes.settings import (
    validate_crypto_asset_change_settings,
)

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings
    from redis.asyncio import Redis

READ_BLOCK_MS = 10
READ_COUNT = 100

CHANGE = CryptoAssetChange(
    asset_id=42,
    kind="updated",
    exchange="BINANCE",
    trading_pair="BTCUSDT",
)


def _fields(**overrides: str) -> dict[str, str]:
    return serialize_crypto_asset_change(CHANGE) | overrides


# --- Сериализация --------------------------------------------------------------


@pytest.mark.parametrize("kind", ["created", "updated", "deleted"])
def test_serialization_roundtrip(kind: str) -> None:
    change = CryptoAssetChange(
        asset_id=7,
        kind=kind,  # type: ignore[arg-type]
        exchange="BINANCE",
        trading_pair="ETHUSDT",
    )

    fields = serialize_crypto_asset_change(change)

    assert all(isinstance(value, str) for value in fields.values())
    assert deserialize_crypto_asset_change(fields) == change


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param(_fields(kind="renamed"), id="unknown-kind"),
        pytest.param(_fields(asset_id="not-an-int"), id="bad-asset-id"),
        pytest.param(
            {k: v for k, v in _fields().items() if k != "kind"},
            id="missing-kind",
        ),
        pytest.param(
            {k: v for k, v in _fields().items() if k != "trading_pair"},
            id="missing-trading-pair",
        ),
        pytest.param({}, id="empty"),
    ],
)
def test_deserialize_malformed_fields_raises_declared_error(
    fields: dict[str, str],
) -> None:
    with pytest.raises(MALFORMED_ASSET_CHANGE_ERRORS):
        deserialize_crypto_asset_change(fields)


# --- Publisher -----------------------------------------------------------------


async def test_publish_appends_serialized_change_to_stream(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
) -> None:
    publish_crypto_asset_change(CHANGE)

    entries = await redis_client.xrange(crypto_asset_changes_stream_key)
    assert [deserialize_crypto_asset_change(f) for _id, f in entries] == [CHANGE]


def test_publish_with_unreachable_redis_logs_error_and_does_not_raise(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings.REDIS_URL = "redis://127.0.0.1:1/0"

    with caplog.at_level(logging.ERROR):
        publish_crypto_asset_change(CHANGE)

    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "не отправлено в Redis" in errors[0].message
    assert "BTCUSDT" in errors[0].message


# --- Listener ------------------------------------------------------------------


async def test_resolve_start_id_on_missing_stream_is_zero(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
) -> None:
    assert await resolve_start_id(redis_client, crypto_asset_changes_stream_key) == (
        "0-0"
    )


async def test_resolve_start_id_returns_last_entry_id(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
) -> None:
    await redis_client.xadd(crypto_asset_changes_stream_key, _fields())
    last_id = await redis_client.xadd(crypto_asset_changes_stream_key, _fields())

    assert await resolve_start_id(redis_client, crypto_asset_changes_stream_key) == (
        last_id
    )


async def test_read_asset_changes_returns_none_when_nothing_arrives(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
) -> None:
    batch = await read_asset_changes(
        redis_client,
        stream_key=crypto_asset_changes_stream_key,
        last_id="0-0",
        count=READ_COUNT,
        block_ms=READ_BLOCK_MS,
    )

    assert batch is None


async def test_read_asset_changes_reads_only_after_last_id(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
) -> None:
    seen_id = await redis_client.xadd(crypto_asset_changes_stream_key, _fields())
    new_id = await redis_client.xadd(
        crypto_asset_changes_stream_key,
        _fields(kind="deleted"),
    )

    batch = await read_asset_changes(
        redis_client,
        stream_key=crypto_asset_changes_stream_key,
        last_id=seen_id,
        count=READ_COUNT,
        block_ms=READ_BLOCK_MS,
    )

    assert batch is not None
    assert batch.last_id == new_id
    assert [change.kind for change in batch.changes] == ["deleted"]


async def test_read_asset_changes_logs_malformed_entry_and_keeps_its_id(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await redis_client.xadd(crypto_asset_changes_stream_key, _fields())
    broken_id = await redis_client.xadd(
        crypto_asset_changes_stream_key,
        _fields(kind="renamed"),
    )

    with caplog.at_level(logging.ERROR):
        batch = await read_asset_changes(
            redis_client,
            stream_key=crypto_asset_changes_stream_key,
            last_id="0-0",
            count=READ_COUNT,
            block_ms=READ_BLOCK_MS,
        )

    assert batch is not None
    # Битая запись последняя — `last_id` всё равно её, иначе стример
    # перечитывал бы её вечно.
    assert batch.last_id == broken_id
    assert batch.changes == (CHANGE,)
    errors = [r.message for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == [f"Битая запись в стриме изменений CryptoAsset, id={broken_id}"]


async def test_read_asset_changes_batch_of_only_malformed_entries_is_not_none(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
) -> None:
    """Пачка из одних битых записей — всё равно повод для сверки."""
    broken_id = await redis_client.xadd(crypto_asset_changes_stream_key, {"x": "1"})

    batch = await read_asset_changes(
        redis_client,
        stream_key=crypto_asset_changes_stream_key,
        last_id="0-0",
        count=READ_COUNT,
        block_ms=READ_BLOCK_MS,
    )

    assert batch is not None
    assert batch.last_id == broken_id
    assert batch.changes == ()


async def test_read_asset_changes_respects_count(
    redis_client: Redis,
    crypto_asset_changes_stream_key: str,
) -> None:
    first_id = await redis_client.xadd(crypto_asset_changes_stream_key, _fields())
    await redis_client.xadd(crypto_asset_changes_stream_key, _fields())

    batch = await read_asset_changes(
        redis_client,
        stream_key=crypto_asset_changes_stream_key,
        last_id="0-0",
        count=1,
        block_ms=READ_BLOCK_MS,
    )

    assert batch is not None
    assert batch.last_id == first_id
    assert len(batch.changes) == 1


# --- Настройки -----------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "MARKET_DATA_CRYPTO_ASSET_CHANGES_MAXLEN",
        "MARKET_DATA_CRYPTO_ASSET_CHANGES_READ_BLOCK_MS",
        "MARKET_DATA_CRYPTO_ASSET_CHANGES_READ_COUNT",
        "MARKET_DATA_CRYPTO_ASSET_CHANGES_PUBLISH_TIMEOUT_SECONDS",
    ],
)
def test_non_positive_setting_is_rejected(settings: Settings, name: str) -> None:
    setattr(settings, name, 0)

    with pytest.raises(ImproperlyConfigured, match=name):
        validate_crypto_asset_change_settings()


def test_default_settings_are_valid() -> None:
    validate_crypto_asset_change_settings()
