import reversion
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimestampedModel


class Vendor(TimestampedModel):
    name = models.CharField(max_length=64, unique=True)
    driver_key = models.SlugField(
        max_length=64,
        unique=True,
        help_text="Identifier matching apps.integrations.devices driver registry "
        "(e.g. 'cisco_iosxr', 'juniper_junos', 'arista_eos').",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DeviceModel(TimestampedModel):
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="models")
    name = models.CharField(max_length=64, help_text="e.g. NCS-540-ACC-SYS, ASR-9901")
    target_software_version = models.CharField(
        max_length=64,
        blank=True,
        help_text="Desired image version. ZTP will upgrade if device version is older.",
    )
    software_image_filename = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["vendor__name", "name"]
        unique_together = [("vendor", "name")]

    def __str__(self) -> str:
        return f"{self.vendor.name} {self.name}"


class Site(TimestampedModel):
    code = models.SlugField(max_length=16, unique=True, help_text="Short site code, e.g. mpls-01")
    name = models.CharField(max_length=128)
    region = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} ({self.name})"


class DeploymentScenario(TimestampedModel):
    """Selects which config template to render. Examples: 'pe-core', 'pe-edge-dual-rr'."""

    key = models.SlugField(max_length=64, unique=True)
    description = models.CharField(max_length=255, blank=True)
    device_model = models.ForeignKey(
        DeviceModel,
        on_delete=models.PROTECT,
        related_name="scenarios",
    )

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class DeviceStatus(models.TextChoices):
    DISCOVERED = "discovered", "Discovered (in lab)"
    AVAILABLE = "available", "Available"
    RESERVED = "reserved", "Reserved"
    CONFIG_GENERATED = "config_generated", "Config generated"
    PROVISIONING = "provisioning", "Provisioning (ZTP in progress)"
    READY = "ready", "Ready (config loaded)"
    DEPLOYED = "deployed", "Deployed to prod"
    FAILED = "failed", "Failed"
    DECOMMISSIONED = "decommissioned", "Decommissioned"


@reversion.register()
class Device(TimestampedModel):
    serial_number = models.CharField(max_length=64, unique=True, db_index=True)
    hostname = models.CharField(max_length=128, blank=True, db_index=True)
    device_model = models.ForeignKey(
        DeviceModel,
        on_delete=models.PROTECT,
        related_name="devices",
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.PROTECT,
        related_name="devices",
        null=True,
        blank=True,
    )
    scenario = models.ForeignKey(
        DeploymentScenario,
        on_delete=models.PROTECT,
        related_name="devices",
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=32,
        choices=DeviceStatus.choices,
        default=DeviceStatus.DISCOVERED,
        db_index=True,
    )

    # Lab/console-server discovery
    console_server = models.CharField(max_length=128, blank=True)
    console_port = models.CharField(max_length=32, blank=True)
    staging_mac = models.CharField(max_length=17, blank=True, help_text="From DHCP lease.")
    staging_ip = models.GenericIPAddressField(null=True, blank=True)
    staging_seen_at = models.DateTimeField(null=True, blank=True)

    # IPAM-derived addressing (cached on render)
    loopback0 = models.GenericIPAddressField(null=True, blank=True)
    mgmt_ip = models.GenericIPAddressField(null=True, blank=True)

    # Reservation
    reserved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reserved_devices",
    )
    reserved_at = models.DateTimeField(null=True, blank=True)
    reservation_note = models.CharField(max_length=255, blank=True)

    # ZTP
    last_ztp_event_at = models.DateTimeField(null=True, blank=True)
    last_ztp_event = models.CharField(max_length=64, blank=True)

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.hostname or self.serial_number} ({self.device_model})"

    def reserve(self, user, note: str = "") -> None:
        self.reserved_by = user
        self.reserved_at = timezone.now()
        self.reservation_note = note
        self.status = DeviceStatus.RESERVED
        self.save(update_fields=["reserved_by", "reserved_at", "reservation_note", "status", "updated_at"])

    def release(self) -> None:
        self.reserved_by = None
        self.reserved_at = None
        self.reservation_note = ""
        if self.status == DeviceStatus.RESERVED:
            self.status = DeviceStatus.AVAILABLE
        self.save(update_fields=["reserved_by", "reserved_at", "reservation_note", "status", "updated_at"])


class InterfaceRole(models.TextChoices):
    UPLINK = "uplink", "Uplink"
    CORE = "core", "Core"
    PEER = "peer", "Peer"
    CUSTOMER = "customer", "Customer"
    MGMT = "mgmt", "Management"


class DeviceInterface(TimestampedModel):
    """Per-device interface assignment, populated when config is generated."""

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="interfaces")
    name = models.CharField(max_length=64, help_text="e.g. HundredGigE0/0/0/0")
    description = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=32, choices=InterfaceRole.choices, blank=True)

    ipv4_address = models.GenericIPAddressField(protocol="IPv4", null=True, blank=True)
    ipv4_prefix_length = models.PositiveSmallIntegerField(null=True, blank=True)
    ipv6_address = models.GenericIPAddressField(protocol="IPv6", null=True, blank=True)
    ipv6_prefix_length = models.PositiveSmallIntegerField(null=True, blank=True)

    bluecat_object_id = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        ordering = ["device", "name"]
        unique_together = [("device", "name")]

    def __str__(self) -> str:
        return f"{self.device}:{self.name}"
