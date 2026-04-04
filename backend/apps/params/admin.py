from django.contrib import admin
from apps.params.models import AppParameter


@admin.register(AppParameter)
class AppParameterAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description', 'updated_at')
    search_fields = ('key', 'description')
    ordering = ('key',)
