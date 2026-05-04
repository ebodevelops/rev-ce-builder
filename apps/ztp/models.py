import reversion
from django.db import models

from apps.core.models import TimestampedModel
from apps.inventory.models import Device


class GeneratedConfigStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    SUPERSEDED = "superseded", "Superseded"


@reversion.register()
class GeneratedConfig(TimestampedModel):
    """Materialized config for a device. Latest published row is what the
    HTTP file server hands to the device during ZTP.
    """

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="configs")
    rendered_at = models.DateTimeField(auto_now_add=True)
    rendered_by = models.CharField(max_length=128, blank=True)
    template_name = models.CharField(max_length=128)
    body = models.TextField()
    status = models.CharField(
        max_length=16,
        choices=GeneratedConfigStatus.choices,
        default=GeneratedConfigStatus.DRAFT,
        db_index=True,
    )
    git_commit_sha = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-rendered_at"]

    def __str__(self) -> str:
        return f"{self.device} @ {self.rendered_at:%Y-%m-%d %H:%M}"


class ZtpEventKind(models.TextChoices):
    DHCP_REQUEST = "dhcp_request", "DHCP request"
    BOOTFILE_FETCH = "bootfile_fetch", "Bootfile fetched"
    CONFIG_FETCH = "config_fetch", "Config fetched"
    IMAGE_FETCH = "image_fetch", "Image fetched"
    READY = "ready", "Device reported ready"
    FAILED = "failed", "Device reported failure"


class ZtpEvent(TimestampedModel):
    """Audit trail of ZTP-related interactions for a device."""

    device = models.ForeignKey(
        Device,
        on_delete=models.CASCADE,
        related_name="ztp_events",
        null=True,
        blank=True,
    )
    serial_number = models.CharField(max_length=64, db_index=True)
    kind = models.CharField(max_length=32, choices=ZtpEventKind.choices)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["serial_number", "kind"])]

    def __str__(self) -> str:
        return f"{self.serial_number} {self.kind} @ {self.created_at:%H:%M:%S}"
