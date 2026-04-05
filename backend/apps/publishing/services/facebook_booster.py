import hashlib
import hmac
import json
import logging
from datetime import date, timedelta

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

# Default targeting: Brugge BE + 10 km radius, age 18-65
DEFAULT_TARGETING = {
    "geo_locations": {
        "cities": [{"key": "172915", "radius": 10, "distance_unit": "kilometer"}]
    },
    "age_min": 25,
    "age_max": 65,  # Facebook's max is 65, which means "65 and older" (covers up to 90+)
}


def _proof(token: str) -> str:
    return hmac.new(
        settings.FACEBOOK_APP_SECRET.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


def boost_post(post, daily_budget_eur: float, days: int) -> dict:
    """
    Boost an existing Facebook page post via the Ads API.

    Creates: Campaign → AdSet (targeting + budget) → AdCreative (existing post) → Ad.

    Returns dict with keys: campaign_id, adset_id, ad_id.
    Raises on any API error.
    """
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    proof = _proof(token)
    ad_account = settings.FACEBOOK_AD_ACCOUNT_ID
    page_id = settings.FACEBOOK_PAGE_ID

    # The Facebook post ID to boost (feed post, not reel)
    if not post.facebook_post_id:
        raise ValueError(f"Post {post.id} has no facebook_post_id — publish it first")

    end_date = date.today() + timedelta(days=days)
    # Facebook expects daily_budget in cents
    daily_budget_cents = int(daily_budget_eur * 100)
    post_name = f"OpenVoor boost — {post.get_category_display()} {post.scheduled_at:%d/%m/%Y}"

    # 1. Campaign
    campaign_resp = requests.post(
        f"{GRAPH_API_BASE}/{ad_account}/campaigns",
        data={
            "name": post_name,
            "objective": "POST_ENGAGEMENT",
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

    # 2. AdSet
    adset_resp = requests.post(
        f"{GRAPH_API_BASE}/{ad_account}/adsets",
        data={
            "name": post_name,
            "campaign_id": campaign_id,
            "daily_budget": daily_budget_cents,
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "POST_ENGAGEMENT",
            "targeting": json.dumps(DEFAULT_TARGETING),
            "end_time": end_date.strftime("%Y-%m-%dT23:59:59+0000"),
            "status": "ACTIVE",
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

    # 3. AdCreative — references existing page post
    object_story_id = f"{page_id}_{post.facebook_post_id.split('_')[-1]}"
    creative_resp = requests.post(
        f"{GRAPH_API_BASE}/{ad_account}/adcreatives",
        data={
            "name": post_name,
            "object_story_id": post.facebook_post_id,
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
