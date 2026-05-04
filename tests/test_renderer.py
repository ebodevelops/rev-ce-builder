"""Renderer test using a fake allocator so we don't hit Bluecat."""

from contextlib import contextmanager
from dataclasses import dataclass

import pytest

from apps.integrations.bluecat.allocator import AllocatedAddress, AllocatedNetwork
from apps.ztp.renderer import RenderError, render_device_config


@dataclass
class FakeAllocator:
    """Stand-in for BluecatAllocator that returns deterministic values."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def allocate_loopback(self, *, hostname, role_tag=None):
        return AllocatedAddress(
            address="10.0.0.1", prefix_length=32, bluecat_object_id="lo-1"
        )

    def allocate_p2p(self, *, hostname, interface, prefix_length=31, peer_label=None):
        return AllocatedNetwork(
            network="10.1.1.0", prefix_length=31, bluecat_object_id=f"p2p-{interface}"
        )


@pytest.mark.django_db
def test_render_device_config_happy_path(device):
    interface_specs = [
        {
            "name": "HundredGigE0/0/0/0",
            "role": "core",
            "peer_label": "core",
            "description": "to-mpls-rtr-02 Hu0/0/0/0",
        }
    ]
    gc = render_device_config(
        device,
        rendered_by="tester",
        interface_specs=interface_specs,
        allocator=FakeAllocator(),
    )
    device.refresh_from_db()
    assert "hostname mpls-rtr-01" in gc.body
    assert "Loopback0" in gc.body
    assert device.loopback0 == "10.0.0.1"
    assert device.interfaces.count() == 1
    iface = device.interfaces.first()
    assert iface.name == "HundredGigE0/0/0/0"
    assert iface.ipv4_address == "10.1.1.0"


@pytest.mark.django_db
def test_render_requires_hostname(device):
    device.hostname = ""
    device.save()
    with pytest.raises(RenderError):
        render_device_config(device, allocator=FakeAllocator())
