def pct(x: float) -> float:
    """Доля → проценты, округление до двух знаков."""
    return round(x * 100, 2) + 0.0


def price(x: float) -> float:
    """Цена, округлённая до шести значащих цифр."""
    return float(f"{x:.6g}")


def pct_or_none(x: float | None) -> float | None:
    """То же, что `pct`, но `None` остаётся `None`."""
    return None if x is None else pct(x)
