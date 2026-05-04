import pytest
from django.test import Client
from django.urls import reverse

from apps.inventory.models import DeviceStatus
from apps.ztp.models import GeneratedConfig, GeneratedConfigStatus, ZtpEvent


@pytest.mark.django_db
def test_serve_config_returns_published_body(device):
    GeneratedConfig.objects.create(
        device=device,
        template_name="pe-core.cfg.j2",
        body="hostname mpls-rtr-01\n",
        status=GeneratedConfigStatus.PUBLISHED,
    )
    client = Client()
    resp = client.get(reverse("ztp:serve_config", args=[device.serial_number]))
    assert resp.status_code == 200
    assert b"hostname mpls-rtr-01" in resp.content
    device.refresh_from_db()
    assert device.status == DeviceStatus.PROVISIONING
    assert ZtpEvent.objects.filter(serial_number=device.serial_number).exists()


@pytest.mark.django_db
def test_serve_config_unknown_serial_404(db):
    client = Client()
    resp = client.get(reverse("ztp:serve_config", args=["NOPE"]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_callback_ready_marks_device(device):
    client = Client()
    resp = client.post(reverse("ztp:callback_ready", args=[device.serial_number]))
    assert resp.status_code == 200
    device.refresh_from_db()
    assert device.status == DeviceStatus.READY
