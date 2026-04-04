import logging
import random
import requests
from django.conf import settings
from apps.engagement.models import EngagementReply
from apps.params.helpers import get_param
from apps.engagement.services.discount_api import claim_discount_code, NoCodesAvailable
from apps.engagement.services.reply_generator import (
    generate_fb_reply_with_code,
    generate_no_codes_reply,
    generate_ig_reply,
    generate_ai_acknowledgment,
    generate_natural_reply,
)
from apps.publishing.services.facebook_publisher import _get_page_token, _appsecret_proof, GRAPH_API_BASE

logger = logging.getLogger(__name__)

# Reply types stored in EngagementReply.error field for auditing
_TYPE_DISCOUNT = 'discount'
_TYPE_AI = 'ai_acknowledgment'
_TYPE_NATURAL = 'natural'


def handle_comment(
    comment_id: str,
    user_id: str,
    user_name: str,
    post_id: str,
    message: str,
    platform: str,
    parent_id: str = '',
):
    if not comment_id:
        return

    # Never reply to the page's own comments
    if str(user_id) == str(settings.FACEBOOK_PAGE_ID):
        logger.debug("Skipping comment from page itself (comment_id=%s)", comment_id)
        return

    # Skip replies to our own replies (prevents reply loops on comment threads)
    if parent_id and EngagementReply.objects.filter(comment_id=parent_id).exists():
        logger.info("Skipping reply to our own comment (parent=%s, comment=%s)", parent_id, comment_id)
        return

    # Skip if already handled
    if EngagementReply.objects.filter(comment_id=comment_id).exists():
        logger.info("Already replied to %s comment %s — skipping", platform, comment_id)
        return

    name = _first_name(user_name)
    message_lower = message.lower()

    # --- Priority 1: discount keyword ---
    kw_str = get_param('engagement.keywords', 'match,openvoor,klaar,korting')
    discount_keywords = [k.strip().lower() for k in kw_str.split(',') if k.strip()]
    matched_discount = next((kw for kw in discount_keywords if kw in message_lower), None)
    if matched_discount:
        _handle_discount_comment(comment_id, user_id, user_name, post_id, message, platform, name, matched_discount)
        return

    # --- Priority 2: AI comment ---
    ai_kw_str = get_param('engagement.ai_keywords', 'ai,robot,nep,chatgpt,gegenereerd')
    ai_keywords = [k.strip().lower() for k in ai_kw_str.split(',') if k.strip()]
    if any(kw in message_lower for kw in ai_keywords):
        _handle_ai_comment(comment_id, user_id, user_name, post_id, message, platform, name)
        return

    # --- Priority 3: natural engagement (probabilistic) ---
    rate = get_param('engagement.natural_reply_rate', 25)
    if random.randint(1, 100) <= rate:
        _handle_natural_comment(comment_id, user_id, user_name, post_id, message, platform, name)


def _handle_discount_comment(comment_id, user_id, user_name, post_id, message, platform, name, keyword):
    logger.info("Discount keyword '%s' in %s comment %s from %s", keyword, platform, comment_id, user_name)
    code = ''
    reply_text = ''
    error = ''
    success = False

    try:
        code = claim_discount_code(platform=platform, user_id=user_id, comment_id=comment_id)
        reply_text = _send_code_reply(platform=platform, comment_id=comment_id, name=name, comment_text=message, code=code, keyword=keyword)
        success = True
        logger.info("Discount reply sent for %s comment %s with code %s", platform, comment_id, code)
    except NoCodesAvailable:
        error = 'no_codes_available'
        try:
            reply_text = _send_no_codes_reply(platform=platform, comment_id=comment_id, name=name, comment_text=message)
            success = True
        except Exception as exc:
            error = f"no_codes_available + reply failed: {exc}"
            logger.error("Failed to send no-codes reply for comment %s: %s", comment_id, exc)
    except Exception as exc:
        error = str(exc)
        logger.error("Failed to handle discount comment %s: %s", comment_id, exc)

    EngagementReply.objects.create(
        comment_id=comment_id, platform=platform, reply_type=_TYPE_DISCOUNT,
        user_id=user_id or '', user_name=user_name or '',
        post_id=post_id or '', comment_text=message,
        reply_text=reply_text, discount_code=code,
        success=success, error=error,
    )


