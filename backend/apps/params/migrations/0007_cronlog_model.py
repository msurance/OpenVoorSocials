import uuid
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('params', '0006_blind_getrouwd_param'),
    ]

    operations = [
        migrations.CreateModel(
            name='CronLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('ran_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('posts_due', models.IntegerField(default=0)),
                ('posts_published', models.IntegerField(default=0)),
                ('posts_failed', models.IntegerField(default=0)),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'Cron run',
                'verbose_name_plural': 'Cron runs',
                'ordering': ['-ran_at'],
            },
        ),
    ]
