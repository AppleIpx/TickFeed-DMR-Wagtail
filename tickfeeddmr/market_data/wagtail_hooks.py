from wagtail.admin.panels import FieldPanel
from wagtail_modeladmin.options import ModelAdmin, ModelAdminGroup, modeladmin_register

from tickfeeddmr.market_data.models import (
    CryptoAsset,
    CryptoDailyCandle,
    CryptoPriceSnapshot,
    FiatCurrency,
    FiatPriceSnapshot,
    StockAsset,
    StockDailyCandle,
    StockPriceSnapshot,
    StockTrade,
)


@modeladmin_register
class CryptoAssetAdmin(ModelAdmin):
    model = CryptoAsset
    menu_icon = "tag"
    list_display = ["symbol", "display_name", "exchange", "trading_pair", "is_active"]
    list_filter = ["exchange", "is_active"]
    search_fields = ["symbol", "display_name", "trading_pair"]


@modeladmin_register
class FiatCurrencyAdmin(ModelAdmin):
    model = FiatCurrency
    menu_icon = "globe"
    list_display = [
        "symbol",
        "display_name",
        "iso_code",
        "cbr_id",
        "is_active",
        "history_backfilled",
    ]
    list_filter = ["is_active", "history_backfilled"]
    search_fields = ["symbol", "display_name", "iso_code"]
    panels = [
        FieldPanel("symbol"),
        FieldPanel("display_name"),
        FieldPanel("iso_code"),
        FieldPanel("cbr_id"),
        FieldPanel("is_active"),
        FieldPanel("history_backfilled", read_only=True),
    ]


class CryptoPriceSnapshotAdmin(ModelAdmin):
    model = CryptoPriceSnapshot
    menu_icon = "time"
    date_hierarchy = "timestamp"
    list_display = ["asset", "price", "volume", "timestamp"]
    list_filter = ["asset"]


class FiatPriceSnapshotAdmin(ModelAdmin):
    model = FiatPriceSnapshot
    menu_icon = "decimal"
    date_hierarchy = "timestamp"
    list_display = ["asset", "price", "effective_date", "timestamp"]
    list_filter = ["asset"]


@modeladmin_register
class StockAssetAdmin(ModelAdmin):
    model = StockAsset
    menu_icon = "tag"
    list_display = [
        "symbol",
        "display_name",
        "board",
        "is_active",
        "track_trades",
    ]
    list_filter = ["board", "is_active", "track_trades"]
    search_fields = ["symbol", "display_name"]


class StockPriceSnapshotAdmin(ModelAdmin):
    model = StockPriceSnapshot
    menu_icon = "time"
    date_hierarchy = "timestamp"
    list_display = ["asset", "last", "change_percent", "volume", "timestamp"]
    list_filter = ["asset"]


@modeladmin_register
class StockTradeAdmin(ModelAdmin):
    model = StockTrade
    menu_icon = "list-ul"
    date_hierarchy = "timestamp"
    list_display = ["asset", "trade_id", "price", "quantity", "side", "timestamp"]
    list_filter = ["asset", "side"]


class CryptoDailyCandleAdmin(ModelAdmin):
    model = CryptoDailyCandle
    menu_icon = "date"
    date_hierarchy = "date"
    list_display = ["asset", "date", "open", "high", "low", "close", "volume"]
    list_filter = ["asset"]


class StockDailyCandleAdmin(ModelAdmin):
    model = StockDailyCandle
    menu_icon = "date"
    date_hierarchy = "date"
    list_display = ["asset", "date", "open", "high", "low", "close", "volume"]
    list_filter = ["asset"]


@modeladmin_register
class SnapshotsGroup(ModelAdminGroup):
    """Снапшоты цен и дневные свечи (крипта/валюта/акции) одним пунктом меню.

    `StockTrade` сюда сознательно не входит — это не снапшот (сводка на
    момент времени), а отдельная сделка купли-продажи, у неё свой пункт
    меню.
    """

    menu_label = "Снапшоты"
    menu_icon = "time"
    items = (
        CryptoPriceSnapshotAdmin,
        FiatPriceSnapshotAdmin,
        StockPriceSnapshotAdmin,
        CryptoDailyCandleAdmin,
        StockDailyCandleAdmin,
    )
