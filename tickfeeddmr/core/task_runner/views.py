from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from tickfeeddmr.core.task_runner.services import RunStatus, build_rows, run_task

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)

URL_NAME = "task-runner"


@require_http_methods(["GET", "POST"])
def task_runner_view(request: HttpRequest) -> HttpResponse:
    """Страница ручного запуска Celery-задач; только для суперпользователя."""
    if not request.user.is_superuser:
        logger.warning(
            f"Отказ в доступе к запуску задач: пользователь {request.user.pk}",
        )
        raise PermissionDenied
    if request.method == "POST":
        return _handle_run(request)
    return _render_page(request)


def _render_page(request: HttpRequest) -> HttpResponse:
    context = {
        **admin.site.each_context(request),
        "title": "Запуск задач",
        "rows": build_rows(),
        "periodic_tasks_url": reverse(
            "admin:django_celery_beat_periodictask_changelist",
        ),
    }
    return TemplateResponse(request, "admin/task_runner/index.html", context)


def _handle_run(request: HttpRequest) -> HttpResponse:
    outcome = run_task(request.POST, user_pk=request.user.pk)
    if outcome.status is RunStatus.UNKNOWN_TASK:
        return HttpResponseBadRequest(outcome.message)
    level = messages.SUCCESS if outcome.status is RunStatus.QUEUED else messages.ERROR
    messages.add_message(request, level, outcome.message)
    return redirect(URL_NAME)
