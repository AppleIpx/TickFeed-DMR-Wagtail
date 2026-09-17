import msgspec


class StockCatchUpResult(msgspec.Struct, frozen=True):
    """Итог догона одного актива — сырые счётчики для лога вызывающей задачи."""

    written: int
    already_up_to_date: bool


class StockDailyCandlesRunResult(msgspec.Struct, frozen=True):
    """Итог ночного прогона по всем активным активам."""

    processed: int
    written: int
    skipped_errors: int
    budget_exhausted: bool


class FiatCatchUpResult(msgspec.Struct, frozen=True):
    """Итог догона одной валюты — сырые счётчики для лога вызывающей задачи."""

    written: int
    already_up_to_date: bool


class FiatDailyCandlesRunResult(msgspec.Struct, frozen=True):
    """Итог ночного прогона по всем активным валютам."""

    processed: int
    written: int
    skipped_errors: int
    budget_exhausted: bool


class CryptoCatchUpResult(msgspec.Struct, frozen=True):
    """Итог догона одного актива — сырые счётчики для лога вызывающей задачи."""

    written: int
    already_up_to_date: bool


class CryptoDailyCandlesRunResult(msgspec.Struct, frozen=True):
    """Итог ночного прогона по всем активным активам."""

    processed: int
    written: int
    skipped_errors: int
    budget_exhausted: bool
