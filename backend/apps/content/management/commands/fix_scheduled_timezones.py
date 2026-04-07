"""
One-time migration: shift future post scheduled_at times from UTC to Brussels time.

Because scheduled_at was previously generated with naive datetimes (stored as UTC),
posts at "10:00 Brussels" were actually stored as 10:00 UTC = 12:00 Brussels.

This command shifts all future approved/draft posts back by the UTC offset of
Europe/Brussels at the time of their scheduled slot, so they end up at the
originally intended Brussels wall-clock time.

Safe to run multiple times — it only touches posts that still appear "wrong"
(i.e. posts whose scheduled_at hour is in the expected naive range and hasn't
been fixed yet).  Run once after deploying the make_aware() fix.
"""
import logging
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.content.models import SocialPost

logger = logging.getLogger(__name__)
BRUSSELS = ZoneInfo('Europe/Brussels')


class Command(BaseCommand):
    help = 'Shift future post scheduled_at from accidental UTC storage → Brussels time'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show what would change without saving')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()

        # Only future posts still waiting to publish
        posts = SocialPost.objects.filter(
            status__in=('draft', 'approved'),
            scheduled_at__gt=now,
        )

        fixed = 0
        skipped = 0
        for post in posts:
            utc_dt = post.scheduled_at
            # What Brussels wall-clock time is this stored UTC time equivalent to?
            brussels_dt = utc_dt.astimezone(BRUSSELS)
            # Get the UTC offset at that moment
            offset_hours = int(brussels_dt.utcoffset().total_seconds() / 3600)

            if offset_hours == 0:
                # Already UTC-only (no offset) — skip
                skipped += 1
                continue

            # Shift back: subtract the offset to align wall-clock to Brussels intended time
            corrected = utc_dt - brussels_dt.utcoffset()

            self.stdout.write(
                f"{'[DRY] ' if dry_run else ''}"
                f"Post {post.id}: {utc_dt.strftime('%Y-%m-%d %H:%M %Z')} "
                f"→ {corrected.strftime('%Y-%m-%d %H:%M %Z')} "
                f"(Brussels: {corrected.astimezone(BRUSSELS).strftime('%H:%M')})"
            )

            if not dry_run:
                post.scheduled_at = corrected
                post.save(update_fields=['scheduled_at'])
            fixed += 1

        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY] ' if dry_run else ''}Fixed {fixed} post(s), skipped {skipped}."
        ))
