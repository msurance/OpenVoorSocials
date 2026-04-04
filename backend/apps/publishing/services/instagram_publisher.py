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


def publish_to_instagram(post) -> str:
    """
    Publish a SocialPost to Instagram Business via the two-step Graph API flow:
      1. Create a media container (returns creation_id)
      2. Publish the container (returns the live media ID)

    Instagram always requires an image — raises ValueError if none is present.
    Raises requests.HTTPError on API failures — caller handles it.

    Returns the Instagram media ID string.
    """
    if not post.image_url:
        raise ValueError(
            f"Post {post.id} has no image — Instagram requires an image to publish."
        )

    caption = f"{post.copy_nl}\n\n{post.hashtags}".strip()
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    proof = _appsecret_proof(token)
    ig_user_id = settings.INSTAGRAM_USER_ID

    # Step 1: Create media container
    logger.info("Creating Instagram media container for post %s", post.id)

    container_resp = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={
            'image_url': post.image_url,
            'caption': caption,
            'access_token': token,
            'appsecret_proof': proof,
        },
        timeout=30,
    )
    if not container_resp.ok:
        logger.error("Instagram container error: %s", container_resp.text)
    container_resp.raise_for_status()
    creation_id = container_resp.json()['id']

    logger.info("Instagram container created: %s (post %s)", creation_id, post.id)

    # Step 2: Publish the container
    publish_resp = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
        data={
            'creation_id': creation_id,
            'access_token': token,
            'appsecret_proof': proof,
        },
        timeout=30,
    )
    if not publish_resp.ok:
        logger.error("Instagram publish error: %s", publish_resp.text)
    publish_resp.raise_for_status()

    media_id = publish_resp.json()['id']
    logger.info("Instagram publish succeeded for post %s → media_id=%s", post.id, media_id)
    return media_id
