from collections.abc import Callable, Hashable
from typing import Any

import msgspec

from tickfeeddmr.market_data.services.stream_selection import SelectionRule


class LiveStreamSpec[T, G: Hashable](msgspec.Struct, frozen=True):
    """Всё доменное, что нужно общему ридеру: откуда читать и что считать событием.

    Собирается адаптерами (`live_trades.py`); правило отбора `rule`
    подменяется здесь, без правки хаба и контроллеров.

    `raw_group_key` смотрит на сырые поля записи **до** `decode` и возвращает
    группу записи (тикер) или `None`, если запись ни к какой группе не
    относится. Хаб (`stream_reader/hub.py`) сам решает, нужна ли эта группа
    хоть одному текущему подписчику (по счётчику активных групп) — членство
    больше не знание спеки, в отличие от прежнего `accept_raw`, замкнутого на
    тикеры одного соединения. Дорогое декодирование (`Decimal`,
    `fromisoformat`, `Struct`) по-прежнему выполняется не более одного раза на
    запись и только для реально запрошенных групп, независимо от числа
    подписчиков на хабе.

    Отдельного `group_key` (группировка уже декодированного `T`) больше нет:
    `raw_group_key` определяет группу до декодирования, хаб буферизует записи
    сразу по этой группе, и повторно её выводить из `T` незачем.
    """

    label: str
    stream_key: str
    raw_group_key: Callable[[dict[str, str]], G | None]
    decode: Callable[[dict[str, str]], T]
    order_key: Callable[[T], Any]
    rule: SelectionRule[T]
