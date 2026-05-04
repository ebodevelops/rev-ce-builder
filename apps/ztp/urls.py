from django.urls import path

from . import views

app_name = "ztp"

urlpatterns = [
    path("configs/<str:serial>.cfg", views.serve_config, name="serve_config"),
    path("bootfile/<str:serial>", views.serve_bootfile, name="serve_bootfile"),
    path("images/<str:filename>", views.serve_image, name="serve_image"),
    path("callback/ready/<str:serial>", views.callback_ready, name="callback_ready"),
    path("callback/failed/<str:serial>", views.callback_failed, name="callback_failed"),
]
