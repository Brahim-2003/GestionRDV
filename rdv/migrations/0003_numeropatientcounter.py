from django.db import migrations, models


def create_singleton_counter(apps, schema_editor):
    """
    Garantit que la ligne du compteur (pk=1) existe toujours, pour que
    generate_next_numero_patient() puisse la verrouiller sans avoir à la
    créer à la volée (et donc sans race condition possible sur sa création).
    """
    NumeroPatientCounter = apps.get_model('rdv', 'NumeroPatientCounter')
    NumeroPatientCounter.objects.get_or_create(pk=1, defaults={'last_number': 0})


def delete_singleton_counter(apps, schema_editor):
    NumeroPatientCounter = apps.get_model('rdv', 'NumeroPatientCounter')
    NumeroPatientCounter.objects.filter(pk=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('rdv', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='NumeroPatientCounter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_number', models.PositiveIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Compteur numéro patient',
                'verbose_name_plural': 'Compteur numéro patient',
            },
        ),
        migrations.RunPython(create_singleton_counter, delete_singleton_counter),
    ]
