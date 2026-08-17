from django import forms

from apps.conductores.models import Driver


class DriverForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = ["nombre", "documento", "telefono", "estado", "observaciones"]