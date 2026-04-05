import hashlib
import hmac
import json
import logging
from datetime import date, timedelta

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def _get_targeting() -> dict:
    """
    Build targeting spec from AppParameter values.
    Uses a comma-separated list of city keys (boost.geo_keys) — no radius,
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

    Creates: Campaign → AdSet (targeting + budget) → AdCreative (existing post) → Ad.
    Uses OUTCOME_AWARENESS + REACH objective (ODAX) with page_id as promoted_object.

    Returns dict with keys: campaign_id, adset_id, ad_id.
    Raises on any API error.
    """
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    proof = _proof(token)
    ad_account = settings.FACEBOOK_AD_ACCOUNT_ID
    page_id = settings.FACEBOOK_PAGE_ID

    # Prefer reel; fall back to regular post
    story_id = post.facebook_reel_id or post.facebook_post_id
    if not story_id:
        raise ValueError(f"Post {post.id} has no facebook_reel_id or facebook_post_id — publish it first")

    end_date = date.today() + timedelta(days=days)
    daily_budget_cents = int(daily_budget_eur * 100)
    post_name = f"OpenVoor boost — {post.get_category_display()} {post.scheduled_at:%d/%m/%Y}"

    # 1. Campaign — OUTCOME_AWARENESS for broad reach (ODAX)
    campaign_resp = requests.post(
        f"{GRAPH_API_BASE}/{ad_account}/campaigns",
        data={
            "name": post_name,
            "objective": "OUTCOME_AWARENESS",
            "status": "ACTIVE",
            "special_ad_categories": "[]",
            "access_token": token,
            "appsecret_proof": proof,
        },
        timeout=30,
    )
    if not campaign_resp.ok:
        logger.error("Boost campaign creation failed: %s", campaign_resp.text)
        campaign_resp.raise_for_status()
    campaign_id = campaign_resp.json()["id"]
    logger.info("Boost campaign created: %s", campaign_id)

    # 2. AdSet — REACH optimization, promoted_object = page (required for OUTCOME_AWARENESS)
    adset_resp = requests.post(
        f"{GRAPH_API_BASE}/{ad_account}/adsets",
        data={
            "name": post_name,
            "campaign_id": campaign_id,
            "daily_budget": daily_budget_cents,
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "REACH",
            "promoted_object": json.dumps({"page_id": page_id}),
            "targeting": json.dumps(_get_targeting()),
            "end_time": end_date.strftime("%Y-%m-%dT23:59:59+0000"),
            "status": "ACTIVE",
            "is_adset_budget_sharing_enabled": "false",
            "access_token": token,
            "appsecret_proof": proof,
        },
        timeout=30,
    )
    if not adset_resp.ok:
        logger.error("Boost adset creation failed: %s", adset_resp.text)
        adset_resp.raise_for_status()
    adset_id = adset_resp.json()["id"]
    logger.info("Boost adset created: %s", adset_id)

    # 3. AdCreative — references the existing page post or reel
    creative_resp = requests.post(
        f"{GRAPH_API_BASE}/{ad_account}/adcreatives",
        data={
            "name": post_name,
            "object_story_id": story_id,
            "access_token": token,
            "appsecret_proof": proof,
        },
        timeout=30,
    )
    if not creative_resp.ok:
        logger.error("Boost creative creation failed: %s", creative_resp.text)
        creative_resp.raise_for_status()
    creative_id = creative_resp.json()["id"]
    logger.info("Boost creative created: %s", creative_id)

    # 4. Ad
    ad_resp = requests.post(
        f"{GRAPH_API_BASE}/{ad_account}/ads",
        data={
            "name": post_name,
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": "ACTIVE",
            "access_token": token,
            "appsecret_proof": proof,
        },
        timeout=30,
    )
    if not ad_resp.ok:
        logger.error("Boost ad creation failed: %s", ad_resp.text)
        ad_resp.raise_for_status()
    ad_id = ad_resp.json()["id"]
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
