"""Оркестрация опроса ISS MOEX: снимок борда (`board.py`) и лента сделок (`trades.py`).

`market_data/tasks.py` содержит только `@shared_task`-обёртки над
`poll_board()`/`poll_trades()` отсюда — по конвенции "тонкие
контроллеры, логика в services/", применённой к Celery-задачам.
`poll_board()`/`poll_trades()` — единственный публичный API пакета; сами
классы (`MoexBoardPoller`/`MoexTradePoller`) снаружи пакета не
используются и специально не реэкспортированы.
"""

from tickfeeddmr.market_data.services.moex_polling.board import poll_board
from tickfeeddmr.market_data.services.moex_polling.trades import poll_trades

__all__ = [
    "poll_board",
    "poll_trades",
]
