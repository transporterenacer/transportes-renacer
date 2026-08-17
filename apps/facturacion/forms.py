from django import forms

from apps.facturacion.models import ClientPayment


class ClientPaymentForm(forms.ModelForm):
    class Meta:
        model = ClientPayment
        fields = ["valor", "fecha", "metodo", "observaciones"]
        widgets = {
            "fecha": forms.DateInput(format="%d/%m/%Y", attrs={"class": "date-input"})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha"].input_formats = ["%d/%m/%Y", "%Y-%m-%d"]
        self.fields["valor"].localize = True
        self.fields["metodo"].initial = ClientPayment.EFECTIVO