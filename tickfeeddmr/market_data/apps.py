from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class MarketDataConfig(AppConfig):
    name = "tickfeeddmr.market_data"
    verbose_name = _("Market Data")

    def ready(self) -> None:
        from tickfeeddmr.market_data import signals  # noqa: F401, PLC0415
