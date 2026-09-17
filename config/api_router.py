from dmr.openapi import build_schema
from dmr.routing import Router

from tickfeeddmr.market_data.api.routes.crypto import router as crypto_router
from tickfeeddmr.market_data.api.routes.fiat import router as fiat_router
from tickfeeddmr.market_data.api.routes.stock import router as stock_router

router = Router("api/")
router.include(crypto_router, namespace="crypto")
router.include(stock_router, namespace="stock")
router.include(fiat_router, namespace="fiat")

schema = build_schema(router)
