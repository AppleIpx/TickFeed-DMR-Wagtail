class ToolInputError(Exception):
    """Ошибка для модели (неверные аргументы, нет актива или данных), не HTTP."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
