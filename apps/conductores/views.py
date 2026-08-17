from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.conductores.forms import DriverForm
from apps.conductores.models import Driver


@login_required
def conductores_lista(request):
    conductores = Driver.objects.all().order_by("nombre")
    return render(request, "conductores/list.html", {"conductores": conductores})


@login_required
def conductor_nuevo(request):
    if request.method == "POST":
        form = DriverForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("conductores:lista")
    else:
        form = DriverForm()
    return render(request, "conductores/form.html", {"form": form})


@login_required
def conductor_editar(request, pk):
    conductor = get_object_or_404(Driver, pk=pk)
    if request.method == "POST":
        form = DriverForm(request.POST, instance=conductor)
        if form.is_valid():
            form.save()
            return redirect("conductores:lista")
    else:
        form = DriverForm(instance=conductor)
    return render(
        request, "conductores/form.html", {"form": form, "conductor": conductor}
    )