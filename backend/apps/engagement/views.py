import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.engagement.services.comment_handler import handle_comment

logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, signature_header: str) -> bool:
    if not signature_header or not signature_header.startswith('sha256='):
        return False
    expected = hmac.new(
        settings.FACEBOOK_APP_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header[7:])


@require_http_methods(['GET', 'POST'])
@csrf_exempt
def facebook_webhook(request):
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        if mode == 'subscribe' and token == settings.WEBHOOK_VERIFY_TOKEN:
            logger.info("Facebook webhook verified successfully")
            return HttpResponse(challenge, content_type='text/plain')
        logger.warning("Facebook webhook verification failed — bad token")
        return HttpResponse(status=403)

    body = request.body
    sig = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
    logger.info("Webhook POST received — sig=%s body_len=%d", sig[:30] if sig else 'NONE', len(body))
    if not _verify_signature(body, sig):
        logger.warning("Facebook webhook signature mismatch — sig=%s", sig[:50] if sig else 'NONE')
        return HttpResponse(status=403)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return HttpResponse(status=400)

    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            field = change.get('field')
            value = change.get('value', {})

            try:
                if field == 'feed' and value.get('item') == 'comment':
                    handle_comment(
                        comment_id=value.get('comment_id', ''),
                        user_id=value.get('from', {}).get('id', ''),
                        user_name=value.get('from', {}).get('name', ''),
                        post_id=value.get('post_id', ''),
                        message=value.get('message', ''),
                        platform='facebook',
                        parent_id=value.get('parent_id', ''),
                    )
                elif field == 'comments':
                    handle_comment(
                        comment_id=value.get('id', ''),
                        user_id=value.get('from', {}).get('id', ''),
                        user_name=value.get('from', {}).get('username', ''),
                        post_id=value.get('media', {}).get('id', ''),
                        message=value.get('text', ''),
                        platform='instagram',
                        parent_id=value.get('parent_id', ''),
                    )
            except Exception as exc:
                logger.exception("Unhandled error processing webhook field=%s: %s", field, exc)

    return JsonResponse({'status': 'ok'})
