import logging
import os
from pathlib import Path

from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.urls import path
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
        'cta_badge',
        'publish_status',
    )
    list_filter = ('status', 'category', 'platform', 'week_number', 'discount_cta')
    search_fields = ('copy_nl', 'hashtags')
    ordering = ('scheduled_at',)
    readonly_fields = (
        'id',
        'image_preview',
        'video_preview',
        'publish_status_detail',
        'created_at',
        'published_at',
        'facebook_post_id',
        'facebook_reel_id',
        'instagram_post_id',
        'instagram_reel_id',
        'error_message',
    )
    fieldsets = (
        ('Content', {
            'fields': ('category', 'platform', 'status', 'copy_nl', 'hashtags', 'discount_cta'),
        }),
        ('Image', {
            'fields': ('image_prompt', 'image_path', 'image_preview', 'video_path', 'video_preview'),
        }),
        ('Scheduling', {
            'fields': ('scheduled_at', 'week_number', 'year'),
        }),
        ('Publishing results', {
            'fields': (
                'publish_status_detail',
                'published_at',
                'facebook_post_id',
                'facebook_reel_id',
                'instagram_post_id',
                'instagram_reel_id',
                'error_message',
            ),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',),
        }),
    )
    actions = ['approve_posts', 'reject_posts', 'publish_now', 'generate_images', 'regenerate_images', 'generate_video']
    change_list_template = 'admin/content/socialpost/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path('generate-content/', self.admin_site.admin_view(self.generate_content_view), name='content_socialpost_generate'),
            path('generation-status/', self.admin_site.admin_view(self.generation_status_view), name='content_socialpost_generation_status'),
        ]
        return extra + urls

    def generation_status_view(self, request):
        from django.http import JsonResponse
        from pathlib import Path
        pending_images = sum(
            1 for p in SocialPost.objects.exclude(image_prompt='')
            if not p.image_path or not (Path(settings.MEDIA_ROOT) / p.image_path).exists()
        )
        pending_videos = sum(
            1 for p in SocialPost.objects.exclude(image_path='').filter(status__in=('draft', 'approved', 'published'))
            if not p.video_path or not (Path(settings.MEDIA_ROOT) / p.video_path).exists()
        )
        return JsonResponse({'pending_images': pending_images, 'pending_videos': pending_videos})

    def changelist_view(self, request, extra_context=None):
        from pathlib import Path
        pending_images = sum(
            1 for p in SocialPost.objects.exclude(image_prompt='')
            if not p.image_path or not (Path(settings.MEDIA_ROOT) / p.image_path).exists()
        )
        pending_videos = sum(
            1 for p in SocialPost.objects.exclude(image_path='').filter(status__in=('draft', 'approved', 'published'))
            if not p.video_path or not (Path(settings.MEDIA_ROOT) / p.video_path).exists()
        )
        extra_context = extra_context or {}
        extra_context['pending_images'] = pending_images
        extra_context['pending_videos'] = pending_videos
        return super().changelist_view(request, extra_context=extra_context)

    def generate_content_view(self, request):
        from django.utils import timezone
        from apps.content.management.commands.generate_weekly_content import Command
        try:
            # Find the first upcoming week that has no posts yet
            now = timezone.now()
            week_number = None
            year = None
            for offset in range(1, 8):
                candidate = now + timezone.timedelta(weeks=offset)
                iso = candidate.isocalendar()
                w, y = iso[1], iso[0]
                if not SocialPost.objects.filter(week_number=w, year=y).exists():
                    week_number, year = w, y
                    break
            if week_number is None:
                self.message_user(request, 'De komende 7 weken hebben al posts.', messages.WARNING)
                return HttpResponseRedirect('../')
            Command().handle(week=week_number, year=year)
            # Fire image + video generation in background threads
            import threading, django.db
            def _generate_media():
                django.db.connections.close_all()
                from apps.content.management.commands.generate_missing_images import Command as ImgCmd
                from apps.content.management.commands.generate_missing_videos import Command as VidCmd
                try:
                    ImgCmd().handle(week=week_number, year=year, workers=4)
                except Exception as e:
                    logger.error('Background image generation failed: %s', e)
                try:
                    VidCmd().handle(week=week_number, year=year, all=True, workers=3)
                except Exception as e:
                    logger.error('Background video generation failed: %s', e)
            threading.Thread(target=_generate_media, daemon=True).start()
            self.message_user(
                request,
                f'Week {week_number}/{year}: {SocialPost.objects.filter(week_number=week_number, year=year).count()} posts aangemaakt. '
                'Afbeeldingen en video\'s worden op de achtergrond gegenereerd (~10 min). Ververs de pagina om de voortgang te zien.',
                messages.SUCCESS,
            )
        except Exception as exc:
            logger.error('Admin generate_content_view failed: %s', exc)
            self.message_user(request, f'Genereren mislukt: {exc}', messages.ERROR)
        return HttpResponseRedirect('../')

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
            url=self._versioned_url_for(obj.image_url, obj.image_path),
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

    @admin.display(description='CTA')
    def cta_badge(self, obj):
        if obj.discount_cta:
            return format_html(
                '<span style="background:#198754;color:#fff;padding:2px 6px;'
                'border-radius:4px;font-size:0.8em;font-weight:600">CTA</span>'
            )
        return '—'

    @admin.display(description='Afbeelding (groot)')
    def image_preview(self, obj):
        if not obj.image_url:
            return '—'
        return format_html(
            '<img src="{url}" style="max-width:400px;border-radius:8px;" />',
            url=self._versioned_url_for(obj.image_url, obj.image_path),
        )

    @admin.display(description='Video')
    def video_preview(self, obj):
        if not obj.video_url:
            return '—'
        return format_html(
            '<video src="{url}" style="max-width:400px;border-radius:8px;" controls></video>',
            url=self._versioned_url_for(obj.video_url, obj.video_path),
        )

    @admin.display(description='Publicatie')
    def publish_status(self, obj):
        if obj.status not in ('published', 'failed'):
            return '—'
        checks = [
            ('FB post', obj.facebook_post_id),
            ('FB reel', obj.facebook_reel_id),
            ('IG post', obj.instagram_post_id),
            ('IG reel', obj.instagram_reel_id),
        ]
        parts = []
        for label, value in checks:
            if value:
                parts.append(
                    f'<span style="color:#198754;font-weight:600" title="{value}">✓ {label}</span>'
                )
            else:
                parts.append(
                    f'<span style="color:#dc3545" title="niet gepubliceerd">✗ {label}</span>'
                )
        return format_html(' &nbsp; '.join(parts))

    @admin.display(description='Publicatiestatus')
    def publish_status_detail(self, obj):
        if obj.status not in ('published', 'failed'):
            return '—'
        rows = [
            ('Facebook post', obj.facebook_post_id, f'https://facebook.com/{obj.facebook_post_id}' if obj.facebook_post_id else None),
            ('Facebook reel', obj.facebook_reel_id, None),
            ('Instagram post', obj.instagram_post_id, None),
            ('Instagram reel', obj.instagram_reel_id, None),
        ]
        html = '<table style="border-collapse:collapse;width:100%">'
        for label, value, link in rows:
            if value:
                cell = f'<a href="{link}" target="_blank">{value}</a>' if link else value
                icon = '<span style="color:#198754;font-weight:700">✓</span>'
            else:
                cell = '<em style="color:#6c757d">niet gepubliceerd</em>'
                icon = '<span style="color:#dc3545;font-weight:700">✗</span>'
            html += (
                f'<tr><td style="padding:3px 8px">{icon}</td>'
                f'<td style="padding:3px 8px;font-weight:600">{label}</td>'
                f'<td style="padding:3px 8px">{cell}</td></tr>'
            )
        html += '</table>'
        if obj.error_message:
            html += f'<p style="color:#dc3545;margin-top:8px"><strong>Fout:</strong> {obj.error_message}</p>'
        return format_html(html)

    def _versioned_url(self, obj):
        """Append file mtime as cache-buster so regenerated images always reload."""
        return self._versioned_url_for(obj.image_url, obj.image_path)

    def _versioned_url_for(self, url, path):
        """Append file mtime as cache-buster for any media file."""
        if path:
            try:
                abs_path = Path(settings.MEDIA_ROOT) / path
                mtime = int(os.path.getmtime(abs_path))
                return f"{url}?v={mtime}"
            except OSError:
                pass
        return url

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

    @admin.action(description='Afbeelding overschrijven (opnieuw genereren)')
    def regenerate_images(self, request, queryset):
        from apps.content.services.image_generator import generate_image

        success_count = 0
        fail_count = 0

        for post in queryset:
            if not post.image_prompt:
                self.message_user(request, f'Post {post.id} overgeslagen: geen prompt.', messages.WARNING)
                continue
            try:
                relative_path = generate_image(
                    str(post.id), post.image_prompt, post.week_number, post.year, post.category
                )
                post.image_path = relative_path
                post.save(update_fields=['image_path'])
                success_count += 1
            except Exception as exc:
                logger.error('Admin regenerate_images failed for %s: %s', post.id, exc)
                self.message_user(request, f'Post {post.id} mislukt: {exc}', messages.ERROR)
                fail_count += 1

        if success_count:
            self.message_user(request, f'{success_count} afbeelding(en) opnieuw gegenereerd.', messages.SUCCESS)

    @admin.action(description='Video genereren (Kling AI — async)')
    def generate_video(self, request, queryset):
        import threading
        from apps.content.services.video_generator import generate_video as gen_video
        import django.db

        posts = [(str(p.id), p.image_path, p.category, p.week_number, p.year)
                 for p in queryset if p.image_path]
        skipped = queryset.count() - len(posts)

        if not posts:
            self.message_user(request, 'Geen posts met afbeelding geselecteerd.', messages.WARNING)
            return

        def _run(post_args):
            # Close any inherited DB connection — thread needs its own
            django.db.connections.close_all()
            post_id, image_path, category, week_number, year = post_args
            try:
                relative_path = gen_video(post_id, image_path, category, week_number, year)
                SocialPost.objects.filter(id=post_id).update(video_path=relative_path)
                logger.info("Background video done: %s → %s", post_id, relative_path)
            except Exception as exc:
                logger.error("Background video FAILED for %s: %s", post_id, exc)

        for post_args in posts:
            t = threading.Thread(target=_run, args=(post_args,), daemon=True)
            t.start()

        msg = f'{len(posts)} video(s) worden op de achtergrond gegenereerd (~90s per video). Ververs de pagina om het resultaat te zien.'
        if skipped:
            msg += f' {skipped} overgeslagen (geen afbeelding).'
        self.message_user(request, msg, messages.SUCCESS)

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
                    result = publish_to_facebook(post)
                    # publish_to_facebook returns "post_id" or "post_id,reel_id"
                    parts = (result or '').split(',')
                    post.facebook_post_id = parts[0] if len(parts) > 0 else ''
                    post.facebook_reel_id = parts[1] if len(parts) > 1 else ''
                except Exception as exc:
                    logger.error(f"Admin publish_now Facebook failed for {post.id}: {exc}")
                    errors.append(f"Facebook: {exc}")

            if post.platform in ('instagram', 'both'):
                try:
                    result = publish_to_instagram(post)
                    # publish_to_instagram returns "image_id" or "image_id,reel_id"
                    parts = (result or '').split(',')
                    post.instagram_post_id = parts[0] if len(parts) > 0 else ''
                    post.instagram_reel_id = parts[1] if len(parts) > 1 else ''
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
                    'facebook_post_id', 'facebook_reel_id',
                    'instagram_post_id', 'instagram_reel_id',
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
