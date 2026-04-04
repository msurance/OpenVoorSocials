from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='socialpost',
            name='video_path',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
