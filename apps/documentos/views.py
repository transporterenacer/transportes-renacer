from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.documentos.forms import DocumentoForm
from apps.documentos.models import Document, DocumentType
from apps.documentos.services import (
    alertas_vencimiento_documentos,
    cargar_documento,
    desactivar_conductor as desactivar_conductor_service,
    documentos_faltantes,
    documentos_vigentes_entidad,
    estado_documento,
    indicador_almacenamiento,
)
from apps.documentos.storage import get_storage_backend
from apps.conductores.models import Driver
from apps.flota.models import Vehicle


def _estado_ui(doc):
    estado = estado_documento(doc)
    if estado == Document.VIGENTE:
        return "registrado" if not doc.fecha_vencimiento else "vigente"
    return estado


def _ficha_url(entidad, pk):
    if isinstance(entidad, Vehicle):
        return reverse("documentos:vehicle", kwargs={"pk": pk})
    return reverse("documentos:driver", kwargs={"pk": pk})


@login_required
def panel(request):
    alertas = alertas_vencimiento_documentos()
    faltantes = documentos_faltantes()
    context = {
        "indicadores": {
            "vigentes": Document.objects.filter(estado=Document.VIGENTE).count(),
            "proximos": len([a for a in alertas if a["estado"] == "proximo"]),
            "vencidos": len([a for a in alertas if a["estado"] == "vencido"]),
            "faltantes": len(faltantes),
        },
        "alertas": alertas,
        "faltantes": faltantes,
        "indicador_almacenamiento": indicador_almacenamiento(),
    }
    return render(request, "documentos/panel.html", context)


@login_required
def ficha_vehicle(request, pk):
    vehicle = get_object_or_404(Vehicle, pk=pk)
    documentos = [
        {"doc": doc, "estado_ui": _estado_ui(doc)}
        for doc in documentos_vigentes_entidad(vehicle).select_related("tipo")
    ]
    context = {
        "vehicle": vehicle,
        "documentos": documentos,
        "today": timezone.localdate(),
    }
    return render(request, "documentos/ficha_vehicle.html", context)


@login_required
def ficha_driver(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    documentos = [
        {"doc": doc, "estado_ui": _estado_ui(doc)}
        for doc in documentos_vigentes_entidad(driver).select_related("tipo")
    ]
    context = {
        "driver": driver,
        "documentos": documentos,
        "today": timezone.localdate(),
    }
    return render(request, "documentos/ficha_driver.html", context)


@login_required
def subir(request):
    vehicle = request.GET.get("vehicle")
    driver = request.GET.get("driver")
    entidad = None
    if vehicle:
        entidad = get_object_or_404(Vehicle, pk=vehicle)
    elif driver:
        entidad = get_object_or_404(Driver, pk=driver)

    form = DocumentoForm(request.POST or None, request.FILES or None, entidad=entidad)
    if request.method == "POST" and form.is_valid():
        archivo = form.cleaned_data["archivo"]
        try:
            cargar_documento(
                tipo=form.cleaned_data["tipo"],
                entidad=entidad,
                archivo=archivo,
                content_type=archivo.content_type or "application/octet-stream",
                extension=archivo.name.rsplit(".", 1)[-1].lower(),
                tamano=archivo.size,
                fecha_expedicion=form.cleaned_data.get("fecha_expedicion"),
                fecha_vencimiento=form.cleaned_data.get("fecha_vencimiento"),
                usuario=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            return redirect(_ficha_url(entidad, entidad.pk))
    context = {
        "form": form,
        "entidad": entidad,
        "cancelar_url": _ficha_url(entidad, entidad.pk) if entidad else reverse("documentos:panel"),
    }
    return render(request, "documentos/documento_form.html", context)


@login_required
def ver(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if settings.DOCUMENT_STORAGE_BACKEND == "local":
        return HttpResponseRedirect(
            reverse("documentos:media", kwargs={"storage_path": doc.storage_path})
        )
    url = get_storage_backend().signed_url(doc.storage_path, settings.DOCUMENT_SIGNED_URL_EXPIRES)
    return HttpResponseRedirect(url)


@login_required
def descargar(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if settings.DOCUMENT_STORAGE_BACKEND == "local":
        response = HttpResponse(
            get_storage_backend().descargar(doc.storage_path),
            content_type=doc.mime_type,
        )
        response["Content-Disposition"] = f'attachment; filename="{doc.nombre_archivo}"'
        return response
    url = get_storage_backend().signed_url(doc.storage_path, settings.DOCUMENT_SIGNED_URL_EXPIRES)
    return HttpResponseRedirect(url)


@login_required
def reemplazar(request, pk):
    anterior = get_object_or_404(Document, pk=pk)
    form = DocumentoForm(
        request.POST or None, request.FILES or None, entidad=anterior.entity
    )
    form.fields.pop("tipo", None)
    if request.method == "POST" and form.is_valid():
        archivo = form.cleaned_data["archivo"]
        try:
            cargar_documento(
                tipo=anterior.tipo,
                entidad=anterior.entity,
                archivo=archivo,
                content_type=archivo.content_type or "application/octet-stream",
                extension=archivo.name.rsplit(".", 1)[-1].lower(),
                tamano=archivo.size,
                fecha_expedicion=form.cleaned_data.get("fecha_expedicion")
                or anterior.fecha_expedicion,
                fecha_vencimiento=form.cleaned_data.get("fecha_vencimiento")
                or anterior.fecha_vencimiento,
                usuario=request.user,
            )
        except ValidationError as exc:
            form.add_error(None, exc.message)
        else:
            return redirect(_ficha_url(anterior.entity, anterior.entity.pk))
    context = {
        "documento": anterior,
        "form": form,
        "cancelar_url": _ficha_url(anterior.entity, anterior.entity.pk),
    }
    return render(request, "documentos/reemplazo_confirm.html", context)


@login_required
def desactivar_conductor(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    if request.method == "POST":
        desactivar_conductor_service(driver, usuario=request.user)
        return redirect("documentos:driver", pk=driver.pk)
    return render(request, "documentos/desactivar_confirm.html", {"driver": driver})


@login_required
def media(request, storage_path):
    if settings.DOCUMENT_STORAGE_BACKEND != "local":
        raise Http404
    storage = get_storage_backend()
    if not storage.existe(storage_path):
        raise Http404
    return HttpResponse(
        storage.descargar(storage_path),
        content_type="application/octet-stream",
    )
