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
        'boost_badge',
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
        'boost_campaign_id',
        'boost_ad_set_id',
        'boost_ad_id',
        'boost_reach',
        'boost_spend_eur',
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
        ('Boost / Advertentie', {
            'fields': (
                'boost_status',
                'boost_daily_budget_eur',
                'boost_end_date',
                'boost_reach',
                'boost_spend_eur',
                'boost_campaign_id',
                'boost_ad_set_id',
                'boost_ad_id',
            ),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',),
        }),
    )
    actions = ['approve_posts', 'reject_posts', 'publish_now', 'unpublish_posts', 'generate_images', 'regenerate_images', 'generate_video', 'boost_post_action', 'refresh_boost_metrics']
    change_list_template = 'admin/content/socialpost/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        extra = [
            path('generate-content/', self.admin_site.admin_view(self.generate_content_view), name='content_socialpost_generate'),
            path('generation-status/', self.admin_site.admin_view(self.generation_status_view), name='content_socialpost_generation_status'),
            path('resume-generation/', self.admin_site.admin_view(self.resume_generation_view), name='content_socialpost_resume_generation'),
            path('boost-post/', self.admin_site.admin_view(self.boost_post_view), name='content_socialpost_boost'),
            path('generate-from-date/', self.admin_site.admin_view(self.generate_from_date_view), name='content_socialpost_generate_from_date'),
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

    def resume_generation_view(self, request):
        import threading
        import django.db
        from apps.content.management.commands.generate_missing_images import Command as ImgCmd
        from apps.content.management.commands.generate_missing_videos import Command as VidCmd

        def _run():
            django.db.connections.close_all()
            try:
                ImgCmd().handle(week=None, year=None, workers=4)
            except Exception as e:
                logger.error('Resume image generation failed: %s', e)
            try:
                VidCmd().handle(week=None, year=None, all=True, workers=3)
            except Exception as e:
                logger.error('Resume video generation failed: %s', e)

        threading.Thread(target=_run, daemon=False).start()
        self.message_user(request, 'Generatie hervat — afbeeldingen en video\'s worden opnieuw opgestart op de achtergrond.', messages.SUCCESS)
        return HttpResponseRedirect('../')

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
            threading.Thread(target=_generate_media, daemon=False).start()
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

    def generate_from_date_view(self, request):
        """Form to pick a specific start date, then generate content for that ISO week."""
        from django.http import HttpResponse
        from django.utils.safestring import mark_safe
        import datetime

        all_categories = ['love', 'friends', 'travel', 'sports', 'parents']

        if request.method == 'POST':
            date_str = request.POST.get('start_date', '')
            post_count = int(request.POST.get('post_count', 12))
            selected_cats = request.POST.getlist('categories') or all_categories
            # Only keep valid values
            selected_cats = [c for c in selected_cats if c in all_categories]
            if not selected_cats:
                selected_cats = all_categories

            try:
                start_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                self.message_user(request, 'Ongeldige datum.', messages.ERROR)
                return HttpResponseRedirect('')

            iso = start_date.isocalendar()
            week_number, year = iso[1], iso[0]

            import threading, django.db

            def _generate(wn, yr, cnt, cats):
                django.db.connections.close_all()
                try:
                    from apps.content.management.commands.generate_weekly_content import Command
                    from apps.content.management.commands.generate_missing_images import Command as ImgCmd
                    from apps.content.management.commands.generate_missing_videos import Command as VidCmd
                    Command().handle(week=wn, year=yr, count=cnt, categories=cats, force=True)
                    try:
                        ImgCmd().handle(week=wn, year=yr, workers=4)
                    except Exception as e:
                        logger.error('Background image generation failed: %s', e)
                    try:
                        VidCmd().handle(week=wn, year=yr, all=True, workers=3)
                    except Exception as e:
                        logger.error('Background video generation failed: %s', e)
                    logger.info('generate_from_date finished: week %d/%d, %d posts, cats=%s', wn, yr, cnt, cats)
                except Exception as exc:
                    logger.error('generate_from_date_view background thread failed: %s', exc)

            threading.Thread(target=_generate, args=(week_number, year, post_count, selected_cats), daemon=False).start()
            cat_labels = ', '.join(selected_cats)
            self.message_user(
                request,
                f'Week {week_number}/{year} (vanaf {start_date:%d/%m/%Y}): {post_count} posts [{cat_labels}] worden op de achtergrond gegenereerd (~1 min). '
                'Ververs de pagina om de voortgang te zien.',
                messages.SUCCESS,
            )

            return HttpResponseRedirect('../')

        # Default start_date = next Monday
        today = datetime.date.today()
        next_monday = today + datetime.timedelta(days=(7 - today.weekday()))
        cat_labels = {'love': 'Liefde', 'friends': 'Vrienden', 'travel': 'Reizen', 'sports': 'Sport', 'parents': 'Ouders'}
        cat_colours = {'love': '#e83e8c', 'friends': '#0dcaf0', 'travel': '#20c997', 'sports': '#fd7e14', 'parents': '#6f42c1'}
        checkboxes = ''.join(
            f'<label style="display:inline-flex;align-items:center;gap:6px;margin:4px 8px 4px 0;cursor:pointer">'
            f'<input type="checkbox" name="categories" value="{cat}" checked '
            f'style="width:16px;height:16px;accent-color:{cat_colours[cat]}">'
            f'<span style="background:{cat_colours[cat]};color:#fff;padding:2px 10px;border-radius:4px;font-size:0.85em;font-weight:600">'
            f'{cat_labels[cat]}</span></label>'
            for cat in all_categories
        )
        form_html = f"""
        <div style="max-width:520px;margin:40px auto;font-family:sans-serif">
          <h2>Weekplanning genereren vanaf datum</h2>
          <p style="color:#555">
            Kies de startdatum, categorieën en aantal posts. Posts worden verdeeld over die week
            op de vaste tijdstippen (ma–zo, 10:00 en 19:00).
          </p>
          <form method="post">
            <input type="hidden" name="csrfmiddlewaretoken" value="{request.META.get('CSRF_COOKIE', '')}">
            <p>
              <label style="font-weight:600">Startdatum van de week:</label><br>
              <input type="date" name="start_date" value="{next_monday.isoformat()}"
                     style="margin-top:6px;padding:6px 10px;font-size:1em;border:1px solid #ccc;border-radius:4px">
              <span id="week-label" style="margin-left:12px;color:#555;font-size:0.9em"></span>
            </p>
            <p>
              <label style="font-weight:600">Categorieën:</label><br>
              <span style="display:flex;flex-wrap:wrap;margin-top:6px">{checkboxes}</span>
            </p>
            <p>
              <label style="font-weight:600">Aantal posts:</label><br>
              <input type="number" name="post_count" value="12" min="1" max="12"
                     style="margin-top:6px;padding:6px 10px;font-size:1em;border:1px solid #ccc;border-radius:4px;width:80px">
              <span style="color:#888;font-size:0.9em;margin-left:8px">max. 12</span>
            </p>
            <button type="submit"
                    style="background:#0d6efd;color:#fff;border:none;padding:8px 22px;
                           border-radius:4px;cursor:pointer;font-size:1em;font-weight:600">
              ✦ Genereer weekplanning
            </button>
            &nbsp;
            <a href="../" style="color:#6c757d">Annuleren</a>
          </form>
        </div>
        <script>
          function updateWeekLabel() {{
            var d = new Date(document.querySelector('[name=start_date]').value);
            if (isNaN(d)) return;
            // ISO week calculation
            var jan4 = new Date(d.getFullYear(), 0, 4);
            var startOfWeek1 = new Date(jan4);
            startOfWeek1.setDate(jan4.getDate() - ((jan4.getDay() + 6) % 7));
            var week = Math.round((d - startOfWeek1) / (7 * 86400000)) + 1;
            document.getElementById('week-label').textContent = '→ Week ' + week + ' / ' + d.getFullYear();
          }}
          document.querySelector('[name=start_date]').addEventListener('change', updateWeekLabel);
          updateWeekLabel();
        </script>
        """
        from django.http import HttpResponse
        from django.utils.safestring import mark_safe
        return HttpResponse(mark_safe(form_html))

    def boost_post_view(self, request):
        """Intermediate form: collect budget + duration, then fire async boost."""
        from django.http import HttpResponse
        from django.utils.safestring import mark_safe

        post_ids = request.POST.getlist('post_ids') or request.GET.getlist('post_ids')

        if request.method == 'POST' and 'confirm' in request.POST:
            import threading
            import django.db
            from apps.publishing.services.facebook_booster import boost_post as do_boost

            daily_budget = float(request.POST.get('daily_budget', 5))
            days = int(request.POST.get('days', 7))

            def _boost(ids, budget, duration):
                django.db.connections.close_all()
                from datetime import date, timedelta
                for post_id in ids:
                    try:
                        post = SocialPost.objects.get(id=post_id)
                        result = do_boost(post, daily_budget_eur=budget, days=duration)
                        post.boost_status = 'active'
                        post.boost_campaign_id = result['campaign_id']
                        post.boost_ad_set_id = result['adset_id']
                        post.boost_ad_id = result['ad_id']
                        post.boost_daily_budget_eur = budget
                        post.boost_end_date = date.today() + timedelta(days=duration)
                        post.save(update_fields=[
                            'boost_status', 'boost_campaign_id', 'boost_ad_set_id',
                            'boost_ad_id', 'boost_daily_budget_eur', 'boost_end_date',
                        ])
                        logger.info("Boost started for post %s — campaign %s", post_id, result['campaign_id'])
                    except Exception as exc:
                        logger.error("Boost failed for post %s: %s", post_id, exc)
                        SocialPost.objects.filter(id=post_id).update(boost_status='failed')

            threading.Thread(target=_boost, args=(post_ids, daily_budget, days), daemon=False).start()
            self.message_user(
                request,
                f'{len(post_ids)} post(s) worden op de achtergrond geboost (€{daily_budget}/dag × {days} dagen). '
                'Ververs de pagina om de boost-status te zien.',
                messages.SUCCESS,
            )
            return HttpResponseRedirect('../')

        # Show confirmation form
        posts = SocialPost.objects.filter(id__in=post_ids)
        post_list = ''.join(
            f'<li>{p.get_category_display()} — {p.scheduled_at:%d/%m/%Y} — {p.copy_nl[:60]}…</li>'
            for p in posts
        )
        hidden_ids = ''.join(f'<input type="hidden" name="post_ids" value="{pid}">' for pid in post_ids)
        form_html = f"""
        <div style="max-width:600px;margin:30px auto;font-family:sans-serif">
          <h2>Post(s) boostten</h2>
          <p>Targeting: <strong>Brugge + 10 km, leeftijd 25–65</strong></p>
          <ul>{post_list}</ul>
          <form method="post">
            <input type="hidden" name="csrfmiddlewaretoken" value="{request.META.get('CSRF_COOKIE', '')}">
            {hidden_ids}
            <input type="hidden" name="confirm" value="1">
            <p>
              <label><strong>Dagelijks budget (€):</strong></label><br>
              <input type="number" name="daily_budget" value="5" min="1" max="100" step="0.5"
                     style="width:100px;padding:4px;margin-top:4px">
            </p>
            <p>
              <label><strong>Duur (dagen):</strong></label><br>
              <input type="number" name="days" value="7" min="1" max="30"
                     style="width:100px;padding:4px;margin-top:4px">
            </p>
            <p style="color:#666;font-size:0.9em">
              Totaal budget: <span id="total">€35.00</span>
            </p>
            <button type="submit"
                    style="background:#198754;color:#fff;border:none;padding:8px 20px;
                           border-radius:4px;cursor:pointer;font-size:1em">
              ✓ Boost starten
            </button>
            &nbsp;
            <a href="../" style="color:#6c757d">Annuleren</a>
          </form>
        </div>
        <script>
          function upd(){{
            var b=parseFloat(document.querySelector('[name=daily_budget]').value)||0;
            var d=parseInt(document.querySelector('[name=days]').value)||0;
            document.getElementById('total').textContent='€'+(b*d).toFixed(2);
          }}
          document.querySelector('[name=daily_budget]').addEventListener('input',upd);
          document.querySelector('[name=days]').addEventListener('input',upd);
        </script>
        """
        return HttpResponse(mark_safe(form_html))

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

    @admin.display(description='Boost')
    def boost_badge(self, obj):
        status = obj.boost_status
        if not status:
            return '—'
        colours = {'active': '#198754', 'completed': '#6c757d', 'failed': '#dc3545'}
        labels = {'active': '▶ Actief', 'completed': '✓ Klaar', 'failed': '✗ Mislukt'}
        colour = colours.get(status, '#6c757d')
        label = labels.get(status, status)
        tip = ''
        if obj.boost_spend_eur is not None:
            tip = f'€{obj.boost_spend_eur} uitgegeven, {obj.boost_reach or 0} bereik'
        return format_html(
            '<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;'
            'font-size:0.8em;font-weight:600" title="{tip}">{label}</span>',
            c=colour, tip=tip, label=label,
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
            t = threading.Thread(target=_run, args=(post_args,), daemon=False)
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
        import threading
        import django.db
        from apps.publishing.services.facebook_publisher import publish_to_facebook
        from apps.publishing.services.instagram_publisher import publish_to_instagram

        post_ids = list(queryset.values_list('id', flat=True))
        if not post_ids:
            return

        def _publish(ids):
            django.db.connections.close_all()
            from django.utils import timezone
            from django.db import transaction
            for post_id in ids:
                # Use select_for_update to prevent race with the cron publisher
                with transaction.atomic():
                    post = (
                        SocialPost.objects.select_for_update(skip_locked=True)
                        .filter(id=post_id, status__in=['draft', 'approved'])
                        .first()
                    )
                    if post is None:
                        logger.info("Post %s already published or locked — skipping", post_id)
                        continue
                    # Mark as published immediately inside the lock so cron can't grab it
                    post.status = 'published'
                    post.save(update_fields=['status'])

                errors = []

                if post.platform in ('facebook', 'both'):
                    try:
                        result = publish_to_facebook(post)
                        parts = (result or '').split(',')
                        post.facebook_post_id = parts[0] if len(parts) > 0 else ''
                        post.facebook_reel_id = parts[1] if len(parts) > 1 else ''
                    except Exception as exc:
                        logger.error("Async publish_now Facebook failed for %s: %s", post_id, exc)
                        errors.append(f"Facebook: {exc}")

                if post.platform in ('instagram', 'both'):
                    try:
                        result = publish_to_instagram(post)
                        parts = (result or '').split(',')
                        post.instagram_post_id = parts[0] if len(parts) > 0 else ''
                        post.instagram_reel_id = parts[1] if len(parts) > 1 else ''
                    except Exception as exc:
                        logger.error("Async publish_now Instagram failed for %s: %s", post_id, exc)
                        errors.append(f"Instagram: {exc}")

                if errors:
                    post.status = 'failed'
                    post.error_message = '\n'.join(errors)
                    logger.error("Post %s publication failed: %s", post_id, errors)
                else:
                    post.published_at = timezone.now()
                    post.error_message = ''
                    logger.info("Post %s published successfully", post_id)

                post.save(update_fields=[
                    'status', 'published_at', 'error_message',
                    'facebook_post_id', 'facebook_reel_id',
                    'instagram_post_id', 'instagram_reel_id',
                ])

        threading.Thread(target=_publish, args=(post_ids,), daemon=False).start()
        self.message_user(
            request,
            f'{len(post_ids)} post(s) worden op de achtergrond gepubliceerd. Ververs de pagina om de status te zien.',
            messages.SUCCESS,
        )

    @admin.action(description='Verwijderen van platforms (unpublish)')
    def unpublish_posts(self, request, queryset):
        from apps.publishing.services.unpublisher import unpublish_post

        published = queryset.filter(status='published')
        skipped = queryset.exclude(status='published').count()

        if skipped:
            self.message_user(
                request,
                f'{skipped} post(s) overgeslagen — alleen gepubliceerde posts kunnen worden verwijderd.',
                messages.WARNING,
            )

        success = 0
        failed = 0
        for post in published:
            result = unpublish_post(post)
            post.status = 'draft'
            post.published_at = None
            post.facebook_post_id = ''
            post.facebook_reel_id = ''
            post.instagram_post_id = ''
            post.instagram_reel_id = ''
            post.error_message = ''
            post.save(update_fields=[
                'status', 'published_at', 'facebook_post_id', 'facebook_reel_id',
                'instagram_post_id', 'instagram_reel_id', 'error_message',
            ])
            if result['errors']:
                self.message_user(
                    request,
                    f'Post "{post.copy_nl[:40]}…" gedeeltelijk verwijderd. '
                    f'Verwijderd: {", ".join(result["deleted"]) or "geen"}. '
                    f'Fouten: {", ".join(result["errors"])}',
                    messages.WARNING,
                )
                failed += 1
            else:
                success += 1

        if success:
            self.message_user(
                request,
                f'{success} post(s) verwijderd van alle platforms en teruggezet naar concept.',
                messages.SUCCESS,
            )

    @admin.action(description='▶ Post boostten (Meta Ads)')
    def boost_post_action(self, request, queryset):
        """Redirect to boost form with selected post IDs."""
        from django.urls import reverse
        post_ids = list(queryset.filter(status='published').values_list('id', flat=True))
        not_published = queryset.exclude(status='published').count()
        if not_published:
            self.message_user(
                request,
                f'{not_published} post(s) overgeslagen — alleen gepubliceerde posts kunnen worden geboost.',
                messages.WARNING,
            )
        if not post_ids:
            return
        ids_qs = '&'.join(f'post_ids={pid}' for pid in post_ids)
        boost_url = reverse('admin:content_socialpost_boost') + f'?{ids_qs}'
        return HttpResponseRedirect(boost_url)

    @admin.action(description='↺ Boost metrics vernieuwen')
    def refresh_boost_metrics(self, request, queryset):
        from apps.publishing.services.facebook_booster import fetch_boost_metrics
        updated = 0
        failed = 0
        for post in queryset.filter(boost_campaign_id__gt=''):
            try:
                metrics = fetch_boost_metrics(post.boost_campaign_id)
                post.boost_spend_eur = metrics['spend_eur']
                post.boost_reach = metrics['reach']
                post.save(update_fields=['boost_spend_eur', 'boost_reach'])
                updated += 1
            except Exception as exc:
                logger.error("Metrics refresh failed for post %s: %s", post.id, exc)
                failed += 1
        if updated:
            self.message_user(request, f'{updated} post(s) bijgewerkt met boost metrics.', messages.SUCCESS)
        if failed:
            self.message_user(request, f'{failed} post(s) mislukt.', messages.ERROR)
        if not updated and not failed:
            self.message_user(request, 'Geen posts met actieve boost gevonden.', messages.WARNING)
