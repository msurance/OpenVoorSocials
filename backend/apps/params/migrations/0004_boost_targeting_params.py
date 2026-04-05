from django.db import migrations


BOOST_PARAMS = [
    (
        'boost.geo_key',
        '172915',
        'Facebook geo key for the target city. Find keys at: '
        'https://graph.facebook.com/v21.0/search?type=adgeolocation&q=CityName',
    ),
    (
        'boost.geo_name',
        'Brugge',
        'Display name of the target city (informational only).',
    ),
    (
        'boost.radius_km',
        '10',
        'Radius around the target city in kilometres (e.g. 10).',
    ),
    (
        'boost.age_min',
        '25',
        'Minimum age for ad targeting (e.g. 25).',
    ),
    (
        'boost.age_max',
        '65',
        'Maximum age for ad targeting. Facebook cap is 65, which means "65 and older" (covers up to 90+).',
    ),
]


def seed(apps, schema_editor):
    AppParameter = apps.get_model('params', 'AppParameter')
    for key, value, description in BOOST_PARAMS:
        AppParameter.objects.get_or_create(
            key=key,
            defaults={'value': value, 'description': description},
        )


def unseed(apps, schema_editor):
    AppParameter = apps.get_model('params', 'AppParameter')
    AppParameter.objects.filter(key__in=[k for k, _, _ in BOOST_PARAMS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('params', '0003_appdocument'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
