import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='EngagementReply',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('comment_id', models.CharField(db_index=True, max_length=200, unique=True)),
                ('platform', models.CharField(
                    choices=[('facebook', 'Facebook'), ('instagram', 'Instagram')],
                    max_length=20,
                )),
                ('user_id', models.CharField(max_length=200)),
                ('user_name', models.CharField(blank=True, max_length=200)),
                ('post_id', models.CharField(blank=True, max_length=200)),
                ('discount_code', models.CharField(blank=True, max_length=100)),
                ('replied_at', models.DateTimeField(auto_now_add=True)),
                ('success', models.BooleanField(default=True)),
                ('error', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['-replied_at'],
            },
        ),
    ]
