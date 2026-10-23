from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tickfeeddmr.ai.services.tools.schemas import BigMoveRow


def truncate_latest(rows: Sequence[Any], n: int) -> tuple[list[Any], bool]:
    """Последние `n` строк и признак, что остальное отброшено."""
    return list(rows[-n:]), len(rows) > n


def truncate_strongest(
    rows: Sequence[BigMoveRow],
    n: int,
) -> tuple[list[BigMoveRow], bool]:
    """`n` самых сильных аномальных дней по дате и признак усечения."""
    strongest = sorted(
        rows,
        key=lambda r: (abs(r.z_score or 0), r.volume_ratio or 0),
        reverse=True,
    )[:n]
    return sorted(strongest, key=lambda r: r.date), len(rows) > n
