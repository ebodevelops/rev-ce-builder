from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.DeviceListView.as_view(), name="device_list"),
    path("devices/<int:pk>/", views.DeviceDetailView.as_view(), name="device_detail"),
    path("devices/<int:pk>/reserve/", views.reserve_device, name="device_reserve"),
    path("devices/<int:pk>/release/", views.release_device, name="device_release"),
]
