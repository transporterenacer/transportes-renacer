from django import forms

from apps.documentos.models import DocumentType


class DocumentoForm(forms.Form):
    tipo = forms.ModelChoiceField(
        queryset=DocumentType.objects.filter(activo=True),
        to_field_name="codigo",
        label="Tipo de documento",
    )
    archivo = forms.FileField(label="Archivo")
    fecha_expedicion = forms.DateField(
        required=False, label="Fecha de expedición",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    fecha_vencimiento = forms.DateField(
        required=False, label="Fecha de vencimiento",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        self.entidad = kwargs.pop("entidad", None)
        super().__init__(*args, **kwargs)
        if self.entidad is not None:
            self.fields["tipo"].queryset = DocumentType.objects.filter(
                entity_type__model=self.entidad.__class__.__name__.lower(),
                activo=True,
            )
