from typing import TYPE_CHECKING

from django import forms

if TYPE_CHECKING:
    from django.db.models import Model


class AssetRunForm(forms.Form):
    """Выбор активного актива для задачи догона одного актива."""

    asset = forms.ModelChoiceField(queryset=None, label="Актив")

    def __init__(self, *args, asset_model: type[Model], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        field = self.fields["asset"]
        field.queryset = asset_model.objects.filter(is_active=True).order_by("symbol")
        field.label_from_instance = lambda asset: (
            f"{asset.symbol} — {asset.display_name}"
        )
