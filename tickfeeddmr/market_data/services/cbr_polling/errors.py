class CbrPollBudgetExceededError(Exception):
    """Прогон опроса ЦБ не уложился в `CBR_POLL_BUDGET_SECONDS`."""

    def __init__(self, message: str, *, last_failure_reason: str | None = None) -> None:
        super().__init__(message)
        self.last_failure_reason = last_failure_reason
