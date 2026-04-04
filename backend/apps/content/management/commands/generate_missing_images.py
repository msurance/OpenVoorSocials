import logging
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.content.models import SocialPost
from apps.content.services.image_generator import generate_image

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate images for posts that have an image_prompt but no image file on disk'

    def add_arguments(self, parser):
        parser.add_argument('--week', type=int, help='Limit to specific week number')
        parser.add_argument('--year', type=int, help='Limit to specific year')

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

        self.stdout.write(f'Generating images for {len(missing)} posts...')
        for post in missing:
            try:
                relative_path = generate_image(str(post.id), post.image_prompt, post.week_number, post.year)
                post.image_path = relative_path
                post.save(update_fields=['image_path'])
                self.stdout.write(self.style.SUCCESS(f'  [OK] {post}'))
            except Exception as e:
                logger.error('Image generation failed for %s: %s', post.id, e)
                self.stdout.write(self.style.ERROR(f'  [FAIL] {post}: {e}'))

        self.stdout.write(self.style.SUCCESS('Done.'))
