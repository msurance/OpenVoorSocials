import hashlib
import hmac
import json
import logging
import time
from datetime import date, timedelta, timezone, datetime

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

DSA_BENEFICIARY = "OpenVoor.app"
DSA_PAYOR = "OpenVoor.app"


def _get_targeting() -> dict:
    """
    Build targeting spec from AppParameter values.
    Uses comma-separated city keys (boost.geo_keys) — no radius,
    which avoids geo boundary errors when cities are near the coast.
    Editable in Django Admin → Parameters.
    """
    from apps.params.helpers import get_param
    geo_keys_str = get_param('boost.geo_keys', '172915,173785,177675,178283,181937')
    cities = [{"key": k.strip()} for k in geo_keys_str.split(',') if k.strip()]
    return {
        "geo_locations": {"cities": cities},
        "age_min": get_param('boost.age_min', 25),
        "age_max": get_param('boost.age_max', 65),
    }


def _post_with_retry(url: str, data: dict, retries: int = 3, delay: float = 3.0) -> dict:
    """POST to Graph API, retrying on transient errors (code 2 / 500)."""
    for attempt in range(1, retries + 1):
        resp = requests.post(url, data=data, timeout=30)
        body = resp.json()
        err = body.get('error', {})
        if resp.ok:
            return body
        if err.get('is_transient') or err.get('code') == 2:
            logger.warning("Transient Graph API error on attempt %d/%d: %s", attempt, retries, err.get('message'))
            if attempt < retries:
                time.sleep(delay)
                continue
        resp.raise_for_status()
    return body  # unreachable but satisfies linter


def _proof(token: str) -> str:
    return hmac.new(
        settings.FACEBOOK_APP_SECRET.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


def boost_post(post, daily_budget_eur: float, days: int) -> dict:
    """
    Boost an existing Facebook page post (image or reel) via the Ads API.
    Prefers the reel ID if available, falls back to the image post ID.
    Runs on Facebook Feed/Reels + Instagram Feed/Reels.

    Creates: Campaign → AdSet (targeting + budget) → AdCreative (existing post) → Ad.

    Returns dict with keys: campaign_id, adset_id, ad_id.
    Raises on any API error.
    """
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    proof = _proof(token)
    ad_account = settings.FACEBOOK_AD_ACCOUNT_ID
    page_id = settings.FACEBOOK_PAGE_ID

    # Use facebook_post_id (PAGE_ID_POST_ID format) — this is the page story ID
    # that the Ads API accepts for object_story_id.
    # facebook_reel_id is a standalone video object ID and cannot be boosted directly.
    story_id = post.facebook_post_id
    if not story_id:
        raise ValueError(f"Post {post.id} has no facebook_post_id — publish it first")

    # Unix timestamp avoids the '+' URL-encoding issue with ISO format
    end_ts = int(
        datetime(
            *( date.today() + timedelta(days=days) ).timetuple()[:3],
            23, 59, 59,
            tzinfo=timezone.utc,
        ).timestamp()
    )
    daily_budget_cents = int(daily_budget_eur * 100)
    post_name = f"OpenVoor boost — {post.get_category_display()} {post.scheduled_at:%d/%m/%Y}"

    # 1. Campaign — OUTCOME_AWARENESS (ODAX)
    campaign_data = _post_with_retry(
        f"{GRAPH_API_BASE}/{ad_account}/campaigns",
        data={
            "name": post_name,
            "objective": "OUTCOME_AWARENESS",
            "status": "ACTIVE",
            "special_ad_categories": "[]",
            "is_adset_budget_sharing_enabled": "false",
            "access_token": token,
            "appsecret_proof": proof,
        },
    )
    campaign_id = campaign_data["id"]
    logger.info("Boost campaign created: %s", campaign_id)

    # 2. AdSet — REACH, city list, Facebook + Instagram placements
    adset_data = _post_with_retry(
        f"{GRAPH_API_BASE}/{ad_account}/adsets",
        data={
            "name": post_name,
            "campaign_id": campaign_id,
            "daily_budget": daily_budget_cents,
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "REACH",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "promoted_object": json.dumps({"page_id": page_id}),
            "targeting": json.dumps(_get_targeting()),
            "publisher_platforms": json.dumps(["facebook", "instagram"]),
            "facebook_positions": json.dumps(["feed", "reels"]),
            "instagram_positions": json.dumps(["stream", "reels"]),
            "end_time": end_ts,
            "status": "ACTIVE",
            "is_adset_budget_sharing_enabled": "false",
            "dsa_beneficiary": DSA_BENEFICIARY,
            "dsa_payor": DSA_PAYOR,
            "access_token": token,
            "appsecret_proof": proof,
        },
    )
    adset_id = adset_data["id"]
    logger.info("Boost adset created: %s", adset_id)

    # 3. AdCreative — references the existing page post (PAGE_ID_POST_ID format)
    creative_data = _post_with_retry(
        f"{GRAPH_API_BASE}/{ad_account}/adcreatives",
        data={
            "name": post_name,
            "object_story_id": story_id,
            "access_token": token,
            "appsecret_proof": proof,
        },
    )
    creative_id = creative_data["id"]
    logger.info("Boost creative created: %s", creative_id)

    # 4. Ad
    ad_data = _post_with_retry(
        f"{GRAPH_API_BASE}/{ad_account}/ads",
        data={
            "name": post_name,
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": "ACTIVE",
            "access_token": token,
            "appsecret_proof": proof,
        },
    )
    ad_id = ad_data["id"]
    logger.info("Boost ad created: %s for post %s", ad_id, post.id)

    return {"campaign_id": campaign_id, "adset_id": adset_id, "ad_id": ad_id}


def fetch_boost_metrics(campaign_id: str) -> dict:
    """
    Pull spend and reach for a campaign.
    Returns dict with keys: spend_eur (float), reach (int).
    """
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    proof = _proof(token)

    resp = requests.get(
        f"{GRAPH_API_BASE}/{campaign_id}/insights",
        params={
            "fields": "spend,reach",
            "access_token": token,
            "appsecret_proof": proof,
        },
        timeout=30,
    )
    if not resp.ok:
        logger.error("Boost metrics fetch failed for %s: %s", campaign_id, resp.text)
        resp.raise_for_status()

    data = resp.json().get("data", [])
    if not data:
        return {"spend_eur": 0.0, "reach": 0}

    row = data[0]
    return {
        "spend_eur": float(row.get("spend", 0)),
        "reach": int(row.get("reach", 0)),
    }
