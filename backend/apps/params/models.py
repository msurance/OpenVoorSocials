import uuid

from django.db import models


class CronLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ran_at = models.DateTimeField(auto_now_add=True, db_index=True)
    posts_due = models.IntegerField(default=0)
    posts_published = models.IntegerField(default=0)
    posts_failed = models.IntegerField(default=0)
    notes = models.TextField(blank=True)  # errors, warnings, or "no posts due"

    class Meta:
        ordering = ['-ran_at']
        verbose_name = 'Cron run'
        verbose_name_plural = 'Cron runs'

    def __str__(self):
        return f"{self.ran_at:%Y-%m-%d %H:%M} — due:{self.posts_due} pub:{self.posts_published} fail:{self.posts_failed}"


class AppParameter(models.Model):
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'Parameter'
        verbose_name_plural = 'Parameters'

    def __str__(self):
        return f"{self.key} = {self.value}"


class AppDocument(models.Model):
    key = models.CharField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key']
        verbose_name = 'Document'
        verbose_name_plural = 'Documenten'

    def __str__(self):
        return self.title
