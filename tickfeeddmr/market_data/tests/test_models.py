"""Снимок полей подписки `CryptoAsset` (`from_db` / `subscription_fields_changed`)."""

from __future__ import annotations

import pytest

from tickfeeddmr.market_data.models import CryptoAsset
from tickfeeddmr.market_data.tests.factories import CryptoAssetFactory

pytestmark = pytest.mark.django_db

TRACKED_FIELD_NEW_VALUES = [
    ("exchange", "OTHER"),
    ("trading_pair", "NEWPAIR"),
    ("is_active", False),
]


def _loaded(asset: CryptoAsset) -> CryptoAsset:
    return CryptoAsset.objects.get(pk=asset.pk)


def test_from_db_remembers_tracked_fields() -> None:
    asset = _loaded(CryptoAssetFactory.create(trading_pair="BTCUSDT"))

    assert asset._subscription_snapshot == {  # noqa: SLF001
        "exchange": "BINANCE",
        "trading_pair": "BTCUSDT",
        "is_active": True,
    }
    assert not asset.subscription_fields_changed(None)


def test_instance_not_loaded_from_db_counts_as_changed() -> None:
    asset = CryptoAsset(symbol="BTC", exchange="BINANCE", trading_pair="BTCUSDT")

    assert asset.subscription_fields_changed(None)


@pytest.mark.parametrize(("field", "value"), TRACKED_FIELD_NEW_VALUES)
def test_changing_tracked_field_is_detected(field: str, value: object) -> None:
    asset = _loaded(CryptoAssetFactory.create())

    setattr(asset, field, value)

    assert asset.subscription_fields_changed(None)
    assert asset.subscription_fields_changed([field])


def test_changing_untracked_field_is_not_a_change() -> None:
    asset = _loaded(CryptoAssetFactory.create())

    asset.display_name = "другое имя"

    assert not asset.subscription_fields_changed(None)


def test_update_fields_without_tracked_fields_is_not_a_change() -> None:
    """`save(update_fields=[...])` не пишет изменённое в памяти `is_active`."""
    asset = _loaded(CryptoAssetFactory.create())

    asset.is_active = False

    assert not asset.subscription_fields_changed(["display_name"])


def test_remember_after_save_resets_change() -> None:
    asset = _loaded(CryptoAssetFactory.create())
    asset.is_active = False
    asset.save()

    asset.remember_subscription_fields()

    assert not asset.subscription_fields_changed(None)


def test_deferred_tracked_field_left_untouched_is_not_a_change() -> None:
    asset = CryptoAsset.objects.only("id", "symbol").get(
        pk=CryptoAssetFactory.create().pk,
    )

    assert asset._subscription_snapshot == {}  # noqa: SLF001
    assert not asset.subscription_fields_changed(None)


def test_deferred_tracked_field_set_afterwards_counts_as_changed() -> None:
    """Прежнее значение неизвестно — это изменение: лишняя сверка безвредна."""
    asset = CryptoAsset.objects.only("id", "symbol").get(
        pk=CryptoAssetFactory.create().pk,
    )

    asset.is_active = True

    assert asset.subscription_fields_changed(None)
