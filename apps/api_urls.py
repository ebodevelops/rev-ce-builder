from django.urls import include, path

urlpatterns = [
    path("inventory/", include("apps.inventory.api_urls")),
    path("ztp/", include("apps.ztp.api_urls")),
]
