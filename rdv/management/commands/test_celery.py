# rdv/management/commands/test_celery.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


from rdv.models import RendezVous, Patient, Medecin

from rdv.tasks import (
    auto_cancel_expired_rdv,
    auto_start_rdv,
    auto_complete_rdv,
    send_rdv_reminder_24h,
    check_high_cancellation_rate,
    cleanup_old_notifications
)
from users.tasks import (
    notify_admins_on_user_create,
    cleanup_inactive_users,
    send_birthday_wishes
)


class Command(BaseCommand):
    help = 'Teste les tâches Celery manuellement'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            help='Nom de la tâche à exécuter',
            choices=[
                'cancel_expired',
                'start_rdv',
                'complete_rdv',
                'reminder_24h',
                'check_cancellation',
                'cleanup_notifs',
                'cleanup_users',
                'birthday',
                'all'
            ],
        )
        parser.add_argument(
            '--async',
            action='store_true',
            help='Exécuter la tâche de manière asynchrone (via Celery)',
        )

    def handle(self, *args, **options):
        task_name = options.get('task', 'all')
        use_async = options.get('async', False)

        self.stdout.write(self.style.SUCCESS(f'\n=== Test des tâches Celery ==='))
        self.stdout.write(f'Mode: {"Asynchrone (Celery)" if use_async else "Synchrone (Direct)"}\n')

        tasks_map = {
            'cancel_expired': ('Annulation RDV expirés', auto_cancel_expired_rdv),
            'start_rdv': ('Démarrage RDV', auto_start_rdv),
            'complete_rdv': ('Finalisation RDV', auto_complete_rdv),
            'reminder_24h': ('Rappels 24h', send_rdv_reminder_24h),
            'check_cancellation': ('Vérification taux annulation', check_high_cancellation_rate),
            'cleanup_notifs': ('Nettoyage notifications', cleanup_old_notifications),
            'cleanup_users': ('Nettoyage utilisateurs inactifs', cleanup_inactive_users),
            'birthday': ('Messages anniversaire', send_birthday_wishes),
        }

        if task_name == 'all':
            tasks_to_run = tasks_map.items()
        else:
            tasks_to_run = [(task_name, tasks_map[task_name])]

        for task_key, (description, task_func) in tasks_to_run:
            self.stdout.write(f'\n▶ Exécution: {description}')
            
            try:
                if use_async:
                    result = task_func.delay()
                    self.stdout.write(self.style.WARNING(f'  Task ID: {result.id}'))
                    self.stdout.write(self.style.WARNING(f'  Statut: En cours (asynchrone)'))
                else:
                    result = task_func()
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Résultat: {result}'))
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Erreur: {str(e)}'))

        self.stdout.write(self.style.SUCCESS('\n=== Tests terminés ===\n'))


# rdv/management/commands/create_test_rdv.py

class Command(BaseCommand):
    help = 'Crée des RDV de test pour tester les tâches automatiques'

    def add_arguments(self, parser):
        parser.add_argument(
            '--expired',
            action='store_true',
            help='Créer des RDV expirés (pour test annulation auto)',
        )
        parser.add_argument(
            '--starting',
            action='store_true',
            help='Créer des RDV qui commencent maintenant (pour test démarrage)',
        )
        parser.add_argument(
            '--completing',
            action='store_true',
            help='Créer des RDV en cours depuis 30min (pour test finalisation)',
        )
        parser.add_argument(
            '--reminder',
            action='store_true',
            help='Créer des RDV dans 24h (pour test rappel)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Création de RDV de test ===\n'))

        # Récupérer premier patient et médecin
        try:
            patient = Patient.objects.first()
            medecin = Medecin.objects.first()
            
            if not patient or not medecin:
                self.stdout.write(self.style.ERROR('Aucun patient ou médecin trouvé !'))
                return
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erreur: {e}'))
            return

        now = timezone.now()
        created = []

        # RDV expirés
        if options['expired']:
            rdv = RendezVous.objects.create(
                patient=patient,
                medecin=medecin,
                date_heure_rdv=now - timedelta(hours=2),
                statut='programme',
                motif='Test RDV expiré'
            )
            created.append(f'RDV #{rdv.id} expiré (programmé il y a 2h)')

        # RDV qui commencent
        if options['starting']:
            rdv = RendezVous.objects.create(
                patient=patient,
                medecin=medecin,
                date_heure_rdv=now,
                statut='confirme',
                motif='Test démarrage RDV'
            )
            created.append(f'RDV #{rdv.id} qui commence maintenant')

        # RDV à compléter
        if options['completing']:
            rdv = RendezVous.objects.create(
                patient=patient,
                medecin=medecin,
                date_heure_rdv=now - timedelta(minutes=35),
                statut='en_cours',
                motif='Test finalisation RDV'
            )
            created.append(f'RDV #{rdv.id} en cours depuis 35min')

        # RDV pour rappel
        if options['reminder']:
            rdv = RendezVous.objects.create(
                patient=patient,
                medecin=medecin,
                date_heure_rdv=now + timedelta(hours=24),
                statut='confirme',
                motif='Test rappel 24h'
            )
            created.append(f'RDV #{rdv.id} dans 24h')

        if created:
            self.stdout.write(self.style.SUCCESS('\nRDV créés:'))
            for msg in created:
                self.stdout.write(f'  ✓ {msg}')
        else:
            self.stdout.write(self.style.WARNING('Aucun RDV créé (utilisez les options --expired, --starting, etc.)'))

        self.stdout.write(self.style.SUCCESS('\n=== Terminé ===\n'))