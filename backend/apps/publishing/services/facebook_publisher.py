import functools
import hashlib
import hmac
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"
SITE_URL = "https://openvoor.app"


def _appsecret_proof(token: str) -> str:
    return hmac.new(
        settings.FACEBOOK_APP_SECRET.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


@functools.lru_cache(maxsize=1)
def _get_page_token() -> str:
    """Exchange System User token for a Page Access Token (cached, doesn't expire)."""
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
    Publish a SocialPost to the Facebook Page feed.

    Two-step when image available:
      1. Upload photo as unpublished → get photo_id
      2. Post to /feed with attached_media → appears in timeline with full image

    Falls back to text-only /feed post if no image.
    Returns the Facebook post ID string.
    """
    token = _get_page_token()
    proof = _appsecret_proof(token)
    page_id = settings.FACEBOOK_PAGE_ID

    message = f"{post.copy_nl}\n\n{post.hashtags}\n\n{SITE_URL}".strip()

    if post.image_path and post.image_url:
        # Step 1: upload as unpublished photo
        photo_resp = requests.post(
            f"{GRAPH_API_BASE}/{page_id}/photos",
            data={
                "url": post.image_url,
                "published": "false",
                "access_token": token,
                "appsecret_proof": proof,
            },
            timeout=30,
        )
        if not photo_resp.ok:
            logger.error("Facebook photo upload error: %s", photo_resp.text)
        photo_resp.raise_for_status()
        photo_id = photo_resp.json()["id"]

        # Step 2: post to feed with attached photo
        feed_resp = requests.post(
            f"{GRAPH_API_BASE}/{page_id}/feed",
            data={
                "message": message,
                "attached_media": json.dumps([{"media_fbid": photo_id}]),
                "access_token": token,
                "appsecret_proof": proof,
            },
            timeout=30,
        )
        if not feed_resp.ok:
            logger.error("Facebook feed post error: %s", feed_resp.text)
        feed_resp.raise_for_status()
        post_id = feed_resp.json()["id"]
    else:
        # Text-only feed post
        feed_resp = requests.post(
            f"{GRAPH_API_BASE}/{page_id}/feed",
            data={"message": message, "access_token": token, "appsecret_proof": proof},
            timeout=30,
        )
        if not feed_resp.ok:
            logger.error("Facebook feed post error: %s", feed_resp.text)
        feed_resp.raise_for_status()
        post_id = feed_resp.json()["id"]

    logger.info("Facebook publish succeeded for post %s → fb_id=%s", post.id, post_id)
    return post_id
