from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest

from config.api_base import DomainError
from tickfeeddmr.market_data.services.queries.errors import (
    AssetNotFoundError,
    InvalidCursorError,
    NoDataYetError,
    TradesNotTrackedError,
)

if TYPE_CHECKING:
    from dmr.test import DMRAsyncClient

    from tickfeeddmr.market_data.models import CryptoAsset

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize(
    ("error_cls", "expected_status"),
    [
        (AssetNotFoundError, HTTPStatus.NOT_FOUND),
        (NoDataYetError, HTTPStatus.NOT_FOUND),
        (TradesNotTrackedError, HTTPStatus.NOT_FOUND),
        (InvalidCursorError, HTTPStatus.UNPROCESSABLE_ENTITY),
    ],
)
def test_domain_errors_are_domain_error_subclasses_with_expected_status(
    error_cls: type[DomainError],
    expected_status: HTTPStatus,
) -> None:
    error = error_cls("сообщение")

    assert isinstance(error, DomainError)
    assert error.status_code == expected_status


async def test_dmr_native_validation_error_is_not_swallowed(
    dmr_async_client: DMRAsyncClient,
    crypto_asset: CryptoAsset,
) -> None:
    """`?limit=abc` — ошибка валидации самого DMR, не наш `AssetNotFoundError`"""
    response = await dmr_async_client.get(
        f"/api/crypto/assets/{crypto_asset.symbol}/trades?limit=abc",
    )

    body = response.json()
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert body["detail"]
    detail = body["detail"][0]
    assert detail["type"] == "value_error"
    assert "int" in detail["msg"]
    assert "str" in detail["msg"]
    assert "не найден" not in detail["msg"]
    assert "{" not in detail["msg"]
