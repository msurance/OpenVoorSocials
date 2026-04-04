import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def claim_discount_code(platform: str, user_id: str, comment_id: str) -> str:
    """
    Call the OpenVoor app API to claim a unique discount code.

    OpenVoor app must implement:
      POST /api/discount-codes/claim/
      Headers: X-Api-Key: <OPENVOOR_DISCOUNT_API_KEY>
      Body: {"platform": "...", "user_id": "...", "comment_id": "..."}
      Response 201: {"code": "OPEN-XXXXXX"}
      Response 409: {"error": "already_claimed", "code": "OPEN-XXXXXX"}
    """
    url = f"{settings.OPENVOOR_API_URL}/api/discount-codes/claim/"
    resp = requests.post(
        url,
        json={"platform": platform, "user_id": user_id, "comment_id": comment_id},
        headers={"X-Api-Key": settings.OPENVOOR_DISCOUNT_API_KEY},
        timeout=10,
    )

    if resp.status_code == 409:
        data = resp.json()
        logger.info("User %s already claimed code %s", user_id, data.get('code'))
        return data.get('code', '')

    if not resp.ok:
        logger.error("Discount API error %s: %s", resp.status_code, resp.text)
        resp.raise_for_status()

    return resp.json()['code']
