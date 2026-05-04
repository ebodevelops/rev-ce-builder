import pytest


@pytest.fixture
def cisco_vendor(db):
    from apps.inventory.models import Vendor

    return Vendor.objects.create(name="Cisco", driver_key="cisco_iosxr")


@pytest.fixture
def ncs540(db, cisco_vendor):
    from apps.inventory.models import DeviceModel

    return DeviceModel.objects.create(
        vendor=cisco_vendor,
        name="NCS-540",
        target_software_version="7.10.2",
        software_image_filename="ncs540-mini-x-7.10.2.iso",
    )


@pytest.fixture
def site(db):
    from apps.inventory.models import Site

    return Site.objects.create(code="mpls-01", name="Minneapolis 1")


@pytest.fixture
def scenario(db, ncs540):
    from apps.inventory.models import DeploymentScenario

    return DeploymentScenario.objects.create(
        key="pe-core", device_model=ncs540, description="PE core scenario"
    )


@pytest.fixture
def device(db, ncs540, site, scenario):
    from apps.inventory.models import Device

    return Device.objects.create(
        serial_number="FOC2401TEST",
        hostname="mpls-rtr-01",
        device_model=ncs540,
        site=site,
        scenario=scenario,
    )
