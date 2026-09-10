from django.core.validators import RegexValidator
from django.db.models import (
    CASCADE,
    BigIntegerField,
    BooleanField,
    CharField,
    DateTimeField,
    DecimalField,
    ForeignKey,
    Index,
    Model,
    PositiveBigIntegerField,
    PositiveIntegerField,
    TextChoices,
    UniqueConstraint,
)
from django.utils.translation import gettext_lazy as _

from tickfeeddmr.market_data.models.base import AssetBase

# SECID ISS MOEX: заглавные латинские буквы и цифры, без "/", "?", "#" и
# прочих разделителей URL. `providers/moex/client.py` подставляет
# `StockAsset.symbol` прямо в путь запроса к ISS (`get_trades_page`,
# `get_candles`) — этот валидатор основная защита от path/query-injection
# в рамках хоста ISS через значение, редактируемое в Wagtail-админке;
# `urllib.parse.quote(..., safe="")` в клиенте — defense-in-depth поверх
# него, не замена.
SECID_VALIDATOR = RegexValidator(
    regex=r"^[A-Z0-9]+\Z",
    message=_(
        "SECID MOEX: только заглавные латинские буквы и цифры, без разделителей.",
    ),
)


class StockBoard(TextChoices):
    """Торговый борд MOEX.

    Хранится полем с `choices`, а не зашитой константой `"TQBR"` —
    решение этапа 4: добавление нового борда (например, СПБ Биржи) не
    должно требовать правки кода везде, где сейчас был бы захардкожен
    борд, а только добавления нового значения сюда.
    """

    TQBR = "TQBR", _("Т+ Акции и ДР")


class StockTradeSide(TextChoices):
    """Сторона сделки.

    Значения совпадают с `TradeEvent.side` (`Literal["buy", "sell"]`).
    """

    BUY = "buy", _("покупка")
    SELL = "sell", _("продажа")


class StockAsset(AssetBase):
    """Акция, отслеживаемая на конкретном борде MOEX."""

    symbol = CharField(
        _("символ"),
        max_length=20,
        unique=True,
        validators=[SECID_VALIDATOR],
        help_text=_(
            "SECID ISS MOEX (например, SBER) — переопределяет "
            "`AssetBase.symbol`, добавляя формат-валидацию: значение "
            "подставляется в путь URL запросов к ISS (см. "
            "`providers/moex/client.py`).",
        ),
    )
    board = CharField(
        _("борд"),
        max_length=10,
        choices=StockBoard,
        default=StockBoard.TQBR,
    )
    track_trades = BooleanField(
        _("вести ленту сделок"),
        default=False,
        help_text=_(
            "Полная лента сделок собирается только по избранным бумагам — "
            "объём ленты за день по ликвидной бумаге исчисляется сотнями "
            "тысяч сделок. Снимок цены борда идёт по всем активным бумагам "
            "независимо от этого флага.",
        ),
    )
    last_trade_no = BigIntegerField(
        _("курсор ленты (TRADENO)"),
        null=True,
        blank=True,
        help_text=_(
            "TRADENO последней записанной сделки — с него "
            "`poll_moex_trades` продолжает дочитывание. Пусто, если лента "
            "ещё ни разу не читалась.",
        ),
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["board", "symbol"],
                name="unique_stock_board_symbol",
            ),
        ]
        verbose_name = _("акция")
        verbose_name_plural = _("акции")

    def __str__(self) -> str:
        return f"{self.symbol} ({self.board})"


class StockPriceSnapshot(Model):
    """Снимок цены борда по `StockAsset` в конкретный момент времени.

    В отличие от `CryptoPriceSnapshot` (одна строка на сделку/тик), это
    агрегированный снимок борда (LAST/OPEN/HIGH/LOW/объём за день) — у
    акций MOEX нет push-ленты сделок, только периодический снимок борда
    плюс отдельно читаемая полная лента (`StockTrade`). Смешивать их в
    одной таблице нельзя: разная семантика полей и разная частота записи
    (снимок — раз в интервал поллинга, лента — построчно на каждую
    сделку по избранным бумагам).
    """

    asset = ForeignKey(
        StockAsset,
        on_delete=CASCADE,
        related_name="price_snapshots",
        verbose_name=_("актив"),
    )
    last = DecimalField(
        _("последняя цена"),
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )
    open = DecimalField(
        _("цена открытия"),
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )
    high = DecimalField(
        _("максимум"),
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )
    low = DecimalField(
        _("минимум"),
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )
    change = DecimalField(
        _("изменение"),
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
    )
    change_percent = DecimalField(
        _("изменение, %"),
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
    )
    volume = PositiveBigIntegerField(_("объём (лоты)"), null=True, blank=True)
    value = DecimalField(
        _("оборот"),
        max_digits=20,
        decimal_places=2,
        null=True,
        blank=True,
    )
    num_trades = PositiveIntegerField(_("число сделок"), null=True, blank=True)
    timestamp = DateTimeField(
        _("метка времени"),
        db_index=True,
        help_text=_(
            "Время данных ISS (`UPDATETIME`), а не время формирования "
            "ответа сервером (`SYSTIME`) — разница может достигать ~15 "
            "минут, это штатная задержка данных ISS, а не баг.",
        ),
    )
    created_at = DateTimeField(_("создано"), auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        constraints = [
            UniqueConstraint(
                fields=["asset", "timestamp"],
                name="unique_stock_snapshot_asset_ts",
            ),
        ]
        indexes = [
            Index(fields=["asset", "-timestamp"], name="stock_snap_asset_ts_idx"),
        ]
        verbose_name = _("снапшот цены акции")
        verbose_name_plural = _("снапшоты цен акций")

    def __str__(self) -> str:
        return f"{self.asset.symbol} @ {self.timestamp}: {self.last}"


class StockTrade(Model):
    """Одна сделка из ленты MOEX ISS по бумаге с `track_trades=True`."""

    asset = ForeignKey(
        StockAsset,
        on_delete=CASCADE,
        related_name="trades",
        verbose_name=_("актив"),
    )
    trade_id = BigIntegerField(_("TRADENO"))
    price = DecimalField(_("цена"), max_digits=14, decimal_places=4)
    quantity = PositiveBigIntegerField(_("количество (лоты)"))
    side = CharField(_("сторона"), max_length=4, choices=StockTradeSide)
    period = CharField(
        _("период торгов (PERIOD)"),
        max_length=1,
        blank=True,
        help_text=_(
            "Сырое значение поля PERIOD ISS (в наблюдавшихся данных — "
            "'S'/'N', полный список кодов ISS не документирует). Решение "
            "о фильтрации аукционных сделок сознательно отложено на этап "
            "работы с API — здесь значение сохраняется как есть, без "
            "интерпретации.",
        ),
    )
    timestamp = DateTimeField(_("метка времени"), db_index=True)
    created_at = DateTimeField(_("создано"), auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        constraints = [
            UniqueConstraint(
                fields=["asset", "trade_id"],
                name="unique_stock_trade_asset_tradeno",
            ),
        ]
        indexes = [
            Index(fields=["asset", "-timestamp"], name="stock_trade_asset_ts_idx"),
        ]
        verbose_name = _("сделка по акции")
        verbose_name_plural = _("сделки по акциям")

    def __str__(self) -> str:
        return f"{self.asset.symbol} #{self.trade_id} @ {self.timestamp}: {self.price}"
