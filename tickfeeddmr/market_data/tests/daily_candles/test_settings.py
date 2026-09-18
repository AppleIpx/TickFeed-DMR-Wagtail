from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured

from tickfeeddmr.market_data.services.daily_candles.settings import (
    validate_poll_budget,
)


@pytest.mark.parametrize("budget", [0, -1])
def test_validate_poll_budget_raises_on_non_positive_budget(budget: int) -> None:
    with pytest.raises(ImproperlyConfigured, match="CRYPTO_DAILY_CANDLES_POLL_BUDGET"):
        validate_poll_budget("CRYPTO", budget, 30)


@pytest.mark.parametrize(("budget", "ttl"), [(30, 34), (30, 30), (30, 20)])
def test_validate_poll_budget_raises_when_margin_too_small(
    budget: int,
    ttl: int,
) -> None:
    with pytest.raises(ImproperlyConfigured, match="STOCK_DAILY_CANDLES_POLL_LOCK_TTL"):
        validate_poll_budget("STOCK", budget, ttl)


def test_validate_poll_budget_accepts_sufficient_margin() -> None:
    validate_poll_budget("FIAT", 30, 35)
