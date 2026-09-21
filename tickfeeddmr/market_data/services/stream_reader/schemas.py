from collections.abc import Callable, Hashable
from typing import Any

import msgspec

from tickfeeddmr.market_data.services.stream_selection import SelectionRule


class LiveStreamSpec[T, G: Hashable](msgspec.Struct, frozen=True):
    """Всё доменное, что нужно читателю: откуда читать и что считать событием.

    Собирается адаптерами (`live_trades.py`); правило отбора `rule`
    подменяется здесь, без правки читателя и контроллеров.

    `accept_raw` смотрит на сырые поля записи **до** `decode`: у каждого
    соединения своя выборка тикеров, а декодирование (`Decimal`,
    `fromisoformat`, `Struct`) на каждую запись стрима иначе стоило бы CPU всех
    соединений на весь поток, даже если клиенту нужен один тикер.
    """

    label: str
    stream_key: str
    accept_raw: Callable[[dict[str, str]], bool]
    decode: Callable[[dict[str, str]], T]
    group_key: Callable[[T], G]
    # Ключ порядка — любое сравнимое значение; `Any`, а не `SupportsRichComparison`
    # из `_typeshed`: типы полей `Struct` читаются в рантайме, а `_typeshed` там нет.
    order_key: Callable[[T], Any]
    rule: SelectionRule[T]
