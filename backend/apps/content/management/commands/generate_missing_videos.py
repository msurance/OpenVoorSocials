import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.content.models import SocialPost
from apps.content.services.video_generator import generate_video

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate videos for approved/published posts that have an image but no video'

    def add_arguments(self, parser):
        parser.add_argument('--week', type=int)
        parser.add_argument('--year', type=int)
        parser.add_argument('--all', action='store_true', help='Include draft posts too')

    def handle(self, *args, **options):
        qs = SocialPost.objects.exclude(image_path='')
        if not options['all']:
            qs = qs.filter(status__in=('approved', 'published'))
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

        self.stdout.write(f'Generating videos for {len(missing)} posts...')
        for post in missing:
            try:
                relative_path = generate_video(
                    str(post.id), post.image_path, post.category, post.week_number, post.year
                )
                post.video_path = relative_path
                post.save(update_fields=['video_path'])
                self.stdout.write(self.style.SUCCESS(f'  [OK] {post}'))
            except Exception as e:
                logger.error('Video generation failed for %s: %s', post.id, e)
                self.stdout.write(self.style.ERROR(f'  [FAIL] {post}: {e}'))

        self.stdout.write(self.style.SUCCESS('Done.'))
