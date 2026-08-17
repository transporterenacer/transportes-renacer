from django import forms

from apps.flota.models import Vehicle
from apps.operaciones.models import OperationVehicle


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ["placa", "marca", "modelo", "anio", "estado", "observaciones"]

    def clean_estado(self):
        estado = self.cleaned_data["estado"]
        instance = self.instance
        if (
            instance
            and instance.pk
            and estado in (Vehicle.EN_TALLER, Vehicle.FUERA_DE_SERVICIO)
            and OperationVehicle.objects.filter(vehicle=instance, activa=True).exists()
        ):
            raise forms.ValidationError(
                "La mula está asignada a una operación activa. "
                "Retírala de la operación antes de marcarla como "
                f"{dict(Vehicle.ESTADOS).get(estado, estado)}."
            )
        return estado