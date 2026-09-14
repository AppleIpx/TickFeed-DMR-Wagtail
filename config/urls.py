from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.views import defaults as default_views
from dmr.openapi.views import OpenAPIJsonView, SwaggerView
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from config.api_router import router as api_router
from config.api_router import schema as api_schema

docs_urlpatterns = [
    path(
        "api/docs/",
        staff_member_required(SwaggerView.as_view(schema=api_schema)),
        name="api-docs",
    ),
    path(
        "api/docs/openapi.json",
        staff_member_required(OpenAPIJsonView.as_view(schema=api_schema)),
        name="api-schema",
    ),
]

urlpatterns = [
    path(f"api/{settings.WAGTAIL_ADMIN_URL}", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path(f"api/{settings.ADMIN_URL}", admin.site.urls),
    *docs_urlpatterns,
    api_router.to_urlpatterns(namespace="api"),
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]
if settings.DEBUG:
    # Static file serving when using Gunicorn + Uvicorn for local web socket development
    urlpatterns += staticfiles_urlpatterns()


if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
            *urlpatterns,
        ]
