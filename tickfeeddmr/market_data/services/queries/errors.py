from http import HTTPStatus

from config.api_base import DomainError


class AssetNotFoundError(DomainError):
    """Актив с данным символом не существует либо неактивен (`is_active=False`).

    Оба случая отдаются одной формулировкой намеренно: если бы ответ для
    "не существует" и "неактивен" отличался, по этому различию можно было
    бы установить сам факт существования неактивного актива.
    """

    status_code = HTTPStatus.NOT_FOUND


class NoDataYetError(DomainError):
    """Актив существует и активен, но по нему ещё нет ни одной точки данных.

    Например, актив только что добавлен в админке, а стрим/опрос ещё не
    успел записать ни одного снапшота. Не смешивать с `AssetNotFoundError`.
    """

    status_code = HTTPStatus.NOT_FOUND


class TradesNotTrackedError(DomainError):
    """Лента сделок для этого актива не ведётся (`StockAsset.track_trades=False`)."""

    status_code = HTTPStatus.NOT_FOUND


class InvalidCursorError(DomainError):
    """Курсор не парсится — это ошибка запроса (422), а не «не найдено» (404)."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY


class InvalidPeriodError(DomainError):
    """`from` больше `to` в запросе `history` — ошибка запроса (422)."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY


class StreamAssetsNotFoundError(DomainError):
    """Для SSE-стрима нечего стримить — ни один тикер не найден или не активен.

    404 (а не «200 + ошибка + закрытие потока») намеренно: браузерный
    `EventSource` на 404 перестаёт переподключаться, а на закрытый поток с
    200 будет долбиться каждые ~3 с. Текст ответа `EventSource` прочитать не
    может — он для curl/Swagger.
    """

    status_code = HTTPStatus.NOT_FOUND


class TooManyTickersError(DomainError):
    """В `symbols`/`secids` больше тикеров, чем разрешено настройкой — 422."""

    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
