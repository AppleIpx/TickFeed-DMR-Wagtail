from __future__ import annotations

from tickfeeddmr.market_data.services.stream_selection import latest, select_per_group


def test_latest_returns_empty_list_for_n_zero_or_negative() -> None:
    items = [1, 2, 3]

    assert latest(items, n=0, key=lambda x: x) == []
    assert latest(items, n=-1, key=lambda x: x) == []


def test_latest_keeps_last_n_by_key_not_first_n() -> None:
    items = [5, 1, 4, 2, 3]  # неотсортированы по значению

    result = latest(items, n=2, key=lambda x: x)

    assert result == [4, 5]


def test_latest_stable_sort_preserves_insertion_order_for_equal_keys() -> None:
    items = [("a", 1), ("b", 1), ("c", 1), ("d", 1)]

    result = latest(items, n=2, key=lambda item: item[1])

    assert result == [("c", 1), ("d", 1)]


def test_latest_n_greater_than_length_returns_all_sorted() -> None:
    items = [3, 1, 2]

    result = latest(items, n=100, key=lambda x: x)

    assert result == [1, 2, 3]


def test_select_per_group_rare_group_is_not_crowded_out_by_active_group() -> None:
    items = [
        ("a", 1),
        ("a", 2),
        ("a", 3),
        ("a", 4),
        ("a", 5),
        ("b", 10),
    ]

    result = select_per_group(
        items,
        group_key=lambda item: item[0],
        rule=lambda group: latest(group, n=2, key=lambda item: item[1]),
        order_key=lambda item: item[1],
    )

    groups_present = {item[0] for item in result}
    assert groups_present == {"a", "b"}
    assert ("b", 10) in result


def test_select_per_group_result_sorted_by_order_key_not_group_order() -> None:
    items = [
        ("second", 20),
        ("first", 5),
        ("second", 15),
        ("first", 1),
    ]

    result = select_per_group(
        items,
        group_key=lambda item: item[0],
        rule=lambda group: latest(group, n=10, key=lambda item: item[1]),
        order_key=lambda item: item[1],
    )

    assert [item[1] for item in result] == [1, 5, 15, 20]
