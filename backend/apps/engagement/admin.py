from django.contrib import admin
from apps.engagement.models import EngagementReply


@admin.register(EngagementReply)
class EngagementReplyAdmin(admin.ModelAdmin):
    list_display = ('platform', 'user_name', 'discount_code', 'replied_at', 'success')
    list_filter = ('platform', 'success')
    ordering = ('-replied_at',)
    readonly_fields = (
        'id', 'comment_id', 'platform', 'user_id', 'user_name',
        'post_id', 'discount_code', 'replied_at', 'success', 'error',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
