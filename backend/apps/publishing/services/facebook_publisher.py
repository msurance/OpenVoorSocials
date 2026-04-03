import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def publish_to_facebook(post) -> str:
    """
    Publish a SocialPost to the configured Facebook Page.

    Uses the /photos endpoint when an image is available (renders better in feed),
    falls back to /feed for text-only posts.

    Returns the Facebook post ID string.
    Raises requests.HTTPError or any other exception on failure — caller handles it.
    """
    message = f"{post.copy_nl}\n\n{post.hashtags}".strip()

    params = {
        'message': message,
        'access_token': settings.FACEBOOK_PAGE_ACCESS_TOKEN,
    }

    if post.image_path and post.image_url:
        url = f"{GRAPH_API_BASE}/{settings.FACEBOOK_PAGE_ID}/photos"
        params['url'] = post.image_url
    else:
        url = f"{GRAPH_API_BASE}/{settings.FACEBOOK_PAGE_ID}/feed"

    logger.info("Publishing post %s to Facebook (platform: %s)", post.id, post.platform)

    response = requests.post(url, data=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    # /photos returns {"id": "...", "post_id": "..."} — prefer post_id for feed linking
    post_id = data.get('post_id') or data.get('id')

    logger.info("Facebook publish succeeded for post %s → fb_id=%s", post.id, post_id)
    return post_id
