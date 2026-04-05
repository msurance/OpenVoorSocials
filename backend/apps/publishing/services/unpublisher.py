import logging

import requests

from apps.publishing.services.facebook_publisher import (
    GRAPH_API_BASE,
    _appsecret_proof,
    _get_page_token,
)

logger = logging.getLogger(__name__)


def _delete(object_id: str, token: str, proof: str) -> None:
    """DELETE a single Graph API object. Ignores 404 (already gone)."""
    resp = requests.delete(
        f"{GRAPH_API_BASE}/{object_id}",
        params={"access_token": token, "appsecret_proof": proof},
        timeout=15,
    )
    if resp.status_code == 404:
        logger.info("Object %s already deleted (404) — skipping", object_id)
        return
    if not resp.ok:
        logger.error("Delete failed for %s: %s", object_id, resp.text)
        resp.raise_for_status()
    logger.info("Deleted %s", object_id)


def unpublish_post(post) -> dict:
    """
    Delete the post from all platforms where it was published.
    Returns {'deleted': [...], 'errors': [...]}.
    Resets the SocialPost record regardless of partial failures.
    """
    token = _get_page_token()
    proof = _appsecret_proof(token)

    deleted = []
    errors = []

    for label, object_id in [
        ("FB post",  post.facebook_post_id),
        ("FB reel",  post.facebook_reel_id),
        ("IG post",  post.instagram_post_id),
        ("IG reel",  post.instagram_reel_id),
    ]:
        if not object_id:
            continue
        try:
            _delete(object_id, token, proof)
            deleted.append(label)
        except Exception as exc:
            logger.error("Could not delete %s (%s) for post %s: %s", label, object_id, post.id, exc)
            errors.append(f"{label}: {exc}")

    return {"deleted": deleted, "errors": errors}
