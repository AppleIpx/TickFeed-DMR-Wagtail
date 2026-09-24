from typing import TYPE_CHECKING, Any, Self

from django.db.models import (
    CASCADE,
    CharField,
    DateTimeField,
    DecimalField,
    ForeignKey,
    Index,
    Model,
    TextChoices,
    UniqueConstraint,
)
from django.utils.translation import gettext_lazy as _

from tickfeeddmr.market_data.models.base import AssetBase

if TYPE_CHECKING:
    from collections.abc import Collection


class CryptoExchange(TextChoices):
    """Биржа — источник крипто-пары."""

    BINANCE = "BINANCE", _("Binance")


class CryptoTradeSide(TextChoices):
    """Сторона сделки.

    Значения совпадают с `TradeEvent.side` (`Literal["buy", "sell"]`) и с
    `StockTradeSide` у акций.
    """

    BUY = "buy", _("покупка")
    SELL = "sell", _("продажа")


SUBSCRIPTION_TRACKED_FIELDS = ("exchange", "trading_pair", "is_active")


class CryptoAsset(AssetBase):
    """Крипто-пара, отслеживаемая на конкретной бирже."""

    exchange = CharField(_("биржа"), max_length=50, choices=CryptoExchange)
    trading_pair = CharField(_("торговая пара"), max_length=20)
    provider_asset_id = CharField(
        _("id актива у провайдера"),
        max_length=100,
        blank=True,
        help_text=_("Необязательный id этого актива у резервного провайдера данных."),
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["exchange", "trading_pair"],
                name="unique_crypto_exchange_trading_pair",
            ),
        ]
        verbose_name = _("крипто-актив")
        verbose_name_plural = _("крипто-активы")

    _subscription_snapshot: dict[str, object] | None = None

    def __str__(self) -> str:
        return f"{self.symbol} ({self.exchange}:{self.trading_pair})"

    @classmethod
    def from_db(
        cls,
        db: str | None,
        field_names: Collection[str],
        values: Collection[Any],
        **kwargs: Any,
    ) -> Self:
        instance = super().from_db(db, field_names, values, **kwargs)
        instance.remember_subscription_fields()
        return instance

    def remember_subscription_fields(self) -> None:
        """Запомнить текущие значения отслеживаемых полей."""
        deferred = self.get_deferred_fields()
        self._subscription_snapshot = {
            name: getattr(self, name)
            for name in SUBSCRIPTION_TRACKED_FIELDS
            if name not in deferred
        }

    def subscription_fields_changed(
        self,
        update_fields: Collection[str] | None,
    ) -> bool:
        """Изменилось ли поле, влияющее на подписку, с момента снимка."""
        tracked = [
            name
            for name in SUBSCRIPTION_TRACKED_FIELDS
            if update_fields is None or name in update_fields
        ]
        if not tracked:
            return False
        snapshot = self._subscription_snapshot
        if snapshot is None:
            return True
        deferred = self.get_deferred_fields()
        return any(
            name not in snapshot or snapshot[name] != getattr(self, name)
            for name in tracked
            if name not in deferred
        )


class CryptoPriceSnapshot(Model):
    """Точка цены `CryptoAsset` в конкретный момент времени.

    Одна строка на сделку/тик, полученный с биржи, либо на точку истории
    из бэкфилла —  для полной истории по одному активу.

    """

    asset = ForeignKey(
        CryptoAsset,
        on_delete=CASCADE,
        related_name="price_snapshots",
        verbose_name=_("актив"),
    )
    price = DecimalField(_("цена"), max_digits=20, decimal_places=8)
    volume = DecimalField(
        _("объём"),
        max_digits=24,
        decimal_places=8,
        null=True,
        blank=True,
    )
    side = CharField(  # noqa: DJ001 — см. обоснование у `trade_id` ниже
        _("сторона"),
        max_length=4,
        choices=CryptoTradeSide,
        null=True,
        blank=True,
        help_text=_(
            "Пусто у строк, записанных до этапа 8a — тогда сторона не персистилась.",
        ),
    )
    trade_id = CharField(  # noqa: DJ001
        _("id сделки у биржи"),
        max_length=64,
        null=True,
        blank=True,
        help_text=_(
            "`TradeEvent.trade_id` с биржи. Пусто у строк, записанных до "
            "этапа 8a. Основа идемпотентности повторного прогона "
            "консьюмера — см. `UniqueConstraint` ниже.",
        ),
    )
    timestamp = DateTimeField(_("метка времени"), db_index=True)
    created_at = DateTimeField(_("создано"), auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        constraints = [
            UniqueConstraint(
                fields=["asset", "trade_id"],
                name="unique_crypto_snapshot_asset_trade_id",
            ),
        ]
        indexes = [
            Index(fields=["asset", "-timestamp"], name="crypto_snap_asset_ts_idx"),
        ]
        verbose_name = _("снапшот цены крипто-актива")
        verbose_name_plural = _("снапшоты цен крипто-активов")

    def __str__(self) -> str:
        return f"{self.asset.symbol} @ {self.timestamp}: {self.price}"
