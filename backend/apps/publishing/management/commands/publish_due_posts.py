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
        now = timezone.now()

        # select_for_update(skip_locked=True) ensures that if two cron invocations
        # overlap they each grab a non-overlapping set of rows — no double-publishes.
        with transaction.atomic():
            due_posts = list(
                SocialPost.objects.select_for_update(skip_locked=True).filter(
                    status='approved',
                    scheduled_at__lte=now,
                )
            )

        if not due_posts:
            self.stdout.write("No posts due for publishing.")
            return

        self.stdout.write(f"Found {len(due_posts)} post(s) to publish.")

        for post in due_posts:
            self.stdout.write(f"Publishing: {post}")
            errors = []

            with transaction.atomic():
                # Re-lock the individual row before mutating to stay safe
                # even if the outer queryset was collected outside atomic.
                locked_post = (
                    SocialPost.objects.select_for_update(skip_locked=True)
                    .filter(pk=post.pk, status='approved')
                    .first()
                )
                if locked_post is None:
                    # Another process already claimed this post
                    logger.info("Post %s no longer available — skipping.", post.pk)
                    continue

                if locked_post.platform in ('facebook', 'both'):
                    try:
                        fb_id = publish_to_facebook(locked_post)
                        locked_post.facebook_post_id = fb_id
                    except Exception as exc:
                        logger.error(
                            "Facebook publish failed for %s: %s", locked_post.id, exc,
                            exc_info=True,
                        )
                        errors.append(f"Facebook: {exc}")

                if locked_post.platform in ('instagram', 'both'):
                    try:
                        ig_id = publish_to_instagram(locked_post)
                        locked_post.instagram_post_id = ig_id
                    except Exception as exc:
                        logger.error(
                            "Instagram publish failed for %s: %s", locked_post.id, exc,
                            exc_info=True,
                        )
                        errors.append(f"Instagram: {exc}")

                if errors:
                    locked_post.status = 'failed'
                    locked_post.error_message = '\n'.join(errors)
                    self.stdout.write(self.style.ERROR(f"  FAILED: {errors}"))
                else:
                    locked_post.status = 'published'
                    locked_post.published_at = now
                    locked_post.error_message = ''
                    self.stdout.write(self.style.SUCCESS("  Published OK"))

                locked_post.save(update_fields=[
                    'status',
                    'published_at',
                    'facebook_post_id',
                    'instagram_post_id',
                    'error_message',
                ])

        self.stdout.write("Publish run complete.")
