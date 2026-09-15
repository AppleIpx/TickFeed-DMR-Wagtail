from tickfeeddmr.market_data.models import FiatCurrency, FiatPriceSnapshot


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
