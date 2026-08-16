from django import forms

from apps.facturacion.models import ClientPayment


class ClientPaymentForm(forms.ModelForm):
    class Meta:
        model = ClientPayment
        fields = ["valor", "fecha", "observaciones"]
