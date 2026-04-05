from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [('params', '0002_default_params')]

    operations = [
        migrations.CreateModel(
            name='AppDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, max_length=100, unique=True)),
                ('title', models.CharField(max_length=200)),
                ('content', models.TextField(blank=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Document',
                'verbose_name_plural': 'Documenten',
                'ordering': ['key'],
            },
        ),
    ]
