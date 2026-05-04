"""Config + bootfile rendering pipeline.

Flow:
  1. Caller hands us a Device (hostname/site/scenario set, reserved by user).
  2. We allocate addressing from Bluecat (loopback, P2P /31s for each interface
     defined on the scenario).
  3. We render the config via the vendor driver's Jinja template.
  4. We persist a GeneratedConfig row (DB version history via django-reversion).
  5. Optionally enqueue a Celery task to mirror the rendered file into a
     git repo for human-readable diff/audit.
"""

from __future__ import annotations

import logging
from typing import Iterable

from django.conf import settings
from django.db import transaction

from apps.integrations.bluecat.allocator import BluecatAllocator
from apps.integrations.devices import DriverContext, get_driver
from apps.inventory.models import Device, DeviceInterface, DeviceStatus

from .models import GeneratedConfig, GeneratedConfigStatus

logger = logging.getLogger(__name__)


class RenderError(RuntimeError):
    """Raised when render preconditions aren't met."""


def render_device_config(
    device: Device,
    *,
    rendered_by: str = "",
    interface_specs: Iterable[dict] | None = None,
    allocator: BluecatAllocator | None = None,
    publish: bool = True,
) -> GeneratedConfig:
    """Render and persist a config for `device`.

    `interface_specs` is an iterable of dicts like:
        {"name": "HundredGigE0/0/0/0", "role": "core", "peer_label": "core",
         "description": "to-mpls-rtr-02 Hu0/0/0/0"}

    For each spec we allocate a /31 from the configured P2P pool and assign
    `.1` to this device. A loopback is allocated for Loopback0.
    """
    if not device.hostname:
        raise RenderError("Device hostname must be set before rendering")
    if not device.scenario:
        raise RenderError("Device scenario must be set before rendering")
    if not device.device_model.target_software_version:
        logger.warning("Device %s has no target_software_version", device)

    driver = get_driver(device.device_model.vendor.driver_key)
    interface_specs = list(interface_specs or [])

    allocator_cm = allocator or BluecatAllocator()
    with allocator_cm:
        # 1. Loopback0
        loopback = allocator_cm.allocate_loopback(hostname=device.hostname)

        # 2. P2P interfaces
        rendered_interfaces: list[dict] = []
        with transaction.atomic():
            device.loopback0 = loopback.address
            device.save(update_fields=["loopback0", "updated_at"])

            # Wipe + recreate interface rows (re-render replaces previous allocation set).
            device.interfaces.all().delete()

            for spec in interface_specs:
                allocated = allocator_cm.allocate_p2p(
                    hostname=device.hostname,
                    interface=spec["name"],
                    prefix_length=spec.get("prefix_length", 31),
                    peer_label=spec.get("peer_label"),
                )
                # /31 convention: this device takes the lower address.
                base_octets = allocated.network.split(".")
                ipv4 = ".".join(base_octets)
                rendered_interfaces.append(
                    {
                        "name": spec["name"],
                        "description": spec.get("description", ""),
                        "role": spec.get("role", ""),
                        "ipv4_address": ipv4,
                        "ipv4_netmask": "255.255.255.254",
                        "prefix_length": allocated.prefix_length,
                    }
                )
                DeviceInterface.objects.create(
                    device=device,
                    name=spec["name"],
                    description=spec.get("description", ""),
                    role=spec.get("role", ""),
                    ipv4_address=ipv4,
                    ipv4_prefix_length=allocated.prefix_length,
                    bluecat_object_id=allocated.bluecat_object_id,
                )

    # 3. Build driver context + render
    image_url = ""
    image_filename = device.device_model.software_image_filename
    if image_filename:
        image_url = f"{settings.ZTP_PUBLIC_BASE_URL}/ztp/images/{image_filename}"

    ctx = DriverContext(
        hostname=device.hostname,
        serial_number=device.serial_number,
        site_code=device.site.code if device.site else "",
        scenario_key=device.scenario.key,
        target_software_version=device.device_model.target_software_version,
        software_image_url=image_url,
        loopback0=loopback.address,
        interfaces=rendered_interfaces,
        extra={},
    )
    template_name = f"{device.scenario.key}.cfg.j2"
    body = driver.render_config(ctx, template_name)

    # 4. Persist
    with transaction.atomic():
        GeneratedConfig.objects.filter(
            device=device, status=GeneratedConfigStatus.PUBLISHED
        ).update(status=GeneratedConfigStatus.SUPERSEDED)
        gc = GeneratedConfig.objects.create(
            device=device,
            rendered_by=rendered_by,
            template_name=template_name,
            body=body,
            status=(
                GeneratedConfigStatus.PUBLISHED if publish else GeneratedConfigStatus.DRAFT
            ),
        )
        if publish:
            device.status = DeviceStatus.CONFIG_GENERATED
            device.save(update_fields=["status", "updated_at"])

    # 5. Optional git mirror
    if publish and settings.GIT_MIRROR["ENABLED"]:
        from .tasks import mirror_config_to_git

        mirror_config_to_git.delay(gc.pk)

    logger.info(
        "Rendered config for %s (template=%s, %d interfaces)",
        device.hostname,
        template_name,
        len(rendered_interfaces),
    )
    return gc


def render_bootfile(device: Device) -> str:
    """Render the per-device ZTP bootfile."""
    driver = get_driver(device.device_model.vendor.driver_key)
    image_url = ""
    image_filename = device.device_model.software_image_filename
    if image_filename:
        image_url = f"{settings.ZTP_PUBLIC_BASE_URL}/ztp/images/{image_filename}"
    config_url = (
        f"{settings.ZTP_PUBLIC_BASE_URL}/ztp/configs/{device.serial_number}.cfg"
    )
    ctx = DriverContext(
        hostname=device.hostname or "",
        serial_number=device.serial_number,
        site_code=device.site.code if device.site else "",
        scenario_key=device.scenario.key if device.scenario else "",
        target_software_version=device.device_model.target_software_version,
        software_image_url=image_url,
        loopback0=device.loopback0 or "",
    )
    return driver.render_bootfile(ctx, config_url=config_url)
