from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import (
    DeploymentScenario,
    Device,
    DeviceInterface,
    DeviceModel,
    Site,
    Vendor,
)


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "driver_key")
    search_fields = ("name", "driver_key")


@admin.register(DeviceModel)
class DeviceModelAdmin(admin.ModelAdmin):
    list_display = ("vendor", "name", "target_software_version", "software_image_filename")
    list_filter = ("vendor",)
    search_fields = ("name",)


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "region")
    search_fields = ("code", "name")


@admin.register(DeploymentScenario)
class DeploymentScenarioAdmin(admin.ModelAdmin):
    list_display = ("key", "device_model", "description")
    list_filter = ("device_model__vendor",)
    search_fields = ("key", "description")


class DeviceInterfaceInline(admin.TabularInline):
    model = DeviceInterface
    extra = 0


@admin.register(Device)
class DeviceAdmin(VersionAdmin):
    list_display = (
        "serial_number",
        "hostname",
        "device_model",
        "site",
        "status",
        "reserved_by",
        "staging_ip",
        "last_ztp_event",
    )
    list_filter = ("status", "device_model__vendor", "device_model", "site")
    search_fields = ("serial_number", "hostname", "staging_ip", "staging_mac")
    readonly_fields = ("staging_seen_at", "last_ztp_event_at", "reserved_at")
    inlines = [DeviceInterfaceInline]
