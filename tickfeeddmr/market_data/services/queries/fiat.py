from typing import TYPE_CHECKING

from tickfeeddmr.market_data.models import FiatCurrency, FiatPriceSnapshot
from tickfeeddmr.market_data.services.queries.errors import AssetNotFoundError
from tickfeeddmr.market_data.services.queries.period import (
    resolve_earliest_available,
    resolve_period,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date


async def list_current_rates() -> list[tuple[FiatCurrency, FiatPriceSnapshot]]:
    """Последний курс по каждой активной валюте, одним запросом."""
    snapshots = [
        snapshot
        async for snapshot in FiatPriceSnapshot.objects.filter(
            asset__is_active=True,
        )
        .select_related("asset")
        .order_by("asset_id", "-effective_date")
        .distinct("asset_id")
    ]
    return [(snapshot.asset, snapshot) for snapshot in snapshots]


async def get_history(
    iso_code: str,
    *,
    date_from: date | None,
    date_to: date | None,
) -> Sequence[FiatPriceSnapshot]:
    """Дневные курсы за период.

    По умолчанию (без `date_from`/`date_to`) — либо последние
    `MARKET_DATA_HISTORY_DEFAULT_PERIOD_DAYS`, либо, если настройка не
    задана, вся история валюты с самого раннего сохранённого курса (см.
    `resolve_period`).

    Свежести в ответе нет (в отличие от `list_current_rates`) — вчерашний
    курс не "задерживается".
    """
    asset = await FiatCurrency.objects.filter(
        iso_code=iso_code,
        is_active=True,
    ).afirst()
    if asset is None:
        msg = f"Валюта {iso_code!r} не найдена"
        raise AssetNotFoundError(msg)

    earliest_available = await resolve_earliest_available(
        date_from=date_from,
        queryset=FiatPriceSnapshot.objects.filter(asset=asset),
        field_name="effective_date",
    )
    frm, to = resolve_period(
        date_from=date_from,
        date_to=date_to,
        earliest_available=earliest_available,
    )
    return [
        snapshot
        async for snapshot in FiatPriceSnapshot.objects.filter(
            asset=asset,
            effective_date__gte=frm,
            effective_date__lte=to,
        ).order_by("effective_date")
    ]
