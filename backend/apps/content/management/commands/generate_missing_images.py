import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import django.db
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.content.models import SocialPost
from apps.content.services.image_generator import generate_image

logger = logging.getLogger(__name__)

_MAX_WORKERS = 4


class Command(BaseCommand):
    help = 'Generate images (in parallel) for posts that have an image_prompt but no image file on disk'

    def add_arguments(self, parser):
        parser.add_argument('--week', type=int, help='Limit to specific week number')
        parser.add_argument('--year', type=int, help='Limit to specific year')
        parser.add_argument('--workers', type=int, default=_MAX_WORKERS)

    def handle(self, *args, **options):
        from apps.params.models import CronLog

        qs = SocialPost.objects.exclude(image_prompt='')
        if options['week']:
            qs = qs.filter(week_number=options['week'])
        if options['year']:
            qs = qs.filter(year=options['year'])

        missing = []
        for post in qs:
            if not post.image_path:
                missing.append(post)
                continue
            abs_path = Path(settings.MEDIA_ROOT) / post.image_path
            if not abs_path.exists():
                missing.append(post)

        if not missing:
            self.stdout.write(self.style.SUCCESS('All posts already have images.'))
            return

        workers = options['workers']
        self.stdout.write(f'Generating images for {len(missing)} posts (workers={workers})...')

        quota_exhausted = False

        def _generate(post):
            django.db.connections.close_all()
            try:
                relative_path = generate_image(
                    str(post.id), post.image_prompt, post.week_number, post.year, post.category
                )
                SocialPost.objects.filter(id=post.id).update(image_path=relative_path)
                return post.id, None
            except Exception as exc:
                return post.id, exc

        ok = fail = quota_hits = 0
        notes = []

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_generate, p): p for p in missing}
            for future in as_completed(futures):
                post_id, exc = future.result()
                if exc is None:
                    self.stdout.write(self.style.SUCCESS(f'  [OK] {post_id}'))
                    ok += 1
                else:
                    err_str = str(exc)
                    if '429' in err_str or 'RESOURCE_EXHAUSTED' in err_str or 'quota' in err_str.lower():
                        quota_hits += 1
                        if not quota_exhausted:
                            quota_exhausted = True
                            msg = f'QUOTA EXHAUSTED after {ok} images — {len(missing) - ok} still pending'
                            logger.warning(msg)
                            self.stdout.write(self.style.ERROR(f'  [QUOTA] {msg}'))
                            notes.append(msg)
                            # Cancel remaining futures — no point burning more quota attempts
                            for f in futures:
                                f.cancel()
                    else:
                        logger.error('Image generation failed for %s: %s', post_id, exc)
                        self.stdout.write(self.style.ERROR(f'  [FAIL] {post_id}: {exc}'))
                        notes.append(f'FAIL {post_id}: {err_str[:120]}')
                        fail += 1

        summary = f'images: {ok} OK, {fail} failed, {quota_hits} quota-blocked, {len(missing)-ok-fail} pending'
        self.stdout.write(self.style.SUCCESS(f'Done. {summary}'))
        logger.info('generate_missing_images: %s', summary)

        CronLog.objects.create(
            posts_due=len(missing),
            posts_published=ok,
            posts_failed=fail + quota_hits,
            notes=f'[image-gen] {summary}' + (('\n' + '\n'.join(notes)) if notes else ''),
        )
