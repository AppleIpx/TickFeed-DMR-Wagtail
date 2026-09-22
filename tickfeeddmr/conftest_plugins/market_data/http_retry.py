from __future__ import annotations

import pytest

from tickfeeddmr.market_data.providers import cbr, moex
from tickfeeddmr.market_data.providers.binance import websocket as binance_ws_module


@pytest.fixture
def fast_cbr_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Для `tests/cbr/test_client.py`.

    Реальный backoff тут не нужен, повторы должны отрабатывать в тестах как
    можно быстрее.
    """
    monkeypatch.setattr(cbr.client, "INITIAL_BACKOFF_SECONDS", 0.0)
    monkeypatch.setattr(cbr.client, "MAX_BACKOFF_SECONDS", 0.0)


@pytest.fixture
def fast_moex_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Для `tests/moex/test_client.py`.

    Реальный backoff (1s -> 8s, до MAX_ATTEMPTS попыток) не нужен в тестах —
    повторы должны отрабатывать как можно быстрее, само значение backoff
    здесь не проверяется.
    """
    monkeypatch.setattr(moex.client, "INITIAL_BACKOFF_SECONDS", 0.0)
    monkeypatch.setattr(moex.client, "MAX_BACKOFF_SECONDS", 0.0)


@pytest.fixture
def fast_binance_ws_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Для `tests/binance/test_websocket.py`.

    Реальный backoff (1s -> 30s) не нужен в тестах — реконнект должен
    произойти как можно быстрее, само значение backoff здесь не
    проверяется.
    """
    monkeypatch.setattr(binance_ws_module, "INITIAL_BACKOFF_SECONDS", 0.01)
    monkeypatch.setattr(binance_ws_module, "MAX_BACKOFF_SECONDS", 0.02)
