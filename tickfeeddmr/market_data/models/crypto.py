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

    def __str__(self) -> str:
        return f"{self.symbol} ({self.exchange}:{self.trading_pair})"


class CryptoPriceSnapshot(Model):
    """Точка цены `CryptoAsset` в конкретный момент времени.

    Одна строка на сделку/тик, полученный с биржи, либо на точку истории
    из бэкфилла —  для полной истории по одному активу.

    `side`/`trade_id` — nullable: строки, записанные до этапа 8a, их не
    несут (в тот момент `write_snapshots` их не сохранял). `trade_id` —
    это и есть идемпотентность повторного прогона консьюмера
    (`UniqueConstraint` ниже, пробел №1 этапа 2): `services/ingest.py`
    пишет через `ignore_conflicts=True`, и повторная подача того же
    события с тем же `trade_id` не создаёт дубликат. Читающая сторона
    (этап 8a, `services/queries/crypto.py`) отдаёт в ленте сделок только
    строки с `trade_id IS NOT NULL` — старые строки без него физически
    не могут получить сторону/id заново, задним числом их не заполнить.
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
        # `null=True`, а не только `blank=True` (DJ001), — намеренно:
        # `UniqueConstraint(asset, trade_id)` ниже полагается на то, что
        # Postgres не считает несколько NULL конфликтующими друг с другом,
        # а пустые строки "" считал бы. Старые строки без `trade_id`
        # (до этапа 8a) иначе столкнулись бы друг с другом на уникальности.
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
