import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import django.db
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.content.models import SocialPost
from apps.content.services.video_generator import generate_video

logger = logging.getLogger(__name__)

_MAX_WORKERS = 3  # Kling AI rate-limit safety


class Command(BaseCommand):
    help = 'Generate videos (in parallel) for posts that have an image but no video'

    def add_arguments(self, parser):
        parser.add_argument('--week', type=int)
        parser.add_argument('--year', type=int)
        parser.add_argument('--all', action='store_true', help='Include draft posts too')
        parser.add_argument('--workers', type=int, default=_MAX_WORKERS)

    def handle(self, *args, **options):
        qs = SocialPost.objects.exclude(image_path='')
        if not options['all']:
            qs = qs.filter(status__in=('approved', 'published', 'draft'))
        if options['week']:
            qs = qs.filter(week_number=options['week'])
        if options['year']:
            qs = qs.filter(year=options['year'])

        missing = [
            p for p in qs
            if not p.video_path or not (Path(settings.MEDIA_ROOT) / p.video_path).exists()
        ]

        if not missing:
            self.stdout.write(self.style.SUCCESS('All eligible posts already have videos.'))
            return

        workers = options['workers']
        self.stdout.write(f'Generating videos for {len(missing)} posts (workers={workers})...')

        def _generate(post):
            django.db.connections.close_all()
            try:
                relative_path = generate_video(
                    str(post.id), post.image_path, post.category, post.week_number, post.year
                )
                SocialPost.objects.filter(id=post.id).update(video_path=relative_path)
                return post.id, None
            except Exception as exc:
                logger.error('Video generation failed for %s: %s', post.id, exc)
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
