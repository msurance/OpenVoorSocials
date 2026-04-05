from django.db import models


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
