from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from asgiref.sync import sync_to_async

from tickfeeddmr.market_data.models import CryptoPriceSnapshot
from tickfeeddmr.market_data.services.queries.cursor import (
    decode_cursor,
    encode_cursor,
    fetch_cursor_page,
)
from tickfeeddmr.market_data.services.queries.errors import InvalidCursorError
from tickfeeddmr.market_data.tests.factories import CryptoPriceSnapshotFactory

if TYPE_CHECKING:
    from tickfeeddmr.market_data.models import CryptoAsset

pytestmark = pytest.mark.django_db(transaction=True)

_PAGE_LIMIT = 3
_CURSOR_PK = 42


def test_encode_decode_cursor_round_trip() -> None:
    timestamp = datetime(2026, 1, 1, 12, 30, tzinfo=UTC)

    cursor = decode_cursor(encode_cursor(timestamp=timestamp, pk=_CURSOR_PK))

    assert cursor.timestamp == timestamp
    assert cursor.pk == _CURSOR_PK


def test_decode_cursor_garbage_raises_invalid_cursor_error() -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor("not-a-valid-cursor")


def _make_rows_sync(asset: CryptoAsset, count: int) -> list[CryptoPriceSnapshot]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        CryptoPriceSnapshotFactory.create(
            asset=asset,
            timestamp=base + timedelta(minutes=i),
        )
        for i in range(count)
    ]


async def _make_rows(asset: CryptoAsset, count: int) -> list[CryptoPriceSnapshot]:
    return await sync_to_async(_make_rows_sync)(asset, count)


async def test_fetch_cursor_page_exact_limit_has_no_next_cursor(
    crypto_asset: CryptoAsset,
) -> None:
    await _make_rows(crypto_asset, _PAGE_LIMIT)

    page, next_cursor = await fetch_cursor_page(
        CryptoPriceSnapshot.objects.filter(asset=crypto_asset),
        cursor=None,
        limit=_PAGE_LIMIT,
    )

    assert len(page) == _PAGE_LIMIT
    assert next_cursor is None


async def test_fetch_cursor_page_one_over_limit_has_next_cursor(
    crypto_asset: CryptoAsset,
) -> None:
    rows = await _make_rows(crypto_asset, _PAGE_LIMIT + 1)

    page, next_cursor = await fetch_cursor_page(
        CryptoPriceSnapshot.objects.filter(asset=crypto_asset),
        cursor=None,
        limit=_PAGE_LIMIT,
    )

    assert len(page) == _PAGE_LIMIT
    assert next_cursor is not None
    assert [row.pk for row in page] == [row.pk for row in reversed(rows[1:])]


async def test_fetch_cursor_page_second_page_returns_remaining_row(
    crypto_asset: CryptoAsset,
) -> None:
    rows = await _make_rows(crypto_asset, _PAGE_LIMIT + 1)

    first_page, next_cursor = await fetch_cursor_page(
        CryptoPriceSnapshot.objects.filter(asset=crypto_asset),
        cursor=None,
        limit=_PAGE_LIMIT,
    )
    assert next_cursor is not None

    second_page, second_next_cursor = await fetch_cursor_page(
        CryptoPriceSnapshot.objects.filter(asset=crypto_asset),
        cursor=decode_cursor(next_cursor),
        limit=_PAGE_LIMIT,
    )

    assert [row.pk for row in second_page] == [rows[0].pk]
    assert second_next_cursor is None
    first_pks = {row.pk for row in first_page}
    second_pks = {row.pk for row in second_page}
    assert not first_pks & second_pks
