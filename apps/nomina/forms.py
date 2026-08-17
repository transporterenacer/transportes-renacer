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
        fields = ["driver", "fecha", "valor", "metodo", "descripcion"]
        widgets = {"fecha": forms.DateInput(format="%d/%m/%Y", attrs={"class": "date-input"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].input_formats = ["%d/%m/%Y", "%Y-%m-%d"]
        self.fields["valor"].localize = True
        self.fields["metodo"].initial = DriverAdvance.EFECTIVO


class DriverPagoForm(forms.Form):
    valor = forms.DecimalField(label="Valor del pago", max_digits=14, decimal_places=0)
    metodo = forms.ChoiceField(
        choices=DriverAdvance.METODOS, label="Método de pago"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metodo"].initial = DriverAdvance.EFECTIVO
        self.fields["valor"].localize = True