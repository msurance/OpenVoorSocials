import functools
import hashlib
import hmac
import json
import logging
import time

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

    logger.info("Facebook image/feed published for post %s → fb_id=%s", post.id, post_id)

    # Also publish as Reel if video exists
    reel_id = ''
    if post.video_path and post.video_url:
        try:
            reel_id = _publish_fb_reel(token, proof, page_id, post)
        except Exception as exc:
            logger.error("Facebook Reel failed for post %s (feed post still published): %s", post.id, exc)

    return ','.join(filter(None, [post_id, reel_id]))


def _publish_fb_reel(token, proof, page_id, post):
    """Upload and publish video as a Facebook Reel."""
    message = f"{post.copy_nl}\n\n{post.hashtags}\n\n{SITE_URL}".strip()

    logger.info("Publishing Facebook Reel for post %s", post.id)

    # Step 1: Initialize upload session
    init_resp = requests.post(
        f"{GRAPH_API_BASE}/{page_id}/video_reels",
        data={
            "upload_phase": "start",
            "access_token": token,
            "appsecret_proof": proof,
        },
        timeout=30,
    )
    if not init_resp.ok:
        logger.error("FB Reel init error: %s", init_resp.text)
        init_resp.raise_for_status()
    video_id = init_resp.json()["video_id"]
    upload_url = init_resp.json()["upload_url"]

    # Step 2: Upload video bytes
    video_bytes = requests.get(post.video_url, timeout=60).content
    upload_resp = requests.post(
        upload_url,
        headers={
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(len(video_bytes)),
        },
        data=video_bytes,
        timeout=120,
    )
    if not upload_resp.ok:
        logger.error("FB Reel upload error: %s", upload_resp.text)
        upload_resp.raise_for_status()

    # Step 3: Finish and publish
    finish_resp = requests.post(
        f"{GRAPH_API_BASE}/{page_id}/video_reels",
        data={
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": message,
            "access_token": token,
            "appsecret_proof": proof,
        },
        timeout=30,
    )
    if not finish_resp.ok:
        logger.error("FB Reel finish error: %s", finish_resp.text)
        finish_resp.raise_for_status()

    logger.info("Facebook Reel published for post %s → video_id=%s", post.id, video_id)
    return video_id
