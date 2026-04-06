from django.db import migrations


def seed(apps, schema_editor):
    apps.get_model('params', 'AppParameter').objects.get_or_create(
        key='content.blind_getrouwd_per_week',
        defaults={
            'value': '4',
            'description': (
                'Aantal posts per week dat het "Blind Getrouwd"-thema krijgt: '
                'AI als expertengroep die jou matcht — net als de experts in de show, '
                'maar dan voor alle categorieën (liefde, vrienden, sport, reizen, ouders). '
                'Stel in op 0 om het thema volledig uit te schakelen.'
            ),
        },
    )


def unseed(apps, schema_editor):
    apps.get_model('params', 'AppParameter').objects.filter(
        key='content.blind_getrouwd_per_week'
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('params', '0005_boost_geo_keys_param'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
