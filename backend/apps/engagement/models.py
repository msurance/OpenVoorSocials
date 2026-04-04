import uuid
from django.db import models


class EngagementReply(models.Model):
    PLATFORM_CHOICES = [('facebook', 'Facebook'), ('instagram', 'Instagram')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment_id = models.CharField(max_length=200, unique=True, db_index=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    user_id = models.CharField(max_length=200)
    user_name = models.CharField(max_length=200, blank=True)
    post_id = models.CharField(max_length=200, blank=True)
    discount_code = models.CharField(max_length=100, blank=True)
    replied_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['-replied_at']

    def __str__(self):
        return f"{self.platform} — {self.user_name} — {self.discount_code or 'no code'}"
