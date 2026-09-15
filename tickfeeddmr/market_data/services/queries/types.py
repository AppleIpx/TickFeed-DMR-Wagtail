from datetime import datetime

import msgspec


class Cursor(msgspec.Struct, frozen=True):
    """Разобранное значение курсора: точка `(timestamp, pk)` в потоке."""

    timestamp: datetime
    pk: int
