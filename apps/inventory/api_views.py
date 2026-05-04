from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DeploymentScenario, Device, DeviceModel, Site, Vendor
from .serializers import (
    DeploymentScenarioSerializer,
    DeviceModelSerializer,
    DeviceSerializer,
    SiteSerializer,
    VendorSerializer,
)


class VendorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Vendor.objects.all()
    serializer_class = VendorSerializer


class DeviceModelViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeviceModel.objects.select_related("vendor").all()
    serializer_class = DeviceModelSerializer


class SiteViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer


class DeploymentScenarioViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DeploymentScenario.objects.select_related("device_model").all()
    serializer_class = DeploymentScenarioSerializer


class DeviceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Device.objects.select_related(
        "device_model", "device_model__vendor", "site", "scenario", "reserved_by"
    ).prefetch_related("interfaces")
    serializer_class = DeviceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["serial_number", "hostname", "staging_ip", "staging_mac"]
    ordering_fields = ["created_at", "hostname", "status"]
    filterset_fields = ["status", "site", "device_model"]

    @action(detail=True, methods=["post"])
    def reserve(self, request, pk=None):
        device = self.get_object()
        device.reserve(request.user, note=request.data.get("note", ""))
        return Response(self.get_serializer(device).data)

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        device = self.get_object()
        device.release()
        return Response(self.get_serializer(device).data)
