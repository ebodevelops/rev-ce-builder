from rest_framework import serializers

from .models import GeneratedConfig


class GeneratedConfigSerializer(serializers.ModelSerializer):
    device_serial = serializers.CharField(source="device.serial_number", read_only=True)
    device_hostname = serializers.CharField(source="device.hostname", read_only=True)

    class Meta:
        model = GeneratedConfig
        fields = [
            "id",
            "device",
            "device_serial",
            "device_hostname",
            "template_name",
            "status",
            "rendered_at",
            "rendered_by",
            "git_commit_sha",
            "body",
        ]
        read_only_fields = fields
