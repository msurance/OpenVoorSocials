from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0004_socialpost_discount_cta'),
    ]

    operations = [
        migrations.AddField(
            model_name='socialpost',
            name='boost_status',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='socialpost',
            name='boost_campaign_id',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='socialpost',
            name='boost_ad_set_id',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='socialpost',
            name='boost_ad_id',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='socialpost',
            name='boost_daily_budget_eur',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True),
        ),
        migrations.AddField(
            model_name='socialpost',
            name='boost_end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='socialpost',
            name='boost_reach',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='socialpost',
            name='boost_spend_eur',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True),
        ),
    ]