def _handle_ai_comment(comment_id, user_id, user_name, post_id, message, platform, name):
    logger.info("AI comment detected in %s comment %s from %s", platform, comment_id, user_name)
    reply_text = ''
    success = False
    error = ''

    try:
        token = _get_page_token()
        proof = _appsecret_proof(token)
        reply_text = generate_ai_acknowledgment(name=name, comment=message)

        if platform == 'facebook':
            _post_fb_comment(comment_id, reply_text, token, proof)
        elif platform == 'instagram':
            _post_ig_reply(comment_id, reply_text, token, proof)

        success = True
        logger.info("AI acknowledgment sent for %s comment %s", platform, comment_id)
    except Exception as exc:
        error = str(exc)
        logger.error("Failed to send AI acknowledgment for comment %s: %s", comment_id, exc)

    EngagementReply.objects.create(
        comment_id=comment_id, platform=platform, reply_type=_TYPE_AI,
        user_id=user_id or '', user_name=user_name or '',
        post_id=post_id or '', comment_text=message,
        reply_text=reply_text, discount_code='',
        success=success, error=error,
    )


def _handle_natural_comment(comment_id, user_id, user_name, post_id, message, platform, name):
    logger.info("Natural engagement for %s comment %s from %s", platform, comment_id, user_name)
    reply_text = ''
    success = False
    error = ''

    try:
        reply_text = generate_natural_reply(name=name, comment=message)
        if not reply_text:
            logger.info("Claude returned empty natural reply — skipping")
            return

        token = _get_page_token()
        proof = _appsecret_proof(token)

        if platform == 'facebook':
            _post_fb_comment(comment_id, reply_text, token, proof)
        elif platform == 'instagram':
            _post_ig_reply(comment_id, reply_text, token, proof)

        success = True
        logger.info("Natural reply sent for %s comment %s", platform, comment_id)
    except Exception as exc:
        error = str(exc)
        logger.error("Failed to send natural reply for comment %s: %s", comment_id, exc)

    EngagementReply.objects.create(
        comment_id=comment_id, platform=platform, reply_type=_TYPE_NATURAL,
        user_id=user_id or '', user_name=user_name or '',
        post_id=post_id or '', comment_text=message,
        reply_text=reply_text, discount_code='',
        success=success, error=error,
    )


def _first_name(user_name: str) -> str:
    return (user_name or '').split()[0] or 'daar'


def _send_code_reply(platform: str, comment_id: str, name: str, comment_text: str, code: str, keyword: str) -> str:
    token = _get_page_token()
    proof = _appsecret_proof(token)

    if platform == 'facebook':
        text = generate_fb_reply_with_code(name=name, comment=comment_text, code=code, keyword=keyword)
        _post_fb_comment(comment_id, text, token, proof)
        return text
    elif platform == 'instagram':
        text = generate_ig_reply(name=name, comment=comment_text, code=code, keyword=keyword)
        _post_ig_reply(comment_id, text, token, proof)
        return text
    return ''


def _send_no_codes_reply(platform: str, comment_id: str, name: str, comment_text: str) -> str:
    token = _get_page_token()
    proof = _appsecret_proof(token)
    text = generate_no_codes_reply(name=name, comment=comment_text, platform=platform)
    if platform == 'facebook':
        _post_fb_comment(comment_id, text, token, proof)
    elif platform == 'instagram':
        _post_ig_reply(comment_id, text, token, proof)
    return text


def _post_fb_comment(comment_id: str, message: str, token: str, proof: str):
    resp = requests.post(
        f"{GRAPH_API_BASE}/{comment_id}/comments",
        data={"message": message, "access_token": token, "appsecret_proof": proof},
        timeout=15,
    )
    if not resp.ok:
        logger.error("FB comment reply error: %s", resp.text)
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
