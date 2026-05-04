"""ZTP file-server endpoints + post-ZTP callback.

These endpoints are intentionally unauthenticated by default (devices in ZTP
have no creds yet). Set ZTP_REQUIRE_AUTH=True to require token auth for
hardened deployments where devices fetch over a tunneled mgmt path.

Endpoints:
  GET  /ztp/configs/<serial>.cfg     -> latest published config for serial
  GET  /ztp/bootfile/<serial>        -> per-device bootfile (Python ZTP script)
  GET  /ztp/images/<filename>        -> static image file from ZTP_FILES_ROOT/images/
  POST /ztp/callback/ready/<serial>  -> device reports ZTP success
  POST /ztp/callback/failed/<serial> -> device reports ZTP failure
"""

from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.inventory.models import Device, DeviceStatus

from .models import GeneratedConfig, GeneratedConfigStatus, ZtpEvent, ZtpEventKind
from .renderer import render_bootfile

logger = logging.getLogger(__name__)


def _client_ip(request) -> str | None:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _record_event(
    *,
    serial: str,
    kind: str,
    request,
    device: Device | None = None,
    detail: dict | None = None,
) -> None:
    ZtpEvent.objects.create(
        device=device,
        serial_number=serial,
        kind=kind,
        source_ip=_client_ip(request),
        detail=detail or {},
    )


@require_GET
def serve_config(request, serial: str):
    """Serve the most recent PUBLISHED config for a device, keyed by serial."""
    device = Device.objects.filter(serial_number=serial).first()
    if device is None:
        _record_event(serial=serial, kind=ZtpEventKind.CONFIG_FETCH, request=request,
                      detail={"error": "unknown_serial"})
        raise Http404("Unknown serial")

    config = (
        GeneratedConfig.objects.filter(
            device=device, status=GeneratedConfigStatus.PUBLISHED
        )
        .order_by("-rendered_at")
        .first()
    )
    if config is None:
        _record_event(serial=serial, kind=ZtpEventKind.CONFIG_FETCH, request=request,
                      device=device, detail={"error": "no_published_config"})
        raise Http404("No published config for this device")

    device.status = DeviceStatus.PROVISIONING
    device.last_ztp_event_at = timezone.now()
    device.last_ztp_event = "config_fetch"
    device.save(update_fields=["status", "last_ztp_event_at", "last_ztp_event", "updated_at"])

    _record_event(
        serial=serial,
        kind=ZtpEventKind.CONFIG_FETCH,
        request=request,
        device=device,
        detail={"config_id": config.pk, "rendered_at": config.rendered_at.isoformat()},
    )
    return HttpResponse(config.body, content_type="text/plain; charset=utf-8")


@require_GET
def serve_bootfile(request, serial: str):
    device = Device.objects.filter(serial_number=serial).first()
    if device is None:
        raise Http404("Unknown serial")
    body = render_bootfile(device)
    _record_event(
        serial=serial, kind=ZtpEventKind.BOOTFILE_FETCH, request=request, device=device
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


@require_GET
def serve_image(request, filename: str):
    safe = Path(filename).name  # strip any traversal
    image_root = Path(settings.ZTP_FILES_ROOT) / "images"
    target = image_root / safe
    if not target.is_file():
        raise Http404("Image not found")
    _record_event(
        serial=request.GET.get("serial", ""),
        kind=ZtpEventKind.IMAGE_FETCH,
        request=request,
        detail={"filename": safe},
    )
    return FileResponse(target.open("rb"), as_attachment=False, filename=safe)


@csrf_exempt
@require_POST
def callback_ready(request, serial: str):
    device = get_object_or_404(Device, serial_number=serial)
    device.status = DeviceStatus.READY
    device.last_ztp_event_at = timezone.now()
    device.last_ztp_event = "ready"
    device.save(update_fields=["status", "last_ztp_event_at", "last_ztp_event", "updated_at"])
    _record_event(
        serial=serial, kind=ZtpEventKind.READY, request=request, device=device
    )
    return JsonResponse({"ok": True, "status": device.status})


@csrf_exempt
@require_POST
def callback_failed(request, serial: str):
    device = get_object_or_404(Device, serial_number=serial)
    device.status = DeviceStatus.FAILED
    device.last_ztp_event_at = timezone.now()
    device.last_ztp_event = "failed"
    device.save(update_fields=["status", "last_ztp_event_at", "last_ztp_event", "updated_at"])
    _record_event(
        serial=serial,
        kind=ZtpEventKind.FAILED,
        request=request,
        device=device,
        detail={"body": request.body.decode("utf-8", errors="replace")[:2000]},
    )
    return JsonResponse({"ok": True, "status": device.status})
