from django.contrib import admin
from django.utils.html import format_html
from apps.engagement.models import EngagementReply


@admin.register(EngagementReply)
class EngagementReplyAdmin(admin.ModelAdmin):
    list_display = ('replied_at', 'platform', 'user_name', 'reply_type_badge', 'comment_preview', 'reply_preview', 'success_badge')
    list_filter = ('platform', 'reply_type', 'success')
    search_fields = ('user_name', 'comment_text', 'reply_text', 'discount_code')
    ordering = ('-replied_at',)
    readonly_fields = (
        'id', 'comment_id', 'platform', 'reply_type', 'user_id', 'user_name',
        'post_id', 'comment_text', 'reply_text', 'discount_code',
        'replied_at', 'success', 'error',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description='Type')
    def reply_type_badge(self, obj):
        colours = {
            'discount': '#0d6efd',
            'ai_acknowledgment': '#6f42c1',
            'natural': '#198754',
        }
        colour = colours.get(obj.reply_type, '#6c757d')
        return format_html(
            '<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:0.8em;font-weight:600">{l}</span>',
            c=colour, l=obj.get_reply_type_display(),
        )

    @admin.display(description='Comment')
    def comment_preview(self, obj):
        text = obj.comment_text or '—'
        if len(text) > 60:
            text = text[:60] + '…'
        return text

    @admin.display(description='Ons antwoord')
    def reply_preview(self, obj):
        text = obj.reply_text or '—'
        if len(text) > 80:
            text = text[:80] + '…'
        return text

    @admin.display(description='OK')
    def success_badge(self, obj):
        if obj.success:
            return format_html('<span style="color:#198754;font-weight:700">✓</span>')
        return format_html('<span style="color:#dc3545;font-weight:700" title="{e}">✗</span>', e=obj.error)
