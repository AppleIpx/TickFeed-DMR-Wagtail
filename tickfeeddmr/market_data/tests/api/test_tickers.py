from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tickfeeddmr.market_data.services.queries.errors import TooManyTickersError
from tickfeeddmr.market_data.services.queries.tickers import parse_tickers

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings


@pytest.mark.parametrize("raw", [None, "", ",", " , ,  ", "   "])
def test_parse_tickers_returns_none_when_no_filter_present(raw: str | None) -> None:
    assert parse_tickers(raw) is None


def test_parse_tickers_splits_on_comma_and_strips_whitespace() -> None:
    assert parse_tickers("BTC, ETH ,SOL") == ["BTC", "ETH", "SOL"]


def test_parse_tickers_dedupes_keeping_first_occurrence_order() -> None:
    assert parse_tickers("BTC,ETH,BTC,SOL,ETH") == ["BTC", "ETH", "SOL"]


def test_parse_tickers_raises_too_many_tickers_over_the_limit(
    settings: Settings,
) -> None:
    settings.MARKET_DATA_SSE_MAX_TICKERS = 3

    with pytest.raises(TooManyTickersError):
        parse_tickers("A,B,C,D")


def test_parse_tickers_at_the_limit_is_allowed(settings: Settings) -> None:
    settings.MARKET_DATA_SSE_MAX_TICKERS = 3

    assert parse_tickers("A,B,C") == ["A", "B", "C"]
