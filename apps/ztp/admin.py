from django.contrib import admin
from reversion.admin import VersionAdmin

from .models import GeneratedConfig, ZtpEvent


@admin.register(GeneratedConfig)
class GeneratedConfigAdmin(VersionAdmin):
    list_display = ("device", "template_name", "status", "rendered_at", "rendered_by")
    list_filter = ("status", "template_name")
    search_fields = ("device__hostname", "device__serial_number")
    readonly_fields = ("rendered_at", "git_commit_sha")


@admin.register(ZtpEvent)
class ZtpEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "serial_number", "kind", "device", "source_ip")
    list_filter = ("kind",)
    search_fields = ("serial_number", "device__hostname")
    readonly_fields = ("created_at",)
