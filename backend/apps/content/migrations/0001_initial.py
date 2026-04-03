import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SocialPost',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('category', models.CharField(
                    choices=[
                        ('love', 'Liefde'),
                        ('friends', 'Vrienden'),
                        ('travel', 'Reizen'),
                        ('sports', 'Sporten'),
                        ('parents', 'Ouders'),
                        ('klusjes', 'Klusjes'),
                        ('all', 'Alles'),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ('platform', models.CharField(
                    choices=[
                        ('facebook', 'Facebook'),
                        ('instagram', 'Instagram'),
                        ('both', 'Beide'),
                    ],
                    db_index=True,
                    default='both',
                    max_length=20,
                )),
                ('status', models.CharField(
                    choices=[
                        ('draft', 'Draft'),
                        ('approved', 'Goedgekeurd'),
                        ('published', 'Gepubliceerd'),
                        ('failed', 'Mislukt'),
                        ('rejected', 'Afgewezen'),
                    ],
                    db_index=True,
                    default='draft',
                    max_length=20,
                )),
                ('copy_nl', models.TextField()),
                ('hashtags', models.TextField(blank=True)),
                ('image_prompt', models.TextField()),
                ('image_path', models.CharField(blank=True, max_length=500)),
                ('scheduled_at', models.DateTimeField(db_index=True)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('facebook_post_id', models.CharField(blank=True, max_length=200)),
                ('instagram_post_id', models.CharField(blank=True, max_length=200)),
                ('error_message', models.TextField(blank=True)),
                ('week_number', models.IntegerField(db_index=True)),
                ('year', models.IntegerField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['scheduled_at'],
            },
        ),
        migrations.AddIndex(
            model_name='socialpost',
            index=models.Index(fields=['status', 'scheduled_at'], name='content_soc_status_sched_idx'),
        ),
        migrations.AddIndex(
            model_name='socialpost',
            index=models.Index(fields=['week_number', 'year'], name='content_soc_week_year_idx'),
        ),
    ]
