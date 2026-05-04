from rest_framework import serializers

from .models import DeploymentScenario, Device, DeviceInterface, DeviceModel, Site, Vendor


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["id", "name", "driver_key"]


class DeviceModelSerializer(serializers.ModelSerializer):
    vendor = VendorSerializer(read_only=True)

    class Meta:
        model = DeviceModel
        fields = [
            "id",
            "vendor",
            "name",
            "target_software_version",
            "software_image_filename",
        ]


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ["id", "code", "name", "region"]


class DeploymentScenarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeploymentScenario
        fields = ["id", "key", "description", "device_model"]


class DeviceInterfaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceInterface
        fields = [
            "id",
            "name",
            "description",
            "role",
            "ipv4_address",
            "ipv4_prefix_length",
            "ipv6_address",
            "ipv6_prefix_length",
        ]


class DeviceSerializer(serializers.ModelSerializer):
    device_model = DeviceModelSerializer(read_only=True)
    site = SiteSerializer(read_only=True)
    scenario = DeploymentScenarioSerializer(read_only=True)
    interfaces = DeviceInterfaceSerializer(many=True, read_only=True)
    reserved_by_username = serializers.CharField(source="reserved_by.username", read_only=True)

    class Meta:
        model = Device
        fields = [
            "id",
            "serial_number",
            "hostname",
            "device_model",
            "site",
            "scenario",
            "status",
            "console_server",
            "console_port",
            "staging_mac",
            "staging_ip",
            "staging_seen_at",
            "loopback0",
            "mgmt_ip",
            "reserved_by_username",
            "reserved_at",
            "reservation_note",
            "last_ztp_event_at",
            "last_ztp_event",
            "interfaces",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
