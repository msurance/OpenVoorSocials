from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('engagement', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='engagementreply',
            name='comment_text',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='engagementreply',
            name='reply_text',
            field=models.TextField(blank=True, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='engagementreply',
            name='reply_type',
            field=models.CharField(
                choices=[
                    ('discount', 'Kortingscode'),
                    ('ai_acknowledgment', 'AI reactie'),
                    ('natural', 'Natuurlijk engagement'),
                ],
                db_index=True,
                default='discount',
                max_length=20,
            ),
            preserve_default=False,
        ),
    ]
