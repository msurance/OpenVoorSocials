import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.content.models import SocialPost
from apps.publishing.services.facebook_publisher import publish_to_facebook
from apps.publishing.services.instagram_publisher import publish_to_instagram

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Publish approved posts whose scheduled_at is in the past'

    def handle(self, *args, **options):
        from apps.params.models import CronLog

        now = timezone.now()
        published_count = 0
        failed_count = 0
        notes = []

        # Recovery: posts stuck with status='published' but published_at=None were
        # mid-flight when the server restarted.  Reset them so this run re-tries.
        stuck = SocialPost.objects.filter(status='published', published_at__isnull=True)
        stuck_count = stuck.count()
        if stuck_count:
            stuck.update(status='approved')
            msg = f"Recovered {stuck_count} stuck post(s) → reset to approved"
            logger.warning(msg)
            notes.append(msg)

        with transaction.atomic():
            due_posts = list(
                SocialPost.objects.select_for_update(skip_locked=True).filter(
                    status='approved',
                    scheduled_at__lte=now,
                )
            )

        if not due_posts:
            CronLog.objects.create(posts_due=0, posts_published=0, posts_failed=0, notes='no posts due')
            self.stdout.write("No posts due for publishing.")
            return

        self.stdout.write(f"Found {len(due_posts)} post(s) to publish.")

        for post in due_posts:
            self.stdout.write(f"Publishing: {post.id} scheduled={post.scheduled_at}")
            errors = []

            with transaction.atomic():
                locked_post = (
                    SocialPost.objects.select_for_update(skip_locked=True)
                    .filter(pk=post.pk, status='approved')
                    .first()
                )
                if locked_post is None:
                    logger.info("Post %s no longer available — skipping.", post.pk)
                    continue

                if locked_post.platform in ('facebook', 'both'):
                    try:
                        fb_id = publish_to_facebook(locked_post)
                        locked_post.facebook_post_id = fb_id
                        logger.info("Facebook OK for post %s: %s", locked_post.id, fb_id)
                    except Exception as exc:
                        logger.error("Facebook publish failed for %s: %s", locked_post.id, exc, exc_info=True)
                        errors.append(f"Facebook: {exc}")

                if locked_post.platform in ('instagram', 'both'):
                    try:
                        ig_id = publish_to_instagram(locked_post)
                        locked_post.instagram_post_id = ig_id
                        logger.info("Instagram OK for post %s: %s", locked_post.id, ig_id)
                    except Exception as exc:
                        logger.error("Instagram publish failed for %s: %s", locked_post.id, exc, exc_info=True)
                        errors.append(f"Instagram: {exc}")

                if errors:
                    locked_post.status = 'failed'
                    locked_post.error_message = '\n'.join(errors)
                    failed_count += 1
                    notes.append(f"FAILED {locked_post.id}: {'; '.join(errors)}")
                    self.stdout.write(self.style.ERROR(f"  FAILED: {errors}"))
                else:
                    locked_post.status = 'published'
                    locked_post.published_at = now
                    locked_post.error_message = ''
                    published_count += 1
                    self.stdout.write(self.style.SUCCESS("  Published OK"))

                locked_post.save(update_fields=[
                    'status',
                    'published_at',
                    'facebook_post_id',
                    'instagram_post_id',
                    'error_message',
                ])

        CronLog.objects.create(
            posts_due=len(due_posts),
            posts_published=published_count,
            posts_failed=failed_count,
            notes='\n'.join(notes),
        )
        self.stdout.write(f"Publish run complete. published={published_count} failed={failed_count}")
