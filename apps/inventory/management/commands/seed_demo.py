"""Seed a tiny set of vendors / models / scenarios so the UI is usable
out of the box. Idempotent — safe to re-run.
"""

from django.core.management.base import BaseCommand

from apps.inventory.models import DeploymentScenario, DeviceModel, Site, Vendor


class Command(BaseCommand):
    help = "Seed demo vendors, device models, sites, and scenarios."

    def handle(self, *args, **options) -> None:
        cisco, _ = Vendor.objects.get_or_create(
            name="Cisco", defaults={"driver_key": "cisco_iosxr"}
        )
        ncs540, _ = DeviceModel.objects.get_or_create(
            vendor=cisco,
            name="NCS-540-ACC-SYS",
            defaults={
                "target_software_version": "7.10.2",
                "software_image_filename": "ncs540-mini-x-7.10.2.iso",
            },
        )
        DeploymentScenario.objects.get_or_create(
            key="pe-core",
            defaults={
                "device_model": ncs540,
                "description": "PE router with iBGP RR clients and core P2P uplinks.",
            },
        )
        Site.objects.get_or_create(code="mpls-01", defaults={"name": "Minneapolis 1", "region": "us-central"})
        self.stdout.write(self.style.SUCCESS("Seed complete."))
