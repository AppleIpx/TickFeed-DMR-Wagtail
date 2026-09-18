from typing import TYPE_CHECKING

from tickfeeddmr.market_data.api.presenters.common import asset_out, freshness
from tickfeeddmr.market_data.api.schemas.fiat import (
    CBR_DATA_DELAY_SECONDS,
    CBR_SOURCE_LABEL,
    FiatRateOut,
    FiatRatePointOut,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.market_data.models import FiatCurrency, FiatPriceSnapshot


def rate_out(asset: FiatCurrency, snapshot: FiatPriceSnapshot) -> FiatRateOut:
    return FiatRateOut(
        asset=asset_out(asset),
        iso_code=asset.iso_code,
        rate=str(snapshot.price),
        effective_date=snapshot.effective_date,
        source=CBR_SOURCE_LABEL,
        freshness=freshness(
            timestamp=snapshot.timestamp,
            data_delay_seconds=CBR_DATA_DELAY_SECONDS,
        ),
    )


def history_point_out(snapshot: FiatPriceSnapshot) -> FiatRatePointOut:
    return FiatRatePointOut(
        timestamp=snapshot.timestamp,
        effective_date=snapshot.effective_date,
        rate=str(snapshot.price),
    )


def history_out(snapshots: Sequence[FiatPriceSnapshot]) -> list[FiatRatePointOut]:
    return [history_point_out(snapshot) for snapshot in snapshots]
