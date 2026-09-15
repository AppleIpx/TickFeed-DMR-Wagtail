from dmr.routing import Router, path

from tickfeeddmr.market_data.api.controllers.crypto import (
    CryptoAssetCurrentController,
    CryptoAssetListController,
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
    ],
)
