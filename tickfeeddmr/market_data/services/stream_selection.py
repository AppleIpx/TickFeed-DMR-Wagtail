from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Hashable, Sequence

    from _typeshed import SupportsRichComparison

type SelectionRule[T] = Callable[[Sequence[T]], list[T]]


def latest[T](
    items: Sequence[T],
    *,
    n: int,
    key: Callable[[T], SupportsRichComparison],
) -> list[T]:
    """Не более `n` самых новых элементов по `key`, по возрастанию `key`.

    `key` — момент/порядковый номер события (у ленты сделок — пара
    `(timestamp, trade_id)`, чтобы сделки одной секунды упорядочивались
    детерминированно). Сортировка устойчивая.
    """
    if n <= 0:
        return []
    ordered = sorted(items, key=key)
    return ordered[-n:]


def select_per_group[T, G: Hashable](
    items: Sequence[T],
    *,
    group_key: Callable[[T], G],
    rule: SelectionRule[T],
    order_key: Callable[[T], SupportsRichComparison],
) -> list[T]:
    """Применить `rule` к каждой группе отдельно и слить результат.

    Нужна, чтобы активный тикер не вытеснял из ленты редкие: при отборе на
    весь поток самые новые N событий почти целиком достались бы самому
    ликвидному инструменту. Итог упорядочен по `order_key` (обычно то же
    время события), чтобы клиент получал ленту в хронологическом порядке.
    """
    groups: dict[G, list[T]] = {}
    for item in items:
        groups.setdefault(group_key(item), []).append(item)
    selected = [item for group in groups.values() for item in rule(group)]
    return sorted(selected, key=order_key)
