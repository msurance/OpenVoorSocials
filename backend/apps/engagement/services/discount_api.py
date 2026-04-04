import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class NoCodesAvailable(Exception):
    pass


def claim_discount_code(platform: str, user_id: str, comment_id: str) -> str:
    """
    Call the OpenVoor app API to claim a unique discount code.

    201 {"code": "OPEN-ABC123"}           → new code, return it
    409 {"error": "already_claimed", ...} → user already has this code, return it
    404 {"error": "no_codes_available"}   → pool empty, raises NoCodesAvailable
    401                                   → bad API key, raises HTTPError
    """
    url = f"{settings.OPENVOOR_API_URL}/api/discount-codes/claim/"
    resp = requests.post(
        url,
        json={"platform": platform, "user_id": user_id, "comment_id": comment_id},
        headers={"X-Api-Key": settings.OPENVOOR_DISCOUNT_API_KEY},
        timeout=10,
    )

    if resp.status_code in (201, 409):
        code = resp.json().get('code', '')
        if resp.status_code == 409:
            logger.info("User %s already claimed code %s", user_id, code)
        return code

    if resp.status_code == 404:
        logger.warning("No discount codes available (pool empty)")
        raise NoCodesAvailable()

    logger.error("Discount API error %s: %s", resp.status_code, resp.text)
    resp.raise_for_status()
