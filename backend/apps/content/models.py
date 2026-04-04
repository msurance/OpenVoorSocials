import uuid

from django.conf import settings
from django.db import models


class SocialPost(models.Model):
    CATEGORY_CHOICES = [
        ('love', 'Liefde'),
        ('friends', 'Vrienden'),
        ('travel', 'Reizen'),
        ('sports', 'Sporten'),
        ('parents', 'Ouders'),
        ('all', 'Alles'),
    ]
    PLATFORM_CHOICES = [
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('both', 'Beide'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Goedgekeurd'),
        ('published', 'Gepubliceerd'),
        ('failed', 'Mislukt'),
        ('rejected', 'Afgewezen'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='both', db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True)
    copy_nl = models.TextField()
    hashtags = models.TextField(blank=True)
    image_prompt = models.TextField()
    image_path = models.CharField(max_length=500, blank=True)
    video_path = models.CharField(max_length=500, blank=True, default='')
    discount_cta = models.BooleanField(default=False, db_index=True)
    scheduled_at = models.DateTimeField(db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    facebook_post_id = models.CharField(max_length=200, blank=True)
    facebook_reel_id = models.CharField(max_length=200, blank=True)
    instagram_post_id = models.CharField(max_length=200, blank=True)
    instagram_reel_id = models.CharField(max_length=200, blank=True)
    error_message = models.TextField(blank=True)
    week_number = models.IntegerField(db_index=True)
    year = models.IntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_at']
        indexes = [
            models.Index(fields=['status', 'scheduled_at']),
            models.Index(fields=['week_number', 'year']),
        ]

    def __str__(self):
        return (
            f"{self.get_category_display()} — "
            f"{self.scheduled_at:%d/%m/%Y %H:%M} "
            f"({self.get_status_display()})"
        )

    @property
    def image_url(self):
        if not self.image_path:
            return None
        return f"{settings.BASE_URL}{settings.MEDIA_URL}{self.image_path}"

    @property
    def video_url(self):
        if not self.video_path:
            return None
        return f"{settings.BASE_URL}{settings.MEDIA_URL}{self.video_path}"
