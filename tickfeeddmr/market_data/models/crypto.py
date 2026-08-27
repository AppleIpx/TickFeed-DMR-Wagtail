from django.db.models import (
    CASCADE,
    CharField,
    DateTimeField,
    DecimalField,
    ForeignKey,
    Index,
    Model,
    UniqueConstraint,
)
from django.utils.translation import gettext_lazy as _

from tickfeeddmr.market_data.models.base import AssetBase


class CryptoAsset(AssetBase):
    """Крипто-пара, отслеживаемая на конкретной бирже."""

    exchange = CharField(_("биржа"), max_length=50)
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

    def __str__(self) -> str:
        return f"{self.symbol} ({self.exchange}:{self.trading_pair})"


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
    timestamp = DateTimeField(_("метка времени"), db_index=True)
    created_at = DateTimeField(_("создано"), auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            Index(fields=["asset", "-timestamp"], name="crypto_snap_asset_ts_idx"),
        ]
        verbose_name = _("снапшот цены крипто-актива")
        verbose_name_plural = _("снапшоты цен крипто-активов")

    def __str__(self) -> str:
        return f"{self.asset.symbol} @ {self.timestamp}: {self.price}"
