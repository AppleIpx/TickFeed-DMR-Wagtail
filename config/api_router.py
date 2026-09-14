from dmr.openapi import build_schema
from dmr.routing import Router

router = Router("api/")

schema = build_schema(router)
