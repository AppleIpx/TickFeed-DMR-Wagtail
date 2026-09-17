from dmr import Path, Query, modify

from config.api_base import BaseController
from tickfeeddmr.market_data.api.presenters import fiat as fiat_presenters
from tickfeeddmr.market_data.api.schemas.common import HistoryQuery  # noqa: TC001
from tickfeeddmr.market_data.api.schemas.fiat import (  # noqa: TC001
    FiatRateOut,
    FiatRatePointOut,
    IsoCodePath,
)
from tickfeeddmr.market_data.services.queries import fiat as fiat_queries

_TAGS = ["Валюты"]


class FiatRateListController(BaseController):
    """`GET /api/fiat/rates/` — текущие курсы всех активных валют."""

    @modify(tags=_TAGS)
    async def get(self) -> list[FiatRateOut]:
        pairs = await fiat_queries.list_current_rates()
        return [fiat_presenters.rate_out(asset, snapshot) for asset, snapshot in pairs]


class FiatHistoryController(BaseController):
    """`GET /api/fiat/rates/{iso_code}/history` — дневные курсы за период."""

    @modify(tags=_TAGS)
    async def get(
        self,
        parsed_path: Path[IsoCodePath],
        parsed_query: Query[HistoryQuery],
    ) -> list[FiatRatePointOut]:
        snapshots = await fiat_queries.get_history(
            parsed_path.iso_code,
            date_from=parsed_query.date_from,
            date_to=parsed_query.date_to,
        )
        return fiat_presenters.history_out(snapshots)
