from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from .models import Device, DeviceStatus


class DeviceListView(LoginRequiredMixin, ListView):
    model = Device
    template_name = "inventory/device_list.html"
    context_object_name = "devices"
    paginate_by = 50

    def get_queryset(self):
        qs = (
            Device.objects.select_related(
                "device_model", "device_model__vendor", "site", "scenario", "reserved_by"
            )
            .order_by("-created_at")
        )
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(serial_number__icontains=q) | qs.filter(hostname__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuses"] = DeviceStatus.choices
        ctx["selected_status"] = self.request.GET.get("status", "")
        ctx["query"] = self.request.GET.get("q", "")
        return ctx


class DeviceDetailView(LoginRequiredMixin, DetailView):
    model = Device
    template_name = "inventory/device_detail.html"
    context_object_name = "device"


@login_required
@require_POST
def reserve_device(request, pk: int):
    device = get_object_or_404(Device, pk=pk)
    note = request.POST.get("note", "").strip()
    device.reserve(request.user, note=note)
    if request.htmx:
        return render(request, "inventory/_device_row.html", {"device": device})
    return redirect("inventory:device_detail", pk=device.pk)


@login_required
@require_POST
def release_device(request, pk: int):
    device = get_object_or_404(Device, pk=pk)
    device.release()
    if request.htmx:
        return render(request, "inventory/_device_row.html", {"device": device})
    return redirect("inventory:device_detail", pk=device.pk)
