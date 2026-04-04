from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0003_socialpost_reel_ids'),
    ]
    operations = [
        migrations.AddField(
            model_name='socialpost',
            name='discount_cta',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
