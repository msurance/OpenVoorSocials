import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_TTL = 60  # seconds


def get_param(key: str, default=None):
    """
    Fetch a parameter value from DB (cached 60s).
    Returns the value cast to the same type as `default` if default is int/float/bool.
    Falls back to `default` if the key doesn't exist or DB is unavailable.
    """
    cache_key = f"appparam:{key}"
    cached = cache.get(cache_key)
    if cached is not None:
        return _cast(cached, default)

    try:
        from apps.params.models import AppParameter
        obj = AppParameter.objects.filter(key=key).first()
        if obj is None:
            return default
        cache.set(cache_key, obj.value, _CACHE_TTL)
        return _cast(obj.value, default)
    except Exception as exc:
        logger.warning("get_param('%s') failed, using default: %s", key, exc)
        return default


def get_document(key: str) -> str:
    """
    Fetch an AppDocument's content by key (cached 5 minutes).
    Returns empty string if not found or DB unavailable.
    """
    cache_key = f"appdoc:{key}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from apps.params.models import AppDocument
        obj = AppDocument.objects.filter(key=key).first()
        content = obj.content if obj else ''
        cache.set(cache_key, content, 300)
        return content
    except Exception as exc:
        logger.warning("get_document('%s') failed: %s", key, exc)
        return ''


def _cast(value: str, default):
    if isinstance(default, bool):
        return value.lower() in ('1', 'true', 'yes')
    if isinstance(default, int):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    if isinstance(default, float):
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    return value
