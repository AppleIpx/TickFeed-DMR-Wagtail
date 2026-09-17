from typing import TYPE_CHECKING

from tickfeeddmr.market_data.api.presenters.common import asset_out, freshness
from tickfeeddmr.market_data.api.schemas.fiat import (
    CBR_DATA_DELAY_SECONDS,
    CBR_SOURCE_LABEL,
    FiatRateOut,
)

if TYPE_CHECKING:
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
