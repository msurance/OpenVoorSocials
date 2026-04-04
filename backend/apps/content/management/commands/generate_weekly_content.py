import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.content.models import SocialPost
from apps.content.services.content_generator import generate_weekly_posts
from apps.content.services.image_generator import generate_image
from apps.content.services.video_generator import generate_video

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate weekly social media content using Claude + Gemini'

    def add_arguments(self, parser):
        parser.add_argument(
            '--week',
            type=int,
            help='ISO week number to generate (default: next week)',
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Year for the target week (default: current or next year)',
        )

    def handle(self, *args, **options):
        now = timezone.now()

        if options['week']:
            week_number = options['week']
            year = options['year'] or now.year
        else:
            next_week = now + timezone.timedelta(weeks=1)
            iso = next_week.isocalendar()
            week_number = iso[1]
            year = iso[0]  # use isocalendar year, not calendar year (handles Jan edge case)

        self.stdout.write(f"Generating content for week {week_number}/{year}...")

        # Idempotency guard — skip if we already have posts for this week
        existing = SocialPost.objects.filter(week_number=week_number, year=year).count()
        if existing > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"Week {week_number}/{year} already has {existing} posts. "
                    "Pass --week/--year explicitly to re-generate a different week."
                )
            )
            return

        posts_data = generate_weekly_posts(week_number, year)

        created = []
        for data in posts_data:
            post = SocialPost.objects.create(
                category=data['category'],
                platform='both',
                status='draft',
                copy_nl=data['copy_nl'],
                hashtags=data['hashtags'],
                image_prompt=data['image_prompt'],
                scheduled_at=data['scheduled_at'],
                week_number=week_number,
                year=year,
            )
            created.append(post)
            self.stdout.write(f"  Created: {post}")

        logger.info("Created %d SocialPost records for week %d/%d", len(created), week_number, year)

        self.stdout.write(f"Generating {len(created)} images...")
        for post in created:
            try:
                relative_path = generate_image(
                    str(post.id), post.image_prompt, week_number, year, post.category
                )
                post.image_path = relative_path
                post.save(update_fields=['image_path'])
                self.stdout.write(f"  Image OK: {post.id}")
            except Exception as exc:
                logger.error("Image generation failed for %s: %s", post.id, exc, exc_info=True)
                self.stdout.write(self.style.ERROR(f"  Image FAILED for {post.id}: {exc}"))

        self.stdout.write(f"Generating {len(created)} videos...")
        for post in created:
            if not post.image_path:
                self.stdout.write(self.style.WARNING(f"  Video skipped (no image): {post.id}"))
                continue
            try:
                relative_path = generate_video(
                    str(post.id), post.image_path, post.category, week_number, year
                )
                post.video_path = relative_path
                post.save(update_fields=['video_path'])
                self.stdout.write(f"  Video OK: {post.id}")
            except Exception as exc:
                logger.error("Video generation failed for %s: %s", post.id, exc, exc_info=True)
                self.stdout.write(self.style.ERROR(f"  Video FAILED for {post.id}: {exc}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {len(created)} posts created for week {week_number}/{year}."
            )
        )
