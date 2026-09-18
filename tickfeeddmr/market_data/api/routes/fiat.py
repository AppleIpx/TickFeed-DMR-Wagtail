from dmr.routing import Router, path

from tickfeeddmr.market_data.api.controllers.fiat import (
    FiatHistoryController,
    FiatRateListController,
)

router = Router(
    "fiat/",
    [
        path(
            "rates/",
            FiatRateListController.as_view(),
            name="fiat-rates-list",
        ),
        path(
            "rates/<str:iso_code>/history",
            FiatHistoryController.as_view(),
            name="fiat-rate-history",
        ),
    ],
)
