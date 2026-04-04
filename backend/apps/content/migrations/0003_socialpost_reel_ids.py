from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0002_socialpost_video_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='socialpost',
            name='facebook_reel_id',
            field=models.CharField(blank=True, default='', max_length=200),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='socialpost',
            name='instagram_reel_id',
            field=models.CharField(blank=True, default='', max_length=200),
            preserve_default=False,
        ),
    ]
