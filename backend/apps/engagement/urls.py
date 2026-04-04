from django.urls import path
from apps.engagement.views import facebook_webhook, webhook_test

urlpatterns = [
    path('webhooks/facebook/', facebook_webhook, name='facebook_webhook'),
    path('webhooks/test/', webhook_test, name='webhook_test'),
]
