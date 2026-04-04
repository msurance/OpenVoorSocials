import logging
import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from apps.publishing.services.facebook_publisher import _get_page_token, _appsecret_proof, GRAPH_API_BASE

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Subscribe the Facebook Page to feed comments webhook"

    def handle(self, *args, **options):
        token = _get_page_token()
        proof = _appsecret_proof(token)
        page_id = settings.FACEBOOK_PAGE_ID

        resp = requests.post(
            f"{GRAPH_API_BASE}/{page_id}/subscribed_apps",
            data={
                "subscribed_fields": "feed",
                "access_token": token,
                "appsecret_proof": proof,
            },
            timeout=15,
        )
        self.stdout.write(f"Facebook Page subscription: {resp.status_code}")
        if resp.ok:
            self.stdout.write(self.style.SUCCESS("Facebook webhook subscription active."))
        else:
            self.stdout.write(self.style.ERROR(f"Failed: {resp.text}"))

        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "Instagram webhooks must be configured in the Meta Developer Dashboard:\n"
            "  App Dashboard -> Webhooks -> Instagram -> Subscribe to: comments\n"
            f"  Callback URL: {settings.BASE_URL}/webhooks/facebook/\n"
            f"  Verify token: (set WEBHOOK_VERIFY_TOKEN env var)"
        ))
