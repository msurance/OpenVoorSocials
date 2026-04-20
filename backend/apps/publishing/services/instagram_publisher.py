import logging
import time

import requests
from django.conf import settings
from apps.publishing.services.facebook_publisher import _get_page_token, _appsecret_proof, SITE_URL

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def publish_to_instagram(post) -> str:
    """
    Publish image post + Reel to Instagram Business.
    Returns comma-separated media IDs: "image_id,reel_id" (reel may be empty if no video).
    """
    if not post.image_url:
        raise ValueError(f"Post {post.id} has no image — Instagram requires an image.")

    caption = f"{post.copy_nl}\n\n{post.hashtags}\n\nLink in bio: {SITE_URL}".strip()
    token = _get_page_token()
    proof = _appsecret_proof(token)
    ig_user_id = settings.INSTAGRAM_USER_ID

    # --- Image post ---
    image_id = _publish_ig_image(ig_user_id, post.image_url, caption, token, proof, post.id)

    # --- Reel (if video exists) ---
    reel_id = ''
    if post.video_path and post.video_url:
        try:
            reel_id = _publish_ig_reel(ig_user_id, post.video_url, caption, token, proof, post.id)
        except Exception as exc:
            logger.error("Instagram Reel failed for post %s (image still published): %s", post.id, exc)

    return ','.join(filter(None, [image_id, reel_id]))


def _publish_ig_image(ig_user_id, image_url, caption, token, proof, post_id):
    logger.info("Creating Instagram image container for post %s", post_id)
    r = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": token, "appsecret_proof": proof},
        timeout=30,
    )
    if not r.ok:
        logger.error("Instagram image container error: %s", r.text)
    r.raise_for_status()
    creation_id = r.json()["id"]

    # Poll until container is ready (images process quickly but not instantly)
    for _ in range(12):
        time.sleep(5)
        status_r = requests.get(
            f"{GRAPH_API_BASE}/{creation_id}",
            params={"fields": "status_code", "access_token": token, "appsecret_proof": proof},
            timeout=15,
        )
        status_code = status_r.json().get("status_code")
        logger.info("Image container status: %s (post %s)", status_code, post_id)
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise RuntimeError(f"Instagram image container failed for post {post_id}")
    else:
        raise TimeoutError(f"Instagram image container timed out for post {post_id}")

    pub = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token, "appsecret_proof": proof},
        timeout=30,
    )
    if not pub.ok:
        logger.error("Instagram image publish error: %s", pub.text)
    pub.raise_for_status()
    media_id = pub.json()["id"]
    logger.info("Instagram image published: %s (post %s)", media_id, post_id)
    return media_id


def _publish_ig_reel(ig_user_id, video_url, caption, token, proof, post_id):
    logger.info("Creating Instagram Reel container for post %s", post_id)
    r = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": token,
            "appsecret_proof": proof,
        },
        timeout=30,
    )
    if not r.ok:
        logger.error("Instagram Reel container error: %s", r.text)
    r.raise_for_status()
    creation_id = r.json()["id"]

    # Poll until video is processed (up to 3 minutes)
    for _ in range(36):
        time.sleep(5)
        status_r = requests.get(
            f"{GRAPH_API_BASE}/{creation_id}",
            params={"fields": "status_code", "access_token": token, "appsecret_proof": proof},
            timeout=15,
        )
        status_code = status_r.json().get("status_code")
        logger.info("Reel processing status: %s (post %s)", status_code, post_id)
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise RuntimeError(f"Instagram Reel processing failed for post {post_id}")
    else:
        raise TimeoutError(f"Instagram Reel processing timed out for post {post_id}")

    pub = requests.post(
        f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token, "appsecret_proof": proof},
        timeout=30,
    )
    if not pub.ok:
        logger.error("Instagram Reel publish error: %s", pub.text)
    pub.raise_for_status()
    reel_id = pub.json()["id"]
    logger.info("Instagram Reel published: %s (post %s)", reel_id, post_id)
    return reel_id
