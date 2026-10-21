from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Annotated, Any, Literal

import msgspec

from tickfeeddmr.ai.services.llm.schemas import ToolCallRequest

Market = Literal["crypto", "stock"]
Granularity = Literal["year", "half_year", "quarter", "month"]
MoveReason = Literal["price", "volume"]

_MarketArg = Annotated[
    Market,
    msgspec.Meta(description="Рынок: crypto — криптовалюты, stock — акции MOEX"),
]
_SymbolArg = Annotated[
    str,
    msgspec.Meta(description="Тикер актива, например BTC или SBER"),
]
_GranularityArg = Annotated[
    Granularity,
    msgspec.Meta(description="Период: year, half_year, quarter или month"),
]
_DateFromArg = Annotated[
    date | None,
    msgspec.Meta(
        description="Начало диапазона, YYYY-MM-DD; по умолчанию начало данных",
    ),
]
_DateToArg = Annotated[
    date | None,
    msgspec.Meta(description="Конец диапазона, YYYY-MM-DD; по умолчанию сегодня"),
]


class ListAssetsArgs(msgspec.Struct, frozen=True):
    """Аргументы `list_assets`: нет."""


class GetCurrentArgs(msgspec.Struct, frozen=True):
    """Аргументы `get_current`."""

    market: _MarketArg
    symbol: _SymbolArg


class PeriodStatsArgs(
    msgspec.Struct,
    frozen=True,
    rename={"date_from": "from", "date_to": "to"},
):
    """Аргументы `get_period_stats`."""

    market: _MarketArg
    symbol: _SymbolArg
    granularity: _GranularityArg
    date_from: _DateFromArg = None
    date_to: _DateToArg = None


class IndicatorsArgs(msgspec.Struct, frozen=True):
    """Аргументы `get_indicators`."""

    market: _MarketArg
    symbol: _SymbolArg


class BigMovesArgs(
    msgspec.Struct,
    frozen=True,
    rename={"date_from": "from", "date_to": "to"},
):
    """Аргументы `find_big_moves`."""

    market: _MarketArg
    symbol: _SymbolArg
    date_from: _DateFromArg = None
    date_to: _DateToArg = None


class AssetItem(msgspec.Struct, frozen=True):
    market: Market
    symbol: str
    name: str


class ListAssetsResult(msgspec.Struct, frozen=True):
    assets: list[AssetItem]
    truncated: bool = False


class CurrentResult(msgspec.Struct, frozen=True):
    market: Market
    symbol: str
    name: str
    price: float
    currency: str | None
    pair: str | None
    as_of: datetime
    change_day_pct: float | None
    note: str | None


class PeriodRow(msgspec.Struct, frozen=True):
    label: str
    first_date: date
    last_date: date
    trading_days: int
    close: float
    return_pct: float
    max_drawdown_pct: float
    volatility_pct: float | None
    volume_change_pct: float | None
    partial: bool


class PeriodStatsResult(msgspec.Struct, frozen=True):
    market: Market
    symbol: str
    granularity: Granularity
    rows: list[PeriodRow]
    truncated: bool
    hint: str | None


class IndicatorsResult(msgspec.Struct, frozen=True):
    market: Market
    symbol: str
    as_of: date
    close: float
    sma50: float | None
    sma200: float | None
    close_vs_sma50_pct: float | None
    close_vs_sma200_pct: float | None
    rsi14: float | None
    high_52w: float | None
    low_52w: float | None
    position_52w_pct: float | None


class BigMoveRow(msgspec.Struct, frozen=True):
    date: date
    change_pct: float | None
    z_score: float | None
    gap_pct: float | None
    volume_ratio: float | None
    reasons: list[MoveReason]


class BigMovesResult(msgspec.Struct, frozen=True):
    market: Market
    symbol: str
    date_from: date
    date_to: date
    sigma_pct: float | None
    rows: list[BigMoveRow]
    truncated: bool
    hint: str | None


class ToolErrorResult(msgspec.Struct, frozen=True):
    error: str
    hint: str | None = None


class ResolvedAsset(msgspec.Struct, frozen=True):
    market: Market
    symbol: str
    name: str
    asset_id: int
    trading_pair: str | None


class ToolContext(msgspec.Struct, frozen=True):
    today: date
    max_rows: int


class ToolDefinition(msgspec.Struct, frozen=True):
    name: str
    description: str
    args_type: type[msgspec.Struct]
    label: Callable[[Any], str]
    handler: Callable[[Any, ToolContext], Awaitable[msgspec.Struct]]


class PreparedCall(msgspec.Struct, frozen=True):
    call: ToolCallRequest
    definition: ToolDefinition
    args: Any
    label: str
