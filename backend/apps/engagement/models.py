import uuid
from django.db import models


class EngagementReply(models.Model):
    PLATFORM_CHOICES = [('facebook', 'Facebook'), ('instagram', 'Instagram')]
    TYPE_CHOICES = [
        ('discount', 'Kortingscode'),
        ('ai_acknowledgment', 'AI reactie'),
        ('natural', 'Natuurlijk engagement'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment_id = models.CharField(max_length=200, unique=True, db_index=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    reply_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='discount', db_index=True)
    user_id = models.CharField(max_length=200)
    user_name = models.CharField(max_length=200, blank=True)
    post_id = models.CharField(max_length=200, blank=True)
    comment_text = models.TextField(blank=True)
    reply_text = models.TextField(blank=True)
    discount_code = models.CharField(max_length=100, blank=True)
    replied_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['-replied_at']

    def __str__(self):
        return f"{self.get_platform_display()} — {self.user_name} — {self.get_reply_type_display()}"
