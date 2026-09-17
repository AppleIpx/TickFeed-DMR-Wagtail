"""Доменные ошибки read-сервисов API (этап 8a).

Наследуются от `config.api_base.DomainError`, а не от голого `Exception` —
только так `BaseController.handle_async_error` их узнаёт и не путает с
собственными исключениями DMR (см. докстринг `DomainError`).
"""

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
