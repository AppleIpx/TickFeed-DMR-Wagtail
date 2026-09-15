from dmr import modify

from config.api_base import BaseController
from tickfeeddmr.market_data.api.presenters import fiat as fiat_presenters
from tickfeeddmr.market_data.api.schemas.fiat import FiatRateOut  # noqa: TC001
from tickfeeddmr.market_data.services.queries import fiat as fiat_queries


class FiatRateListController(BaseController):
    """`GET /api/fiat/rates/` — текущие курсы всех активных валют."""

    @modify(tags=["Валюты"])
    async def get(self) -> list[FiatRateOut]:
        pairs = await fiat_queries.list_current_rates()
        return [fiat_presenters.rate_out(asset, snapshot) for asset, snapshot in pairs]
