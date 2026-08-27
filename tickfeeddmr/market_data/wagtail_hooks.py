from wagtail_modeladmin.options import ModelAdmin, modeladmin_register

from tickfeeddmr.market_data.models import (
    CryptoAsset,
    CryptoPriceSnapshot,
    FiatCurrency,
    FiatPriceSnapshot,
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


@modeladmin_register
class CryptoPriceSnapshotAdmin(ModelAdmin):
    model = CryptoPriceSnapshot
    menu_icon = "time"
    date_hierarchy = "timestamp"
    list_display = ["asset", "price", "volume", "timestamp"]
    list_filter = ["asset"]


@modeladmin_register
class FiatPriceSnapshotAdmin(ModelAdmin):
    model = FiatPriceSnapshot
    menu_icon = "decimal"
    date_hierarchy = "timestamp"
    list_display = ["asset", "price", "source", "timestamp"]
    list_filter = ["asset", "source"]
