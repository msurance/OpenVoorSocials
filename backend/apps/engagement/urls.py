from django.urls import path
from apps.engagement.views import facebook_webhook

urlpatterns = [
    path('webhooks/facebook/', facebook_webhook, name='facebook_webhook'),
]
