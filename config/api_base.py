from dmr import Controller
from dmr.plugins.msgspec import MsgspecSerializer


class BaseController(Controller[MsgspecSerializer]):
    """Общий базовый контроллер: сериализация через msgspec."""

    serializer = MsgspecSerializer
