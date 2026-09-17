from dmr.routing import Router, path

from tickfeeddmr.market_data.api.controllers.fiat import FiatRateListController

router = Router(
    "fiat/",
    [
        path(
            "rates/",
            FiatRateListController.as_view(),
            name="fiat-rates-list",
        ),
    ],
)
