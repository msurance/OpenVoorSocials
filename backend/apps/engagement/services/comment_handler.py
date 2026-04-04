import logging
import requests
from django.conf import settings
from apps.engagement.models import EngagementReply
from apps.engagement.services.discount_api import claim_discount_code, NoCodesAvailable
from apps.publishing.services.facebook_publisher import _get_page_token, _appsecret_proof, GRAPH_API_BASE

logger = logging.getLogger(__name__)

_FB_CODE_REPLY = (
    "Bedankt voor je reactie, {name}! \U0001f389 "
    "Hier is jouw unieke kortingscode: {code}\n"
    "Voer deze in op https://openvoor.app om je account te activeren. Veel succes!"
)

_IG_CODE_REPLY = (
    "Bedankt {name}! \U0001f389 Jouw kortingscode: {code} \u2014 "
    "voer hem in op https://openvoor.app om je account te activeren!"
)

_FB_NO_CODES_REPLY = (
    "Bedankt voor je reactie, {name}! Helaas zijn alle kortingscodes al geclaimd. "
    "Volg onze pagina voor de volgende actie!"
)

_IG_NO_CODES_REPLY = (
    "Bedankt {name}! Helaas zijn alle codes al geclaimd \u2014 volg ons voor de volgende actie!"
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
    no_codes = False

    try:
        code = claim_discount_code(platform=platform, user_id=user_id, comment_id=comment_id)
        _send_code_reply(platform=platform, comment_id=comment_id, user_name=user_name, code=code)
        success = True
        logger.info("Replied to %s comment %s with code %s", platform, comment_id, code)
    except NoCodesAvailable:
        no_codes = True
        error = 'no_codes_available'
        logger.warning("No codes available — sending sorry reply to %s comment %s", platform, comment_id)
        try:
            _send_no_codes_reply(platform=platform, comment_id=comment_id, user_name=user_name)
            success = True  # reply was sent, even if no code
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


def _send_code_reply(platform: str, comment_id: str, user_name: str, code: str):
    token = _get_page_token()
    proof = _appsecret_proof(token)
    name = _first_name(user_name)

    if platform == 'facebook':
        text = _FB_CODE_REPLY.format(name=name, code=code)
        _post_fb_comment(comment_id, text, token, proof)
    elif platform == 'instagram':
        text = _IG_CODE_REPLY.format(name=name, code=code)
        _post_ig_reply(comment_id, text, token, proof)


def _send_no_codes_reply(platform: str, comment_id: str, user_name: str):
    token = _get_page_token()
    proof = _appsecret_proof(token)
    name = _first_name(user_name)

    if platform == 'facebook':
        text = _FB_NO_CODES_REPLY.format(name=name)
        _post_fb_comment(comment_id, text, token, proof)
    elif platform == 'instagram':
        text = _IG_NO_CODES_REPLY.format(name=name)
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


def _post_ig_reply(comment_id: str, message: str, token: str, proof: str):
    resp = requests.post(
        f"{GRAPH_API_BASE}/{comment_id}/replies",
        data={"message": message, "access_token": token, "appsecret_proof": proof},
        timeout=15,
    )
    if not resp.ok:
        logger.error("IG comment reply error: %s", resp.text)
    resp.raise_for_status()
