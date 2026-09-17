import asyncio


class RunBudget:
    """Абсолютный дедлайн одного прогона, отсчитанный от момента создания."""

    def __init__(self, budget_seconds: int) -> None:
        self._deadline = asyncio.get_running_loop().time() + budget_seconds
        self.budget_seconds = budget_seconds

    @property
    def expired(self) -> bool:
        return asyncio.get_running_loop().time() >= self._deadline
