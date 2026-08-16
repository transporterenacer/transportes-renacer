from django.contrib import admin

from apps.documentos.models import DocumentType


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "entity_type", "requires_expiration", "replace_previous", "is_required", "activo")
    list_filter = ("entity_type", "activo")
    search_fields = ("nombre", "codigo")
