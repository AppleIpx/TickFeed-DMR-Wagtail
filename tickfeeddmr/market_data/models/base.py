from django.db.models import BooleanField, CharField, DateTimeField, Model
from django.utils.translation import gettext_lazy as _


class AssetBase(Model):
    """Общие поля для любого торгуемого актива (крипто или фиат).

    Абстрактная модель — у каждого конкретного наследника своя таблица,
    поэтому `symbol` уникален в пределах таблицы конкретного наследника
    (например, отдельно среди `CryptoAsset`, отдельно среди `FiatCurrency`),
    а не глобально между ними.
    """

    symbol = CharField(_("символ"), max_length=20, unique=True)
    display_name = CharField(_("отображаемое имя"), max_length=255)
    is_active = BooleanField(
        _("активен"),
        default=True,
        help_text=_(
            "Ведётся ли сейчас фоновый сбор данных по этому активу. Не "
            "является признаком того, что актив всё ещё существует или "
            "торгуется у источника.",
        ),
    )
    created_at = DateTimeField(_("создано"), auto_now_add=True)
    updated_at = DateTimeField(_("обновлено"), auto_now=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.symbol
