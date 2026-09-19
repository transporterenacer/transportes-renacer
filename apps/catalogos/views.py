import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from apps.catalogos.forms import CargoGeneratorForm, IncidentCategoryForm, PortForm, ProveedorForm
from apps.catalogos.models import CargoGenerator, IncidentCategory, Port, Proveedor
from apps.documentos.models import DocumentType


@login_required
def configuracion(request):
    return render(request, "catalogos/configuracion.html")


@login_required
def catalogos(request):
    context = {
        "puertos": Port.objects.all().order_by("nombre"),
        "generadores": CargoGenerator.objects.all().order_by("nombre"),
        "categorias": IncidentCategory.objects.all().order_by("nombre"),
        "proveedores": Proveedor.objects.all().order_by("nombre"),
        "puerto_form": PortForm(),
        "generador_form": CargoGeneratorForm(),
        "categoria_form": IncidentCategoryForm(),
        "proveedor_form": ProveedorForm(),
        "tipos_documento": DocumentType.objects.select_related("entity_type").order_by("entity_type__model", "nombre"),
    }
    return render(request, "catalogos/catalogos.html", context)


@login_required
def crear_puerto(request):
    if request.method == "POST":
        form = PortForm(request.POST)
        if form.is_valid():
            form.save()
    return redirect("catalogos:catalogos")


@login_required
def crear_generador(request):
    if request.method == "POST":
        form = CargoGeneratorForm(request.POST)
        if form.is_valid():
            form.save()
    return redirect("catalogos:catalogos")


@login_required
def crear_categoria(request):
    if request.method == "POST":
        form = IncidentCategoryForm(request.POST)
        if form.is_valid():
            form.save()
    return redirect("catalogos:catalogos")


@login_required
def api_crear_puerto(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    try:
        data = json.loads(request.body or b"{}")
        puerto = Port.objects.create(nombre=data.get("nombre", "").strip(), ciudad=data.get("ciudad", "").strip())
        return JsonResponse({"id": puerto.pk, "nombre": str(puerto)})
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": str(exc)}, status=400)


@login_required
def api_crear_generador(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    try:
        data = json.loads(request.body or b"{}")
        generador = CargoGenerator.objects.create(
            nombre=data.get("nombre", "").strip(),
            nit=data.get("nit", "").strip(),
            contacto=data.get("contacto", "").strip(),
            telefono=data.get("telefono", "").strip(),
        )
        return JsonResponse({"id": generador.pk, "nombre": str(generador)})
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": str(exc)}, status=400)


@login_required
def crear_proveedor(request):
    if request.method == "POST":
        form = ProveedorForm(request.POST)
        if form.is_valid():
            form.save()
    return redirect("catalogos:catalogos")


@login_required
def api_crear_proveedor(request):
    if request.method != "POST":
        return JsonResponse({"error": "Método no permitido"}, status=405)
    try:
        data = json.loads(request.body or b"{}")
        proveedor = Proveedor.objects.create(
            nombre=data.get("nombre", "").strip(),
            nit=data.get("nit", "").strip() or None,
            contacto=data.get("contacto", "").strip(),
            telefono=data.get("telefono", "").strip(),
        )
        return JsonResponse({"id": proveedor.pk, "nombre": str(proveedor)})
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"error": str(exc)}, status=400)


@login_required
def crear_documento_tipo(request):
    if request.method == "POST":
        from django.contrib.contenttypes.models import ContentType

        nombre = request.POST.get("nombre", "").strip()
        codigo = request.POST.get("codigo", "").strip().lower()
        entity_app = request.POST.get("entity_app", "flota")
        entity_model = request.POST.get("entity_model", "vehicle")
        requires_expiration = request.POST.get("requires_expiration") == "on"
        requires_issue_date = request.POST.get("requires_issue_date") == "on"

        if nombre and codigo:
            entity_type = ContentType.objects.get(app_label=entity_app, model=entity_model)
            DocumentType.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "entity_type": entity_type,
                    "requires_expiration": requires_expiration,
                    "requires_issue_date": requires_issue_date,
                },
            )
    return redirect("catalogos:catalogos")
