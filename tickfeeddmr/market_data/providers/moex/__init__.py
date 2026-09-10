"""Провайдер данных MOEX ISS: снимок борда + курсорная лента сделок акций."""

from tickfeeddmr.market_data.providers.moex.provider import EXCHANGE, MoexProvider

__all__ = [
    "EXCHANGE",
    "MoexProvider",
]
