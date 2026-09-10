from wagtail_modeladmin.options import ModelAdmin, ModelAdminGroup, modeladmin_register

from tickfeeddmr.market_data.models import (
    CryptoAsset,
    CryptoPriceSnapshot,
    FiatCurrency,
    FiatPriceSnapshot,
    StockAsset,
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
    list_display = ["symbol", "display_name", "iso_code", "source", "is_active"]
    list_filter = ["source", "is_active"]
    search_fields = ["symbol", "display_name", "iso_code"]


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
    list_display = ["asset", "price", "source", "timestamp"]
    list_filter = ["asset", "source"]


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


@modeladmin_register
class SnapshotsGroup(ModelAdminGroup):
    """Снапшоты цен (крипта/валюта/акции) одним пунктом меню в админке.

    `StockTrade` сюда сознательно не входит — это не снапшот (сводка на
    момент времени), а отдельная сделка купли-продажи, у неё свой пункт
    меню.
    """

    menu_label = "Снапшоты"
    menu_icon = "time"
    items = (CryptoPriceSnapshotAdmin, FiatPriceSnapshotAdmin, StockPriceSnapshotAdmin)
