from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

import msgspec
from django_celery_beat.models import PeriodicTask

if TYPE_CHECKING:
    from collections.abc import Iterable


class ScheduleEntry(msgspec.Struct, frozen=True):
    """Периодическая запись `django_celery_beat` в виде, удобном шаблону."""

    schedule: str
    enabled: bool
    last_run_at: datetime | None


def load_schedule(task_names: Iterable[str]) -> dict[str, list[ScheduleEntry]]:
    """Расписание задач одним запросом; нет записи — нет ключа."""
    periodic_tasks = PeriodicTask.objects.filter(
        task__in=list(task_names),
    ).select_related(
        "interval",
        "crontab",
        "solar",
        "clocked",
    )
    entries: dict[str, list[ScheduleEntry]] = defaultdict(list)
    for periodic_task in periodic_tasks.order_by("name"):
        entries[periodic_task.task].append(
            ScheduleEntry(
                schedule=str(periodic_task.scheduler or "—"),
                enabled=periodic_task.enabled,
                last_run_at=periodic_task.last_run_at,
            ),
        )
    return dict(entries)
