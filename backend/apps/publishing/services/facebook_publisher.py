import functools
import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def _appsecret_proof(token: str) -> str:
    return hmac.new(
        settings.FACEBOOK_APP_SECRET.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


@functools.lru_cache(maxsize=1)
def _get_page_token() -> str:
    """
    Exchange the System User token for a Page Access Token.
    Cached for the process lifetime — page tokens from system users don't expire.
    """
    system_token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    proof = _appsecret_proof(system_token)
    resp = requests.get(
        f"{GRAPH_API_BASE}/{settings.FACEBOOK_PAGE_ID}",
        params={"fields": "access_token", "access_token": system_token, "appsecret_proof": proof},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def publish_to_facebook(post) -> str:
    """
    Publish a SocialPost to the configured Facebook Page.
    Uses /photos endpoint when image available, falls back to /feed.
    Returns the Facebook post ID string.
    """
    token = _get_page_token()
    proof = _appsecret_proof(token)
    message = f"{post.copy_nl}\n\n{post.hashtags}".strip()

    params = {
        "message": message,
        "access_token": token,
        "appsecret_proof": proof,
    }

    if post.image_path and post.image_url:
        url = f"{GRAPH_API_BASE}/{settings.FACEBOOK_PAGE_ID}/photos"
        params["url"] = post.image_url
    else:
        url = f"{GRAPH_API_BASE}/{settings.FACEBOOK_PAGE_ID}/feed"

    logger.info("Publishing post %s to Facebook", post.id)
    response = requests.post(url, data=params, timeout=30)
    if not response.ok:
        logger.error("Facebook API error: %s", response.text)
    response.raise_for_status()

    data = response.json()
    post_id = data.get("post_id") or data.get("id")
    logger.info("Facebook publish succeeded for post %s → fb_id=%s", post.id, post_id)
    return post_id
