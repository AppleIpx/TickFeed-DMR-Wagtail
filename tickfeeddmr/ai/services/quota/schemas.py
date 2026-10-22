import msgspec


class QuotaUsage(msgspec.Struct, frozen=True):
    """Расход за текущие московские сутки."""

    requests: int
    tokens: int
