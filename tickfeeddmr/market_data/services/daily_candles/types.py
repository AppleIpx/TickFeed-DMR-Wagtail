import msgspec


class CatchUpResult(msgspec.Struct, frozen=True):
    """Итог догона одного актива — сырые счётчики для лога вызывающей задачи."""

    written: int
    already_up_to_date: bool


class DailyCandlesRunResult(msgspec.Struct, frozen=True):
    """Итог ночного прогона по всем активным активам домена."""

    processed: int
    written: int
    skipped_errors: int
    budget_exhausted: bool


class RunMessages(msgspec.Struct, frozen=True):
    """Русскоязычные тексты лога прогона — единственное, что у каждого домена своё.

    `run_started`/`budget_exhausted`/`provider_unavailable`/`unexpected_error`/
    `run_summary` — шаблоны под `str.format(...)`, `no_active_assets`/
    `lock_busy` подставлять некуда — это готовые строки.
    """

    no_active_assets: str
    lock_busy: str
    run_started: str
    budget_exhausted: str
    provider_unavailable: str
    unexpected_error: str
    run_summary: str
