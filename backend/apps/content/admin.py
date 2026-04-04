import logging

from django.contrib import admin, messages
from django.utils.html import format_html

from apps.content.models import SocialPost

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status badge colours
# ---------------------------------------------------------------------------

_STATUS_COLOURS = {
    'draft': '#6c757d',
    'approved': '#0d6efd',
    'published': '#198754',
    'failed': '#dc3545',
    'rejected': '#fd7e14',
}

_CATEGORY_COLOURS = {
    'love': '#e83e8c',
    'friends': '#0dcaf0',
    'travel': '#20c997',
    'sports': '#fd7e14',
    'parents': '#6f42c1',
    'klusjes': '#ffc107',
    'all': '#6c757d',
}


@admin.register(SocialPost)
class SocialPostAdmin(admin.ModelAdmin):
    list_display = (
        'category_badge',
        'copy_preview',
        'image_thumbnail',
        'scheduled_at',
        'status_badge',
        'platform',
    )
    list_filter = ('status', 'category', 'platform', 'week_number')
    search_fields = ('copy_nl', 'hashtags')
    ordering = ('scheduled_at',)
    readonly_fields = (
        'id',
        'image_preview',
        'created_at',
        'published_at',
        'facebook_post_id',
        'instagram_post_id',
        'error_message',
    )
    fieldsets = (
        ('Content', {
            'fields': ('category', 'platform', 'status', 'copy_nl', 'hashtags'),
        }),
        ('Image', {
            'fields': ('image_prompt', 'image_path', 'image_preview'),
        }),
        ('Scheduling', {
            'fields': ('scheduled_at', 'week_number', 'year'),
        }),
        ('Publishing results', {
            'fields': (
                'published_at',
                'facebook_post_id',
                'instagram_post_id',
                'error_message',
            ),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',),
        }),
    )
    actions = ['approve_posts', 'reject_posts', 'publish_now', 'generate_images']

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @admin.display(description='Categorie', ordering='category')
    def category_badge(self, obj):
        colour = _CATEGORY_COLOURS.get(obj.category, '#6c757d')
        return format_html(
            '<span style="'
            'background:{colour};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:0.8em;font-weight:600;">'
            '{label}</span>',
            colour=colour,
            label=obj.get_category_display(),
        )

    @admin.display(description='Post tekst')
    def copy_preview(self, obj):
        text = obj.copy_nl[:80]
        if len(obj.copy_nl) > 80:
            text += '…'
        return text

    @admin.display(description='Afbeelding')
    def image_thumbnail(self, obj):
        if not obj.image_url:
            return '—'
        return format_html(
            '<img src="{url}" style="max-height:60px;border-radius:4px;" />',
            url=obj.image_url,
        )

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        colour = _STATUS_COLOURS.get(obj.status, '#6c757d')
        return format_html(
            '<span style="'
            'background:{colour};color:#fff;padding:2px 8px;'
            'border-radius:4px;font-size:0.8em;font-weight:600;">'
            '{label}</span>',
            colour=colour,
            label=obj.get_status_display(),
        )

    @admin.display(description='Afbeelding (groot)')
    def image_preview(self, obj):
        if not obj.image_url:
            return '—'
        return format_html(
            '<img src="{url}" style="max-width:400px;border-radius:8px;" />',
            url=obj.image_url,
        )

    # ------------------------------------------------------------------
    # Admin actions
    # ------------------------------------------------------------------

    @admin.action(description='Afbeelding genereren')
    def generate_images(self, request, queryset):
        from pathlib import Path
        from django.conf import settings
        from apps.content.services.image_generator import generate_image

        success_count = 0
        skip_count = 0
        fail_count = 0

        for post in queryset:
            if not post.image_prompt:
                skip_count += 1
                continue
            if post.image_path:
                abs_path = Path(settings.MEDIA_ROOT) / post.image_path
                if abs_path.exists():
                    skip_count += 1
                    continue
            try:
                relative_path = generate_image(
                    str(post.id), post.image_prompt, post.week_number, post.year, post.category
                )
                post.image_path = relative_path
                post.save(update_fields=['image_path'])
                success_count += 1
            except Exception as exc:
                logger.error('Admin generate_images failed for %s: %s', post.id, exc)
                self.message_user(request, f'Post {post.id} mislukt: {exc}', messages.ERROR)
                fail_count += 1

        if success_count:
            self.message_user(request, f'{success_count} afbeelding(en) gegenereerd.', messages.SUCCESS)
        if skip_count:
            self.message_user(request, f'{skip_count} post(s) overgeslagen (al een afbeelding of geen prompt).', messages.WARNING)

    @admin.action(description='Goedkeuren')
    def approve_posts(self, request, queryset):
        updated = queryset.exclude(status='published').update(status='approved')
        self.message_user(request, f'{updated} post(s) goedgekeurd.', messages.SUCCESS)

    @admin.action(description='Afwijzen')
    def reject_posts(self, request, queryset):
        updated = queryset.exclude(status='published').update(status='rejected')
        self.message_user(request, f'{updated} post(s) afgewezen.', messages.WARNING)

    @admin.action(description='Nu publiceren')
    def publish_now(self, request, queryset):
        from django.utils import timezone

        from apps.publishing.services.facebook_publisher import publish_to_facebook
        from apps.publishing.services.instagram_publisher import publish_to_instagram

        now = timezone.now()
        success_count = 0
        fail_count = 0

        for post in queryset:
            errors = []

            if post.platform in ('facebook', 'both'):
                try:
                    fb_id = publish_to_facebook(post)
                    post.facebook_post_id = fb_id
                except Exception as exc:
                    logger.error(f"Admin publish_now Facebook failed for {post.id}: {exc}")
                    errors.append(f"Facebook: {exc}")

            if post.platform in ('instagram', 'both'):
                try:
                    ig_id = publish_to_instagram(post)
                    post.instagram_post_id = ig_id
                except Exception as exc:
                    logger.error(f"Admin publish_now Instagram failed for {post.id}: {exc}")
                    errors.append(f"Instagram: {exc}")

            if errors:
                post.status = 'failed'
                post.error_message = '\n'.join(errors)
                post.save(update_fields=[
                    'status', 'error_message',
                    'facebook_post_id', 'instagram_post_id',
                ])
                self.message_user(
                    request,
                    f'Post {post.id} mislukt: {"; ".join(errors)}',
                    messages.ERROR,
                )
                fail_count += 1
            else:
                post.status = 'published'
                post.published_at = now
                post.error_message = ''
                post.save(update_fields=[
                    'status', 'published_at', 'error_message',
                    'facebook_post_id', 'instagram_post_id',
                ])
                success_count += 1

        if success_count:
            self.message_user(
                request,
                f'{success_count} post(s) succesvol gepubliceerd.',
                messages.SUCCESS,
            )
        if fail_count:
            self.message_user(
                request,
                f'{fail_count} post(s) mislukt. Zie details hierboven.',
                messages.ERROR,
            )
