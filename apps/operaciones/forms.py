from django import forms

from apps.catalogos.models import IncidentCategory
from apps.conductores.models import Driver
from apps.flota.models import Vehicle
from apps.operaciones.models import Operation
from apps.operaciones.services import mulas_disponibles


class OperationForm(forms.ModelForm):
    mulas = forms.ModelMultipleChoiceField(
        queryset=Vehicle.objects.none(), required=False, label="Mulas"
    )

    class Meta:
        model = Operation
        fields = [
            "codigo", "buque", "generador_de_carga", "puerto", "fecha_inicio",
            "fecha_fin_estimada", "meta_horas", "tarifa_hora",
            "valor_turno_dia", "valor_turno_noche", "observaciones",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mulas"].queryset = mulas_disponibles()


class ShiftForm(forms.Form):
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.none(), label="Mula")
    driver = forms.ModelChoiceField(
        queryset=Driver.objects.all(), label="Conductor"
    )
    fecha_inicio = forms.DateTimeField(label="Hora de inicio", input_formats=["%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"])
    fecha_fin = forms.DateTimeField(label="Hora de fin", input_formats=["%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"])
    tipo = forms.ChoiceField(choices=[("dia", "Día"), ("noche", "Noche")], label="Tipo")
    novedad_categoria = forms.ModelChoiceField(
        queryset=IncidentCategory.objects.filter(activa=True),
        required=False,
        label="Novedad",
    )
    novedad_descripcion = forms.CharField(
        required=False, widget=forms.Textarea, label="Detalle de la novedad"
    )
