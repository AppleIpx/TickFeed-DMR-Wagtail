from django.db.models import (
    CASCADE,
    DateField,
    DateTimeField,
    DecimalField,
    ForeignKey,
    Index,
    Model,
    PositiveBigIntegerField,
    UniqueConstraint,
)
from django.utils.translation import gettext_lazy as _

from tickfeeddmr.market_data.models.crypto import CryptoAsset
from tickfeeddmr.market_data.models.stock import StockAsset


class DailyCandleBase(Model):
    """Общие поля дневной свечи — по образцу `AssetBase`.

    `open`/`high`/`low`/`close`/`volume` не вынесены сюда: у крипты и
    акций разная точность цены и разный тип объёма
    """

    date = DateField(_("торговый день"), db_index=True)
    created_at = DateTimeField(_("создано"), auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-date"]


class CryptoDailyCandle(DailyCandleBase):
    """Дневная свеча крипто-актива — берётся у Binance (`klines`, 1d, МСК)."""

    asset = ForeignKey(
        CryptoAsset,
        on_delete=CASCADE,
        related_name="daily_candles",
        verbose_name=_("актив"),
    )
    open = DecimalField(_("открытие"), max_digits=20, decimal_places=8)
    high = DecimalField(_("максимум"), max_digits=20, decimal_places=8)
    low = DecimalField(_("минимум"), max_digits=20, decimal_places=8)
    close = DecimalField(_("закрытие"), max_digits=20, decimal_places=8)
    volume = DecimalField(_("объём"), max_digits=24, decimal_places=8)

    class Meta(DailyCandleBase.Meta):
        constraints = [
            UniqueConstraint(
                fields=["asset", "date"],
                name="unique_crypto_daily_candle_asset_date",
            ),
        ]
        indexes = [
            Index(fields=["asset", "-date"], name="crypto_candle_asset_date_idx"),
        ]
        verbose_name = _("дневная свеча крипто-актива")
        verbose_name_plural = _("дневные свечи крипто-активов")

    def __str__(self) -> str:
        return f"{self.asset.symbol} @ {self.date}: {self.close}"


class StockDailyCandle(DailyCandleBase):
    """Дневная свеча акции — берётся у MOEX ISS (`candles.json`, interval=24)."""

    asset = ForeignKey(
        StockAsset,
        on_delete=CASCADE,
        related_name="daily_candles",
        verbose_name=_("актив"),
    )
    open = DecimalField(_("открытие"), max_digits=14, decimal_places=4)
    high = DecimalField(_("максимум"), max_digits=14, decimal_places=4)
    low = DecimalField(_("минимум"), max_digits=14, decimal_places=4)
    close = DecimalField(_("закрытие"), max_digits=14, decimal_places=4)
    volume = PositiveBigIntegerField(_("объём (лоты)"))
    value = DecimalField(_("оборот"), max_digits=20, decimal_places=2)

    class Meta(DailyCandleBase.Meta):
        constraints = [
            UniqueConstraint(
                fields=["asset", "date"],
                name="unique_stock_daily_candle_asset_date",
            ),
        ]
        indexes = [
            Index(fields=["asset", "-date"], name="stock_candle_asset_date_idx"),
        ]
        verbose_name = _("дневная свеча акции")
        verbose_name_plural = _("дневные свечи акций")

    def __str__(self) -> str:
        return f"{self.asset.symbol} @ {self.date}: {self.close}"
