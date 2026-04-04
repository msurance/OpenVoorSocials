from django.db import migrations

DEFAULTS = [
    ('engagement.natural_reply_rate', '25', 'Percentage van gewone comments die een automatische reply krijgen (0-100)'),
    ('engagement.discount_cta_per_week', '3', 'Aantal posts per week dat een discount CTA krijgt toegevoegd'),
    ('engagement.keywords', 'match,openvoor,klaar,korting', 'Kommalijst van keywords die de discount flow triggeren'),
    ('engagement.ai_keywords', 'ai,artificial,chatgpt,robot,nep,fake,gegenereerd,bot,chatbot,automatisch,generated', 'Kommalijst van keywords die de AI-bevestiging triggeren'),
]


def create_defaults(apps, schema_editor):
    AppParameter = apps.get_model('params', 'AppParameter')
    for key, value, description in DEFAULTS:
        AppParameter.objects.get_or_create(key=key, defaults={'value': value, 'description': description})


def reverse_defaults(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('params', '0001_initial')]
    operations = [migrations.RunPython(create_defaults, reverse_defaults)]
