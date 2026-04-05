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

        def _generate(post):
            django.db.connections.close_all()
            try:
                relative_path = generate_image(
                    str(post.id), post.image_prompt, post.week_number, post.year, post.category
                )
                SocialPost.objects.filter(id=post.id).update(image_path=relative_path)
                return post.id, None
            except Exception as exc:
                logger.error('Image generation failed for %s: %s', post.id, exc)
                return post.id, exc

        ok = fail = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_generate, p): p for p in missing}
            for future in as_completed(futures):
                post_id, exc = future.result()
                if exc:
                    self.stdout.write(self.style.ERROR(f'  [FAIL] {post_id}: {exc}'))
                    fail += 1
                else:
                    self.stdout.write(self.style.SUCCESS(f'  [OK] {post_id}'))
                    ok += 1

        self.stdout.write(self.style.SUCCESS(f'Done. {ok} OK, {fail} failed.'))
