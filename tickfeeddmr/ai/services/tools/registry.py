import functools
from typing import TYPE_CHECKING, Any

import msgspec

from tickfeeddmr.ai.services.llm.schemas import ToolSpec
from tickfeeddmr.ai.services.tools.handlers import (
    handle_big_moves,
    handle_get_current,
    handle_indicators,
    handle_list_assets,
    handle_period_stats,
)
from tickfeeddmr.ai.services.tools.schemas import (
    BigMovesArgs,
    GetCurrentArgs,
    IndicatorsArgs,
    ListAssetsArgs,
    PeriodStatsArgs,
    ToolDefinition,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

SYMBOL_LABEL_MAX = 20
_GRANULARITY_LABELS = {
    "year": "годам",
    "half_year": "полугодиям",
    "quarter": "кварталам",
    "month": "месяцам",
}


def _symbol(args: Any) -> str:
    return str(args.symbol)[:SYMBOL_LABEL_MAX]


def _period_stats_label(args: Any) -> str:
    unit = _GRANULARITY_LABELS[args.granularity]
    return f"Смотрю статистику {_symbol(args)} по {unit}"


TOOLS: Mapping[str, ToolDefinition] = {
    t.name: t
    for t in (
        ToolDefinition(
            name="list_assets",
            description=(
                "Список активных активов: рынок, тикер и название. Вызывай, если "
                "не уверен в рынке или тикере."
            ),
            args_type=ListAssetsArgs,
            label=lambda _: "Смотрю список доступных активов",
            handler=handle_list_assets,
        ),
        ToolDefinition(
            name="get_current",
            description=(
                "Последняя цена актива, момент, к которому она относится, и "
                "изменение за день в процентах."
            ),
            args_type=GetCurrentArgs,
            label=lambda a: f"Смотрю текущую цену {_symbol(a)}",
            handler=handle_get_current,
        ),
        ToolDefinition(
            name="get_period_stats",
            description=(
                "Статистика актива по календарным периодам: доходность, максимальная "
                "просадка, волатильность, изменение объёма. Начни с half_year или "
                "year, затем возьми month по интересному периоду. Даты — в формате "
                "YYYY-MM-DD."
            ),
            args_type=PeriodStatsArgs,
            label=_period_stats_label,
            handler=handle_period_stats,
        ),
        ToolDefinition(
            name="get_indicators",
            description=(
                "Технические индикаторы по последней дневной свече: SMA50, SMA200, "
                "RSI14, максимум и минимум за год и положение цены в этом диапазоне."
            ),
            args_type=IndicatorsArgs,
            label=lambda a: f"Считаю индикаторы {_symbol(a)}",
            handler=handle_indicators,
        ),
        ToolDefinition(
            name="find_big_moves",
            description=(
                "Дни с аномальным движением цены (от 3σ) или объёма (от 3× медианы) "
                "в окне, по умолчанию за год. Даты — в формате YYYY-MM-DD."
            ),
            args_type=BigMovesArgs,
            label=lambda a: f"Ищу резкие движения {_symbol(a)}",
            handler=handle_big_moves,
        ),
    )
}


def parameters_schema(t: type[msgspec.Struct]) -> dict[str, Any]:
    """JSON Schema аргументов без `$ref`/`$defs` и `title` — для модели."""
    raw = msgspec.json.schema(t)
    body = raw["$defs"][raw["$ref"].rsplit("/", 1)[-1]] if "$ref" in raw else raw
    body = {k: v for k, v in body.items() if k != "title"}
    body.setdefault("type", "object")
    body.setdefault("properties", {})
    return body


@functools.cache
def tool_specs() -> tuple[ToolSpec, ...]:
    """Описания всех инструментов в виде, который понимают провайдеры."""
    return tuple(
        ToolSpec(t.name, t.description, parameters_schema(t.args_type))
        for t in TOOLS.values()
    )
