import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def _appsecret_proof(token: str) -> str:
    """HMAC-SHA256 of the access token — required for server-side Graph API calls."""
    return hmac.new(
        settings.FACEBOOK_APP_SECRET.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


def publish_to_facebook(post) -> str:
    """
    Publish a SocialPost to the configured Facebook Page.

    Uses the /photos endpoint when an image is available (renders better in feed),
    falls back to /feed for text-only posts.

    Returns the Facebook post ID string.
    Raises requests.HTTPError or any other exception on failure — caller handles it.
    """
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    message = f"{post.copy_nl}\n\n{post.hashtags}".strip()

    params = {
        'message': message,
        'access_token': token,
        'appsecret_proof': _appsecret_proof(token),
    }

    if post.image_path and post.image_url:
        url = f"{GRAPH_API_BASE}/{settings.FACEBOOK_PAGE_ID}/photos"
        params['url'] = post.image_url
    else:
        url = f"{GRAPH_API_BASE}/{settings.FACEBOOK_PAGE_ID}/feed"

    logger.info("Publishing post %s to Facebook (platform: %s)", post.id, post.platform)

    response = requests.post(url, data=params, timeout=30)
    if not response.ok:
        logger.error("Facebook API error: %s", response.text)
    response.raise_for_status()

    data = response.json()
    post_id = data.get('post_id') or data.get('id')

    logger.info("Facebook publish succeeded for post %s → fb_id=%s", post.id, post_id)
    return post_id
