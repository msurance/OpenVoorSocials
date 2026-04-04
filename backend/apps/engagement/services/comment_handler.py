import logging
import requests
from django.conf import settings
from apps.engagement.models import EngagementReply
from apps.engagement.services.discount_api import claim_discount_code, NoCodesAvailable
from apps.engagement.services.reply_generator import (
    generate_fb_public_reply,
    generate_fb_private_message,
    generate_no_codes_reply,
    generate_ig_reply,
)
from apps.publishing.services.facebook_publisher import _get_page_token, _appsecret_proof, GRAPH_API_BASE

logger = logging.getLogger(__name__)


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

    # Ignore comments made by the page itself to prevent reply loops
    if str(user_id) == str(settings.FACEBOOK_PAGE_ID):
        logger.debug("Skipping comment from page itself (comment_id=%s)", comment_id)
        return

    keywords = [k.strip().lower() for k in settings.ENGAGEMENT_KEYWORD.split(',') if k.strip()]
    message_lower = message.lower()
    matched = next((kw for kw in keywords if kw in message_lower), None)
    if not matched:
        return

    if EngagementReply.objects.filter(comment_id=comment_id).exists():
        logger.info("Already replied to %s comment %s — skipping", platform, comment_id)
        return

    logger.info("Keyword '%s' matched in %s comment %s from %s", matched, platform, comment_id, user_name)

    name = _first_name(user_name)
    code = ''
    error = ''
    success = False

    try:
        code = claim_discount_code(platform=platform, user_id=user_id, comment_id=comment_id)
        _send_code_reply(
            platform=platform,
            comment_id=comment_id,
            name=name,
            comment_text=message,
            code=code,
            keyword=matched,
        )
        success = True
        logger.info("Replied to %s comment %s with code %s", platform, comment_id, code)
    except NoCodesAvailable:
        error = 'no_codes_available'
        logger.warning("No codes available — sending sorry reply to %s comment %s", platform, comment_id)
        try:
            _send_no_codes_reply(platform=platform, comment_id=comment_id, name=name, comment_text=message)
            success = True
        except Exception as exc:
            error = f"no_codes_available + reply failed: {exc}"
            logger.error("Failed to send no-codes reply for comment %s: %s", comment_id, exc)
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


def _first_name(user_name: str) -> str:
    return (user_name or '').split()[0] or 'daar'


def _send_code_reply(platform: str, comment_id: str, name: str, comment_text: str, code: str, keyword: str):
    token = _get_page_token()
    proof = _appsecret_proof(token)

    if platform == 'facebook':
        public_text = generate_fb_public_reply(name=name, comment=comment_text, keyword=keyword)
        _post_fb_comment(comment_id, public_text, token, proof)
        private_text = generate_fb_private_message(name=name, comment=comment_text, code=code)
        _post_fb_private_reply(comment_id, private_text, token, proof)
    elif platform == 'instagram':
        text = generate_ig_reply(name=name, comment=comment_text, code=code, keyword=keyword)
        _post_ig_reply(comment_id, text, token, proof)


def _send_no_codes_reply(platform: str, comment_id: str, name: str, comment_text: str):
    token = _get_page_token()
    proof = _appsecret_proof(token)
    text = generate_no_codes_reply(name=name, comment=comment_text, platform=platform)

    if platform == 'facebook':
        _post_fb_comment(comment_id, text, token, proof)
    elif platform == 'instagram':
        _post_ig_reply(comment_id, text, token, proof)


def _post_fb_comment(comment_id: str, message: str, token: str, proof: str):
    resp = requests.post(
        f"{GRAPH_API_BASE}/{comment_id}/comments",
        data={"message": message, "access_token": token, "appsecret_proof": proof},
        timeout=15,
    )
    if not resp.ok:
        logger.error("FB comment reply error: %s", resp.text)
    resp.raise_for_status()


def _post_fb_private_reply(comment_id: str, message: str, token: str, proof: str):
    resp = requests.post(
        f"{GRAPH_API_BASE}/{comment_id}/private_replies",
        data={"message": message, "access_token": token, "appsecret_proof": proof},
        timeout=15,
    )
    if not resp.ok:
        logger.error("FB private reply error: %s", resp.text)
    resp.raise_for_status()


def _post_ig_reply(comment_id: str, message: str, token: str, proof: str):
    resp = requests.post(
        f"{GRAPH_API_BASE}/{comment_id}/replies",
        data={"message": message, "access_token": token, "appsecret_proof": proof},
        timeout=15,
    )
    if not resp.ok:
        logger.error("IG comment reply error: %s", resp.text)
    resp.raise_for_status()
