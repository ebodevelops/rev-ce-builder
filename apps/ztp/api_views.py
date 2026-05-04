from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.inventory.models import Device

from .models import GeneratedConfig
from .renderer import RenderError, render_device_config
from .serializers import GeneratedConfigSerializer


class GeneratedConfigViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = GeneratedConfig.objects.select_related("device").all()
    serializer_class = GeneratedConfigSerializer
    filterset_fields = ["device", "status"]

    @action(detail=False, methods=["post"], url_path="render")
    def render(self, request):
        device_id = request.data.get("device_id")
        if not device_id:
            return Response(
                {"error": "device_id required"}, status=status.HTTP_400_BAD_REQUEST
            )
        device = Device.objects.filter(pk=device_id).first()
        if device is None:
            return Response({"error": "device not found"}, status=status.HTTP_404_NOT_FOUND)
        interface_specs = request.data.get("interfaces", [])
        try:
            gc = render_device_config(
                device,
                rendered_by=getattr(request.user, "username", "") or "",
                interface_specs=interface_specs,
            )
        except RenderError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(gc).data, status=status.HTTP_201_CREATED)
