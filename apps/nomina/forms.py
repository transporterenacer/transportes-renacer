from django import forms

from apps.nomina.models import DriverAdvance


class PeriodoForm(forms.Form):
    periodo_inicio = forms.DateField(label="Inicio del periodo", input_formats=["%d/%m/%Y", "%Y-%m-%d"])
    periodo_fin = forms.DateField(label="Fin del periodo", input_formats=["%d/%m/%Y", "%Y-%m-%d"])

    def clean(self):
        data = super().clean()
        if data.get("periodo_inicio") and data.get("periodo_fin"):
            if data["periodo_fin"] < data["periodo_inicio"]:
                raise forms.ValidationError("El fin del periodo no puede ser anterior al inicio.")
        return data


class DriverAdvanceForm(forms.ModelForm):
    class Meta:
        model = DriverAdvance
        fields = ["driver", "valor", "descripcion", "fecha"]
