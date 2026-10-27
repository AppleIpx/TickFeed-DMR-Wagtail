from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING, Any

import msgspec
from kombu.exceptions import OperationalError

from tickfeeddmr.core.task_runner.forms import AssetRunForm
from tickfeeddmr.core.task_runner.registry import SPECS_BY_NAME, TASKS, TaskSpec
from tickfeeddmr.core.task_runner.schedule import ScheduleEntry, load_schedule

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)


class TaskRow(msgspec.Struct, frozen=True):
    name: str
    spec: TaskSpec
    schedule: list[ScheduleEntry]
    form: Any = None


class RunStatus(enum.Enum):
    QUEUED = "queued"
    UNKNOWN_TASK = "unknown_task"
    INVALID_ASSET = "invalid_asset"
    BROKER_DOWN = "broker_down"


class RunOutcome(msgspec.Struct, frozen=True):
    status: RunStatus
    message: str


def build_rows() -> list[TaskRow]:
    """Строки страницы: задача, её расписание и форма выбора актива."""
    schedule = load_schedule(spec.task.name for spec in TASKS)
    return [
        TaskRow(
            name=spec.task.name,
            spec=spec,
            schedule=schedule.get(spec.task.name, []),
            form=(
                AssetRunForm(asset_model=spec.asset_model, auto_id=f"id_{index}_%s")
                if spec.asset_model
                else None
            ),
        )
        for index, spec in enumerate(TASKS)
    ]


def run_task(data: Mapping[str, str], *, user_pk: int) -> RunOutcome:
    """Поставить в очередь задачу из реестра по данным формы."""
    spec = SPECS_BY_NAME.get(data.get("task", ""))
    if spec is None:
        return RunOutcome(RunStatus.UNKNOWN_TASK, "Неизвестная задача.")

    args: tuple[int, ...] = ()
    if spec.asset_model is not None:
        form = AssetRunForm(data, asset_model=spec.asset_model)
        if not form.is_valid():
            return RunOutcome(
                RunStatus.INVALID_ASSET,
                f"«{spec.title}»: выберите активный актив из списка.",
            )
        args = (form.cleaned_data["asset"].pk,)

    try:
        result = spec.task.delay(*args)
    except OperationalError:
        logger.exception(f"Не удалось поставить задачу {spec.task.name} в очередь")
        return RunOutcome(
            RunStatus.BROKER_DOWN,
            f"«{spec.title}»: брокер недоступен, задача не поставлена в очередь.",
        )

    logger.info(
        f"Ручной запуск задачи {spec.task.name}: пользователь {user_pk}, "
        f"аргументы {args}, id {result.id}",
    )
    text = (
        f"«{spec.title}» поставлена в очередь (id {result.id}). "
        "Результат — в логах celeryworker."
    )
    if spec.takes_lock:
        text += " Если предыдущий запуск ещё идёт, воркер пропустит этот."
    return RunOutcome(RunStatus.QUEUED, text)
