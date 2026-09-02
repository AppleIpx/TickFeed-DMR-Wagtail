"""Провайдер данных Binance: REST-бэкфилл + один WS-стрим сделок."""

from tickfeeddmr.market_data.providers.binance.provider import EXCHANGE, BinanceProvider

__all__ = [
    "EXCHANGE",
    "BinanceProvider",
]
