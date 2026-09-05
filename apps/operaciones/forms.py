from datetime import time

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


def _half_hour_choices():
    choices = [("", "--:--")]
    for h in range(24):
        for m in (0, 30):
            t = time(h, m)
            label = t.strftime("%H:%M")
            choices.append((label, label))
    return choices


class ShiftForm(forms.Form):
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.none(), label="Mula")
    driver = forms.ModelChoiceField(
        queryset=Driver.objects.all(), label="Conductor"
    )
    fecha_inicio_date = forms.DateField(
        label="Fecha de inicio",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fecha_inicio_time = forms.ChoiceField(
        choices=_half_hour_choices(), label="Hora de inicio"
    )
    fecha_fin_date = forms.DateField(
        label="Fecha de fin",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fecha_fin_time = forms.ChoiceField(
        choices=_half_hour_choices(), label="Hora de fin"
    )
    tipo = forms.ChoiceField(choices=[("dia", "Día"), ("noche", "Noche")], label="Tipo")
    novedad_categoria = forms.ModelChoiceField(
        queryset=IncidentCategory.objects.filter(activa=True),
        required=False,
        label="Novedad",
    )
    novedad_descripcion = forms.CharField(
        required=False, widget=forms.Textarea, label="Detalle de la novedad"
    )
    liberar_mula = forms.BooleanField(
        required=False,
        label="Este es el último turno de esta mula",
        help_text="Al guardar, retira la mula de esta operación y la deja disponible.",
    )


class ShiftStopForm(forms.Form):
    inicio = forms.ChoiceField(
        choices=_half_hour_choices(), label="Inicio parada"
    )
    fin = forms.ChoiceField(
        choices=_half_hour_choices(), label="Fin parada"
    )

    def clean(self):
        cleaned = super().clean()
        ini = cleaned.get("inicio")
        fin = cleaned.get("fin")
        if ini and fin and ini >= fin:
            raise forms.ValidationError("La hora de fin debe ser posterior a la de inicio.")
        return cleaned


ShiftStopFormSet = forms.formset_factory(
    ShiftStopForm, extra=0, can_delete=True
)
