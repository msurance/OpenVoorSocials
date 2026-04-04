import logging
import requests
from django.conf import settings
from apps.engagement.models import EngagementReply
from apps.engagement.services.discount_api import claim_discount_code
from apps.publishing.services.facebook_publisher import _get_page_token, _appsecret_proof, GRAPH_API_BASE

logger = logging.getLogger(__name__)

_FB_REPLY = (
    "Bedankt voor je reactie, {name}! \U0001f389 "
    "Hier is jouw unieke kortingscode: {code}\n"
    "Geldig voor 25% korting op je eerste maand OpenVoor Premium.\n"
    "\U0001f449 Gebruik de code op https://openvoor.app bij het afrekenen. Veel succes!"
)

_IG_REPLY = (
    "Bedankt {name}! \U0001f389 Jouw kortingscode: {code} \u2014 "
    "25% korting op je eerste maand OpenVoor Premium op https://openvoor.app"
)


def handle_comment(
    comment_id: str,
    user_id: str,
    user_name: str,
    post_id: str,
    message: str,
    platform: str,
):
    if not comment_id:
        return

    keyword = settings.ENGAGEMENT_KEYWORD.lower()
    if keyword not in message.lower():
        return

    if EngagementReply.objects.filter(comment_id=comment_id).exists():
        logger.info("Already replied to %s comment %s — skipping", platform, comment_id)
        return

    logger.info("Keyword '%s' in %s comment %s from %s", keyword, platform, comment_id, user_name)

    code = ''
    error = ''
    success = False

    try:
        code = claim_discount_code(platform=platform, user_id=user_id, comment_id=comment_id)
        _send_reply(platform=platform, comment_id=comment_id, user_name=user_name, code=code)
        success = True
        logger.info("Replied to %s comment %s with code %s", platform, comment_id, code)
    except Exception as exc:
        error = str(exc)
        logger.error("Failed to handle comment %s: %s", comment_id, exc)

    EngagementReply.objects.create(
        comment_id=comment_id,
        platform=platform,
        user_id=user_id or '',
        user_name=user_name or '',
        post_id=post_id or '',
        discount_code=code,
        success=success,
        error=error,
    )


def _send_reply(platform: str, comment_id: str, user_name: str, code: str):
    token = _get_page_token()
    proof = _appsecret_proof(token)
    name = (user_name or '').split()[0] or 'daar'

    if platform == 'facebook':
        message = _FB_REPLY.format(name=name, code=code)
        resp = requests.post(
            f"{GRAPH_API_BASE}/{comment_id}/comments",
            data={"message": message, "access_token": token, "appsecret_proof": proof},
            timeout=15,
        )
        if not resp.ok:
            logger.error("FB comment reply error: %s", resp.text)
        resp.raise_for_status()

    elif platform == 'instagram':
        message = _IG_REPLY.format(name=name, code=code)
        resp = requests.post(
            f"{GRAPH_API_BASE}/{comment_id}/replies",
            data={"message": message, "access_token": token, "appsecret_proof": proof},
            timeout=15,
        )
        if not resp.ok:
            logger.error("IG comment reply error: %s", resp.text)
        resp.raise_for_status()
