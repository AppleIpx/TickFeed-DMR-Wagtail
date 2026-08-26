from __future__ import annotations

from typing import TYPE_CHECKING

from wagtail import hooks

if TYPE_CHECKING:
    from django.http import HttpRequest
    from wagtail.admin.menu import MenuItem

UNWANTED_ITEM_NAMES = frozenset(
    (
        # "documents",
        "explorer",
        "help",
        "videos",
        "snippets",
        "reports",
    ),
)

MENU_ORDER: dict[str, int] = {
    "images": 200,
    "reports": 210,
    "settings": 220,
}


@hooks.register("construct_main_menu")
def hide_pages_menu(request: HttpRequest, menu_items: list[MenuItem]) -> None:
    """Скрытие ненужных меню в админке вагтейла"""
    menu_items[:] = [
        item for item in menu_items if item.name not in UNWANTED_ITEM_NAMES
    ]
    for item in menu_items:
        if item.name in MENU_ORDER:
            item.order = MENU_ORDER[item.name]


@hooks.register("construct_settings_menu")
def hide_settings_item(request, menu_items):
    """Скрываем ненужные пункты меню настроек."""
    excluded_items = [
        "groups",
        "collections",
        "workflows",
        "workflow-tasks",
        "redirects",
        "sites",
        "locales",
        "u041bu043eu043au0430u043bu0438",
        "users",
    ]
    menu_items[:] = [item for item in menu_items if item.name not in excluded_items]
