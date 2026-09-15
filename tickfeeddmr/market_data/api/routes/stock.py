from dmr.routing import Router, path

from tickfeeddmr.market_data.api.controllers.stock import (
    StockAssetCurrentController,
    StockAssetListController,
    StockTradesController,
)

router = Router(
    "stocks/",
    [
        path(
            "",
            StockAssetListController.as_view(),
            name="stock-assets-list",
        ),
        path(
            "<str:secid>/current",
            StockAssetCurrentController.as_view(),
            name="stock-asset-current",
        ),
        path(
            "<str:secid>/trades",
            StockTradesController.as_view(),
            name="stock-asset-trades",
        ),
    ],
)
