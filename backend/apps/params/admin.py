from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html

from apps.params.models import AppParameter, AppDocument


@admin.register(AppParameter)
class AppParameterAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description', 'updated_at')
    search_fields = ('key', 'description')
    ordering = ('key',)


class AppDocumentForm(forms.ModelForm):
    upload_file = forms.FileField(
        required=False,
        label='Upload .md bestand',
        help_text='Upload een Markdown (.md) bestand om de inhoud te overschrijven.',
    )

    class Meta:
        model = AppDocument
        fields = ('key', 'title', 'content')
        widgets = {
            'content': forms.Textarea(attrs={'rows': 30, 'style': 'font-family:monospace;font-size:0.85em;'}),
        }


@admin.register(AppDocument)
class AppDocumentAdmin(admin.ModelAdmin):
    form = AppDocumentForm
    list_display = ('title', 'key', 'content_preview', 'updated_at')
    search_fields = ('key', 'title')
    ordering = ('key',)
    readonly_fields = ('updated_at',)

    @admin.display(description='Inhoud')
    def content_preview(self, obj):
        text = (obj.content or '').strip()[:100]
        if len(obj.content or '') > 100:
            text += '…'
        return text

    def save_model(self, request, obj, form, change):
        upload = request.FILES.get('upload_file')
        if upload:
            try:
                obj.content = upload.read().decode('utf-8')
                messages.success(request, f'Inhoud geladen uit "{upload.name}" ({len(obj.content)} tekens).')
            except Exception as exc:
                messages.error(request, f'Kon bestand niet lezen: {exc}')
        super().save_model(request, obj, form, change)
        # Invalidate cache so reply generator picks up new content immediately
        from django.core.cache import cache
        cache.delete(f'appdoc:{obj.key}')
