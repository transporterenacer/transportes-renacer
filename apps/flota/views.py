from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.flota.forms import VehicleForm
from apps.flota.models import Vehicle


@login_required
def flota_lista(request):
    vehiculos = Vehicle.objects.all().order_by("placa")
    resumen = {
        "total": vehiculos.count(),
        "en_operacion": vehiculos.filter(estado=Vehicle.EN_OPERACION).count(),
        "disponibles": vehiculos.filter(estado=Vehicle.DISPONIBLE).count(),
        "en_taller": vehiculos.filter(estado=Vehicle.EN_TALLER).count(),
        "fuera_de_servicio": vehiculos.filter(estado=Vehicle.FUERA_DE_SERVICIO).count(),
    }
    return render(
        request,
        "flota/list.html",
        {"vehiculos": vehiculos, "resumen": resumen},
    )


@login_required
def vehiculo_nuevo(request):
    if request.method == "POST":
        form = VehicleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("flota:lista")
    else:
        form = VehicleForm()
    return render(request, "flota/form.html", {"form": form})


@login_required
def vehiculo_editar(request, pk):
    vehiculo = get_object_or_404(Vehicle, pk=pk)
    if request.method == "POST":
        form = VehicleForm(request.POST, instance=vehiculo)
        if form.is_valid():
            form.save()
            return redirect("flota:lista")
    else:
        form = VehicleForm(instance=vehiculo)
    return render(request, "flota/form.html", {"form": form, "vehiculo": vehiculo})