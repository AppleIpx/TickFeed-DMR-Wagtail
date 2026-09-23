from django.core.validators import RegexValidator
from django.db.models import (
    CASCADE,
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    DecimalField,
    ForeignKey,
    Index,
    Model,
    UniqueConstraint,
)
from django.utils.translation import gettext_lazy as _

from tickfeeddmr.market_data.models.base import AssetBase

CBR_ID_VALIDATOR = RegexValidator(
    regex=r"^R\d{5}\Z",
    message=_("Код ЦБ РФ: латинская R и пять цифр, например R01235."),
)


class FiatCurrency(AssetBase):
    """Фиатная валюта, отслеживаемая через ЦБ РФ.

    Поля `source` у этой модели и у `FiatPriceSnapshot` сознательно нет:
    источник валютных цен ровно один и другого не
    планируется — колонка с единственным возможным значением несёт не
    информацию, а константу.
    """

    iso_code = CharField(_("ISO-код"), max_length=3, unique=True)
    cbr_id = CharField(
        _("код ЦБ РФ"),
        max_length=20,
        unique=True,
        validators=[CBR_ID_VALIDATOR],
        help_text=_(
            "Внутренний код ЦБ РФ (атрибут ID в ответе XML_daily.asp, "
            "например R01235) — по нему опрос курсов резолвит строки",
        ),
    )
    history_backfilled = BooleanField(
        _("полная история загружена"),
        default=False,
        help_text=_(
            "Показывает, загружена ли по этой валюте вся история курсов "
            "с момента её появления, а не только текущие значения за "
            "последние дни. Пока не отмечено — при ближайшем обновлении "
            "системой валюта автоматически докачает всю историю целиком, "
            "и после этого отметка проставится сама. Поле только для "
            "чтения — заполняется автоматически, вручную менять не нужно.",
        ),
    )

    class Meta:
        verbose_name = _("фиатная валюта")
        verbose_name_plural = _("фиатные валюты")

    def __str__(self) -> str:
        return f"{self.symbol} ({self.iso_code})"


class FiatPriceSnapshot(Model):
    """Точка цены `FiatCurrency` в конкретный момент времени."""

    asset = ForeignKey(
        FiatCurrency,
        on_delete=CASCADE,
        related_name="price_snapshots",
        verbose_name=_("актив"),
    )
    price = DecimalField(_("цена"), max_digits=14, decimal_places=6)
    effective_date = DateField(
        _("дата курса"),
        db_index=True,
        help_text=_(
            "Официальная дата, на которую котируется курс (атрибут Date "
            "ValCurs у ЦБ РФ) — не дата фактического опроса: ЦБ публикует "
            "курс на завтрашний рабочий день заранее, вечером текущего.",
        ),
    )
    timestamp = DateTimeField(_("метка времени"), db_index=True)
    created_at = DateTimeField(_("создано"), auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        constraints = [
            UniqueConstraint(
                fields=["asset", "effective_date"],
                name="unique_fiat_snapshot_asset_effective_date",
            ),
        ]
        indexes = [
            Index(fields=["asset", "-timestamp"], name="fiat_snap_asset_ts_idx"),
        ]
        verbose_name = _("снапшот цены валюты")
        verbose_name_plural = _("снапшоты цен валют")

    def __str__(self) -> str:
        return f"{self.asset.symbol} @ {self.timestamp}: {self.price}"
