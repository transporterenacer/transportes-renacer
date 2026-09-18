from django import forms

from apps.catalogos.models import CargoGenerator, IncidentCategory, Port, Proveedor


class PortForm(forms.ModelForm):
    class Meta:
        model = Port
        fields = ["nombre", "ciudad"]


class CargoGeneratorForm(forms.ModelForm):
    class Meta:
        model = CargoGenerator
        fields = ["nombre", "nit", "contacto", "telefono"]


class IncidentCategoryForm(forms.ModelForm):
    class Meta:
        model = IncidentCategory
        fields = ["nombre", "activa"]


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ["nombre", "nit", "contacto", "telefono"]
