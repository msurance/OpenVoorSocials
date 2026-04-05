from django.db import migrations


def seed(apps, schema_editor):
    AppParameter = apps.get_model('params', 'AppParameter')
    AppParameter.objects.get_or_create(
        key='boost.geo_keys',
        defaults={
            'value': '172915,173785,177675,178283,181937',
            'description': (
                'Comma-separated Facebook city geo keys for ad targeting. '
                'Default covers Brugge (172915), Damme (173785), Jabbeke (177675), '
                'Knokke (178283), Oostende (181937). '
                'Find keys at: https://graph.facebook.com/v21.0/search?type=adgeolocation&q=CityName'
            ),
        },
    )


def unseed(apps, schema_editor):
    apps.get_model('params', 'AppParameter').objects.filter(key='boost.geo_keys').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('params', '0004_boost_targeting_params'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
