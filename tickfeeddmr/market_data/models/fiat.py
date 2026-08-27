from django.db.models import (
    CASCADE,
    CharField,
    DateTimeField,
    DecimalField,
    ForeignKey,
    Index,
    Model,
    TextChoices,
)
from django.utils.translation import gettext_lazy as _

from tickfeeddmr.market_data.models.base import AssetBase


class FiatSource(TextChoices):
    """Источник валютных цен/справочных данных.

    Используется и в `FiatCurrency.source` (основной источник валюты), и в
    `FiatPriceSnapshot.source` (источник конкретной точки цены — у одной
    валюты со временем могут накапливаться снапшоты из обоих источников).
    """

    MOEX = "MOEX", _("Московская биржа")
    CBR = "CBR", _("Центральный банк РФ")


class FiatCurrency(AssetBase):
    """Фиатная валюта, отслеживаемая через MOEX и/или ЦБ РФ."""

    iso_code = CharField(_("ISO-код"), max_length=3, unique=True)
    moex_secid = CharField(
        _("SECID на MOEX"),
        max_length=20,
        blank=True,
        help_text=_("Код инструмента на MOEX, если валюта там доступна."),
    )
    source = CharField(_("источник"), max_length=10, choices=FiatSource)

    class Meta:
        verbose_name = _("фиатная валюта")
        verbose_name_plural = _("фиатные валюты")

    def __str__(self) -> str:
        return f"{self.symbol} ({self.iso_code})"


class FiatPriceSnapshot(Model):
    """Точка цены `FiatCurrency` в конкретный момент времени.

    `source` указывается для каждого снапшота отдельно, а не для валюты
    целиком, потому что у одной валюты со временем могут накапливаться
    точки и от MOEX, и от ЦБ.
    """

    asset = ForeignKey(
        FiatCurrency,
        on_delete=CASCADE,
        related_name="price_snapshots",
        verbose_name=_("актив"),
    )
    price = DecimalField(_("цена"), max_digits=14, decimal_places=6)
    source = CharField(_("источник"), max_length=10, choices=FiatSource)
    timestamp = DateTimeField(_("метка времени"), db_index=True)
    created_at = DateTimeField(_("создано"), auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            Index(fields=["asset", "-timestamp"], name="fiat_snap_asset_ts_idx"),
        ]
        verbose_name = _("снапшот цены валюты")
        verbose_name_plural = _("снапшоты цен валют")

    def __str__(self) -> str:
        return f"{self.asset.symbol} @ {self.timestamp}: {self.price}"
