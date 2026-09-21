from dmr.routing import Router, path

from tickfeeddmr.market_data.api.controllers.crypto import (
    CryptoAssetCurrentController,
    CryptoAssetListController,
    CryptoHistoryController,
    CryptoIntradayController,
    CryptoStreamController,
    CryptoTradesController,
)

router = Router(
    "crypto/",
    [
        path(
            "assets/",
            CryptoAssetListController.as_view(),
            name="crypto-assets-list",
        ),
        path(
            "assets/<str:symbol>/current",
            CryptoAssetCurrentController.as_view(),
            name="crypto-asset-current",
        ),
        path(
            "assets/<str:symbol>/trades",
            CryptoTradesController.as_view(),
            name="crypto-asset-trades",
        ),
        path(
            "assets/<str:symbol>/intraday",
            CryptoIntradayController.as_view(),
            name="crypto-asset-intraday",
        ),
        path(
            "assets/<str:symbol>/history",
            CryptoHistoryController.as_view(),
            name="crypto-asset-history",
        ),
        path(
            "stream",
            CryptoStreamController.as_view(),
            name="crypto-stream",
        ),
    ],
)
