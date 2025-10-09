# rdv/management/commands/init_periodic_tasks.py - VERSION AMÉLIORÉE
from django.core.management.base import BaseCommand
from django.db import transaction
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
from django.conf import settings


class Command(BaseCommand):
    help = "Initialise les tâches périodiques Celery Beat (version robuste avec timezone)"

    def ensure_single_crontab(self, **schedule_kwargs):
        """Retourne un seul CrontabSchedule correspondant aux kwargs."""
        qs = CrontabSchedule.objects.filter(**schedule_kwargs).order_by('id')
        if qs.exists():
            kept = qs.first()
            duplicates = list(qs[1:])
            if duplicates:
                for dup in duplicates:
                    PeriodicTask.objects.filter(crontab=dup).update(crontab=kept)
                    dup.delete()
            return kept
        return CrontabSchedule.objects.create(**schedule_kwargs)

    def ensure_single_interval(self, every, period):
        """Retourne un seul IntervalSchedule."""
        qs = IntervalSchedule.objects.filter(every=every, period=period).order_by('id')
        if qs.exists():
            kept = qs.first()
            duplicates = list(qs[1:])
            if duplicates:
                for dup in duplicates:
                    PeriodicTask.objects.filter(interval=dup).update(interval=kept)
                    dup.delete()
            return kept
        return IntervalSchedule.objects.create(every=every, period=period)

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Initialisation des tâches périodiques ===\n'))

        # Déterminer le timezone à utiliser
        celery_tz = getattr(settings, 'CELERY_TIMEZONE', 'UTC')
        self.stdout.write(f"Timezone Celery: {celery_tz}\n")

        # Créer les intervals
        schedule_2min = self.ensure_single_interval(every=2, period=IntervalSchedule.MINUTES)
        schedule_10min = self.ensure_single_interval(every=10, period=IntervalSchedule.MINUTES)
        schedule_30min = self.ensure_single_interval(every=30, period=IntervalSchedule.MINUTES)
        schedule_1hour = self.ensure_single_interval(every=1, period=IntervalSchedule.HOURS)

        # Tâches avec interval
        interval_tasks = [
            {
                'name': 'auto-start-rdv',
                'task': 'rdv.tasks.auto_start_rdv',
                'interval': schedule_2min,  # ← Changé de 5min à 2min (plus précis)
                'description': "Démarre les RDV confirmés à l'heure (toutes les 2 min)",
            },
            {
                'name': 'auto-cancel-expired-rdv',
                'task': 'rdv.tasks.auto_cancel_expired_rdv',
                'interval': schedule_10min,  # ← Changé de 5min à 10min (moins critique)
                'description': "Annule automatiquement les RDV expirés toutes les 10 minutes",
            },
            {
                'name': 'auto-complete-rdv',
                'task': 'rdv.tasks.auto_complete_rdv',
                'interval': schedule_10min,  # ← Changé de 5min à 10min (pas urgent)
                'description': "Termine les RDV en cours après leur durée",
            },
            {
                'name': 'send-rdv-reminder-2h',
                'task': 'rdv.tasks.send_rdv_reminder_2h',
                'interval': schedule_10min,  # ← Changé de 30min à 10min (plus efficace)
                'description': "Envoie des rappels 2h avant les RDV",
            },
            {
                'name': 'send-rdv-reminder-24h',
                'task': 'rdv.tasks.send_rdv_reminder_24h',
                'interval': schedule_1hour,  # ← Reste à 1h (OK)
                'description': "Envoie des rappels 24h avant les RDV",
            },
        ]
        # Tâches avec crontab - CORRECTION: Utiliser le timezone de Celery
        crontab_tasks = [
            {
                'name': 'alert-unconfirmed-rdv',
                'task': 'rdv.tasks.alert_unconfirmed_rdv_to_doctors',
                'schedule': {
                    'minute': '0',
                    'hour': '8',
                    'day_of_week': '*',
                    'day_of_month': '*',
                    'month_of_year': '*',
                    'timezone': celery_tz  # IMPORTANT: Utiliser le timezone de Celery
                },
                'description': "Alerte médecins pour RDV non confirmés dans 48h (8h)",
            },
            {
                'name': 'send-weekly-stats-doctors',
                'task': 'rdv.tasks.send_weekly_stats_to_doctors',
                'schedule': {
                    'minute': '0',
                    'hour': '9',
                    'day_of_week': '1',
                    'day_of_month': '*',
                    'month_of_year': '*',
                    'timezone': celery_tz
                },
                'description': "Envoie stats hebdomadaires aux médecins (Lundi 9h)",
            },
            {
                'name': 'check-high-cancellation-rate',
                'task': 'rdv.tasks.check_high_cancellation_rate',
                'schedule': {
                    'minute': '0',
                    'hour': '8',
                    'day_of_week': '1',
                    'day_of_month': '*',
                    'month_of_year': '*',
                    'timezone': celery_tz
                },
                'description': "Vérifie le taux d'annulation (Lundi 8h)",
            },
            {
                'name': 'cleanup-old-notifications',
                'task': 'rdv.tasks.cleanup_old_notifications',
                'schedule': {
                    'minute': '0',
                    'hour': '3',
                    'day_of_week': '*',
                    'day_of_month': '*',
                    'month_of_year': '*',
                    'timezone': celery_tz
                },
                'description': "Nettoie les notifications anciennes (3h du matin)",
            },
            {
                'name': 'generate-daily-stats-report',
                'task': 'rdv.tasks.generate_daily_stats_report',
                'schedule': {
                    'minute': '0',
                    'hour': '7',
                    'day_of_week': '*',
                    'day_of_month': '*',
                    'month_of_year': '*',
                    'timezone': celery_tz
                },
                'description': "Génère le rapport quotidien (7h du matin)",
            },
            {
                'name': 'cleanup-inactive-users',
                'task': 'users.tasks.cleanup_inactive_users',
                'schedule': {
                    'minute': '0',
                    'hour': '2',
                    'day_of_week': '0',
                    'day_of_month': '*',
                    'month_of_year': '*',
                    'timezone': celery_tz
                },
                'description': "Nettoie les utilisateurs inactifs (Dimanche 2h)",
            },
            {
                'name': 'send-birthday-wishes',
                'task': 'users.tasks.send_birthday_wishes',
                'schedule': {
                    'minute': '0',
                    'hour': '9',
                    'day_of_week': '*',
                    'day_of_month': '*',
                    'month_of_year': '*',
                    'timezone': celery_tz
                },
                'description': "Envoie les messages d'anniversaire (9h)",
            },
        ]

        created_count = 0
        updated_count = 0
        errors = []

        # Traiter les tâches interval
        for cfg in interval_tasks:
            try:
                with transaction.atomic():
                    defaults = {
                        'task': cfg['task'],
                        'interval': cfg['interval'],
                        'crontab': None,
                        'enabled': True,
                        'description': cfg.get('description', ''),
                    }
                    task_obj, created = PeriodicTask.objects.update_or_create(
                        name=cfg['name'],
                        defaults=defaults
                    )

                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Créée: {cfg['name']}"))
                else:
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f"  ↻ Mise à jour: {cfg['name']}"))

            except Exception as exc:
                errors.append(f"{cfg['name']}: {str(exc)}")
                self.stdout.write(self.style.ERROR(f"  ✗ Erreur: {cfg['name']} - {str(exc)}"))

        # Traiter les tâches crontab
        for cfg in crontab_tasks:
            try:
                schedule_kwargs = {
                    'minute': cfg['schedule'].get('minute', '*'),
                    'hour': cfg['schedule'].get('hour', '*'),
                    'day_of_week': cfg['schedule'].get('day_of_week', '*'),
                    'day_of_month': cfg['schedule'].get('day_of_month', '*'),
                    'month_of_year': cfg['schedule'].get('month_of_year', '*'),
                    'timezone': cfg['schedule'].get('timezone', celery_tz),
                }

                with transaction.atomic():
                    schedule = self.ensure_single_crontab(**schedule_kwargs)

                    defaults = {
                        'task': cfg['task'],
                        'crontab': schedule,
                        'interval': None,
                        'enabled': True,
                        'description': cfg.get('description', ''),
                    }

                    task_obj, created = PeriodicTask.objects.update_or_create(
                        name=cfg['name'],
                        defaults=defaults
                    )

                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Créée: {cfg['name']}"))
                else:
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f"  ↻ Mise à jour: {cfg['name']}"))

            except Exception as exc:
                errors.append(f"{cfg['name']}: {str(exc)}")
                self.stdout.write(self.style.ERROR(f"  ✗ Erreur: {cfg['name']} - {str(exc)}"))

        # Résumé
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'Tâches créées: {created_count}'))
        self.stdout.write(self.style.WARNING(f'Tâches mises à jour: {updated_count}'))

        if errors:
            self.stdout.write(self.style.ERROR(f'Erreurs: {len(errors)}'))
            for e in errors:
                self.stdout.write(self.style.ERROR(f'  - {e}'))
        else:
            self.stdout.write(self.style.SUCCESS('Aucune erreur'))

        self.stdout.write('='*50 + '\n')
        self.stdout.write(self.style.SUCCESS(
            '\nLes tâches périodiques sont configurées!\n'
            'Pour les voir: http://localhost:8000/admin/django_celery_beat/periodictask/\n'
            'Redémarrez Celery Beat pour appliquer les changements:\n'
            '  docker-compose restart beat\n'
        ))