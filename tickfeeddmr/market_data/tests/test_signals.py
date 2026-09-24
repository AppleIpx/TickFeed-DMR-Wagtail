from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import msgspec
import pytest
import redis
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from tickfeeddmr.market_data import tasks
from tickfeeddmr.market_data.models import CryptoAsset
from tickfeeddmr.market_data.services.crypto_asset_changes import (
    CryptoAssetChange,
    deserialize_crypto_asset_change,
)
from tickfeeddmr.market_data.tests.factories import (
    CryptoAssetFactory,
    FiatCurrencyFactory,
    StockAssetFactory,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_django.fixtures import Settings

pytestmark = pytest.mark.django_db(transaction=True)


class DomainCase(msgspec.Struct, frozen=True):
    factory: Any
    task_name: str


CASES = [
    DomainCase(CryptoAssetFactory, "catch_up_crypto_asset_history"),
    DomainCase(StockAssetFactory, "catch_up_stock_asset_history"),
    DomainCase(FiatCurrencyFactory, "catch_up_fiat_asset_history"),
]
CASE_IDS = ["crypto", "stock", "fiat"]


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
async def test_creating_asset_queues_signal_catch_up_with_its_id(
    case: DomainCase,
) -> None:
    task = getattr(tasks, case.task_name)

    asset = await sync_to_async(case.factory.create)()

    task.delay.assert_called_once_with(asset_id=asset.pk)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
async def test_updating_existing_asset_does_not_queue_signal_catch_up(
    case: DomainCase,
) -> None:
    task = getattr(tasks, case.task_name)
    asset = await sync_to_async(case.factory.create)()
    task.delay.reset_mock()

    asset.display_name = "updated"
    await sync_to_async(asset.save)(update_fields=["display_name"])

    task.delay.assert_not_called()


UNREACHABLE_REDIS_URL = "redis://127.0.0.1:1/0"

TRACKED_FIELD_NEW_VALUES = [
    ("exchange", "OTHER"),
    ("trading_pair", "NEWPAIR"),
    ("is_active", False),
]


def _published_changes(stream_key: str) -> list[CryptoAssetChange]:
    client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        entries = client.xrange(stream_key)
    finally:
        client.close()
    return [deserialize_crypto_asset_change(fields) for _id, fields in entries]


def _loaded_crypto_asset(**kwargs: object) -> CryptoAsset:
    """Актив, загруженный из БД — как его видит админка при редактировании."""
    return CryptoAsset.objects.get(pk=CryptoAssetFactory.create(**kwargs).pk)


def test_creating_crypto_asset_publishes_created_event(
    crypto_asset_changes_stream_key: str,
) -> None:
    asset = CryptoAssetFactory.create(trading_pair="BTCUSDT")

    assert _published_changes(crypto_asset_changes_stream_key) == [
        CryptoAssetChange(
            asset_id=asset.pk,
            kind="created",
            exchange="BINANCE",
            trading_pair="BTCUSDT",
        ),
    ]


@pytest.mark.parametrize(("field", "value"), TRACKED_FIELD_NEW_VALUES)
def test_changing_tracked_field_publishes_one_updated_event(
    crypto_asset_changes_stream_key: str,
    field: str,
    value: object,
) -> None:
    asset = _loaded_crypto_asset()

    setattr(asset, field, value)
    asset.save()

    changes = _published_changes(crypto_asset_changes_stream_key)
    assert [change.kind for change in changes] == ["created", "updated"]
    assert changes[-1].asset_id == asset.pk
    if field != "is_active":  # `is_active` в событие не входит
        assert getattr(changes[-1], field) == value


def test_deleting_crypto_asset_publishes_deleted_event_with_old_id(
    crypto_asset_changes_stream_key: str,
) -> None:
    asset = _loaded_crypto_asset(trading_pair="BTCUSDT")
    asset_id = asset.pk

    asset.delete()

    assert _published_changes(crypto_asset_changes_stream_key)[-1] == (
        CryptoAssetChange(
            asset_id=asset_id,
            kind="deleted",
            exchange="BINANCE",
            trading_pair="BTCUSDT",
        )
    )


def test_deleting_crypto_asset_loaded_with_deferred_fields_still_publishes(
    crypto_asset_changes_stream_key: str,
) -> None:
    asset_id = CryptoAssetFactory.create().pk
    asset = CryptoAsset.objects.only("id").get(pk=asset_id)

    asset.delete()

    last = _published_changes(crypto_asset_changes_stream_key)[-1]
    assert (last.kind, last.asset_id, last.trading_pair) == ("deleted", asset_id, "")


def test_saving_without_changes_publishes_nothing(
    crypto_asset_changes_stream_key: str,
) -> None:
    asset = _loaded_crypto_asset()

    asset.display_name = "другое имя"
    asset.save()

    assert len(_published_changes(crypto_asset_changes_stream_key)) == 1  # created


def test_update_fields_without_tracked_fields_publishes_nothing(
    crypto_asset_changes_stream_key: str,
) -> None:
    asset = _loaded_crypto_asset()

    asset.is_active = False
    asset.save(update_fields=["display_name"])

    assert len(_published_changes(crypto_asset_changes_stream_key)) == 1  # created


def test_saving_same_instance_again_after_change_publishes_once(
    crypto_asset_changes_stream_key: str,
) -> None:
    asset = _loaded_crypto_asset()

    asset.is_active = False
    asset.save()
    asset.save()

    kinds = [c.kind for c in _published_changes(crypto_asset_changes_stream_key)]
    assert kinds == ["created", "updated"]


def test_created_instance_saved_again_without_changes_publishes_once(
    crypto_asset_changes_stream_key: str,
) -> None:
    asset = CryptoAssetFactory.create()

    asset.save()

    kinds = [c.kind for c in _published_changes(crypto_asset_changes_stream_key)]
    assert kinds == ["created"]


def test_raw_save_publishes_nothing_and_queues_no_catch_up(
    crypto_asset_changes_stream_key: str,
) -> None:
    """`raw=True` — так сохраняет `loaddata`."""
    now = timezone.now()
    # Raw-сохранение не выставляет `auto_now`/`auto_now_add` — как и фикстура,
    # оно пишет значения как есть.
    asset = CryptoAssetFactory.build(created_at=now, updated_at=now)

    asset.save_base(raw=True)

    assert CryptoAsset.objects.filter(pk=asset.pk).exists()
    assert _published_changes(crypto_asset_changes_stream_key) == []
    tasks.catch_up_crypto_asset_history.delay.assert_not_called()


def test_rolled_back_create_publishes_nothing(
    crypto_asset_changes_stream_key: str,
) -> None:
    with pytest.raises(_RollbackError):
        _rolled_back(CryptoAssetFactory.create)

    assert _published_changes(crypto_asset_changes_stream_key) == []


def test_rolled_back_update_publishes_nothing(
    crypto_asset_changes_stream_key: str,
) -> None:
    asset = _loaded_crypto_asset()

    asset.is_active = False

    with pytest.raises(_RollbackError):
        _rolled_back(asset.save)

    kinds = [c.kind for c in _published_changes(crypto_asset_changes_stream_key)]
    assert kinds == ["created"]


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Баг: post_save обновляет снимок до коммита — после отката повторный "
        "save() того же инстанса не видит изменения и событие теряется"
    ),
)
def test_resaving_instance_after_rolled_back_update_publishes_event(
    crypto_asset_changes_stream_key: str,
) -> None:
    asset = _loaded_crypto_asset()
    asset.is_active = False
    with pytest.raises(_RollbackError):
        _rolled_back(asset.save)

    asset.save()  # теперь is_active=False действительно попадает в БД

    assert not CryptoAsset.objects.get(pk=asset.pk).is_active
    kinds = [c.kind for c in _published_changes(crypto_asset_changes_stream_key)]
    assert kinds == ["created", "updated"]


def test_successful_publish_logs_info(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        CryptoAssetFactory.create(trading_pair="BTCUSDT")

    assert any(
        "отправлено в Redis для stream_binance" in r.message and "BTCUSDT" in r.message
        for r in caplog.records
        if r.levelno == logging.INFO
    )


def test_unreachable_redis_logs_error_but_save_succeeds_and_catch_up_is_queued(
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings.REDIS_URL = UNREACHABLE_REDIS_URL

    with caplog.at_level(logging.ERROR):
        asset = CryptoAssetFactory.create(trading_pair="BTCUSDT")

    assert CryptoAsset.objects.filter(pk=asset.pk).exists()
    tasks.catch_up_crypto_asset_history.delay.assert_called_once_with(
        asset_id=asset.pk,
    )
    errors = [r.message for r in caplog.records if r.levelno == logging.ERROR]
    assert any("не отправлено в Redis" in message for message in errors)


class _RollbackError(Exception):
    pass


def _rolled_back(action: Callable[[], object]) -> None:
    with transaction.atomic():
        action()
        raise _RollbackError
