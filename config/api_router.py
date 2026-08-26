from django.urls import include, path

urlpatterns = [
    path("users/", include("tickfeeddmr.users.urls", namespace="users")),
]
