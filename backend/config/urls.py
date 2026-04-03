from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import path


def health_check(request):
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False
    return JsonResponse({"status": "ok", "db": db_ok})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check),
]

# Serve media files in development
from django.conf import settings  # noqa: E402

if settings.DEBUG:
    from django.conf.urls.static import static  # noqa: E402

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
