pytest_plugins = [
    "tickfeeddmr.conftest_plugins.common.media",
    "tickfeeddmr.conftest_plugins.market_data.models",
    "tickfeeddmr.conftest_plugins.market_data.redis",
    "tickfeeddmr.conftest_plugins.market_data.sse",
    "tickfeeddmr.conftest_plugins.market_data.http_retry",
]
