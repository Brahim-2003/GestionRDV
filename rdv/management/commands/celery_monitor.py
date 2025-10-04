# rdv/management/commands/celery_monitor.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django_celery_beat.models import PeriodicTask
from rdv.models import RendezVous, Notification
from users.models import Utilisateur
import time
import os


class Command(BaseCommand):
    help = 'Dashboard de monitoring des tâches Celery'

    def add_arguments(self, parser):
        parser.add_argument(
            '--refresh',
            type=int,
            default=5,
            help='Intervalle de rafraîchissement en secondes (0 = pas de rafraîchissement)',
        )

    def clear_screen(self):
        """Efface l'écran selon l'OS"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def get_rdv_stats(self):
        """Statistiques des RDV"""
        now = timezone.now()
        today = now.date()
        
        return {
            'total': RendezVous.objects.count(),
            'aujourd_hui': RendezVous.objects.filter(date_heure_rdv__date=today).count(),
            'en_cours': RendezVous.objects.filter(statut='en_cours').count(),
            'programmes': RendezVous.objects.filter(statut='programme').count(),
            'confirmes': RendezVous.objects.filter(statut='confirme').count(),
            'expires': RendezVous.objects.filter(
                statut='programme',
                date_heure_rdv__lt=now
            ).count(),
            'a_terminer': RendezVous.objects.filter(
                statut='en_cours',
                date_heure_rdv__lt=now - timedelta(minutes=30)
            ).count(),
        }

    def get_notification_stats(self):
        """Statistiques des notifications"""
        return {
            'total': Notification.objects.count(),
            'non_lues': Notification.objects.filter(is_read=False).count(),
            'aujourd_hui': Notification.objects.filter(
                date_envoi__date=timezone.now().date()
            ).count(),
        }

    def get_task_stats(self):
        """Statistiques des tâches périodiques"""
        return {
            'total': PeriodicTask.objects.count(),
            'actives': PeriodicTask.objects.filter(enabled=True).count(),
            'inactives': PeriodicTask.objects.filter(enabled=False).count(),
        }

    def get_user_stats(self):
        """Statistiques utilisateurs"""
        return {
            'total': Utilisateur.objects.count(),
            'actifs': Utilisateur.objects.filter(is_actif=True).count(),
            'patients': Utilisateur.objects.filter(role='patient').count(),
            'medecins': Utilisateur.objects.filter(role='medecin').count(),
            'admins': Utilisateur.objects.filter(role='admin').count(),
        }

    def get_celery_status(self):
        """État de Celery"""
        try:
            from GestionRDV.celery import app
            inspect = app.control.inspect()
            
            active = inspect.active()
            stats = inspect.stats()
            
            if active is None:
                return {'status': 'offline', 'workers': 0, 'tasks': 0}
            
            worker_count = len(active)
            active_tasks = sum(len(tasks) for tasks in active.values())
            
            return {
                'status': 'online',
                'workers': worker_count,
                'tasks': active_tasks
            }
        except Exception:
            return {'status': 'error', 'workers': 0, 'tasks': 0}

    def display_dashboard(self):
        """Affiche le dashboard"""
        self.clear_screen()
        
        # En-tête
        print("╔" + "═"*78 + "╗")
        print("║" + " "*20 + "DASHBOARD CELERY - GESTION RDV" + " "*28 + "║")
        print("║" + " "*20 + timezone.now().strftime("%d/%m/%Y %H:%M:%S") + " "*33 + "║")
        print("╚" + "═"*78 + "╝\n")

        # État Celery
        celery = self.get_celery_status()
        status_color = {
            'online': '\033[92m',  # Vert
            'offline': '\033[91m',  # Rouge
            'error': '\033[93m'  # Jaune
        }
        color = status_color.get(celery['status'], '\033[0m')
        
        print("┌─ ÉTAT CELERY " + "─"*64)
        print(f"│ Statut : {color}{celery['status'].upper()}\033[0m")
        print(f"│ Workers actifs : {celery['workers']}")
        print(f"│ Tâches en cours : {celery['tasks']}")
        print("└" + "─"*78 + "\n")

        # Statistiques RDV
        rdv = self.get_rdv_stats()
        print("┌─ RENDEZ-VOUS " + "─"*64)
        print(f"│ Total : {rdv['total']}")
        print(f"│ Aujourd'hui : {rdv['aujourd_hui']}")
        print(f"│ En cours : \033[93m{rdv['en_cours']}\033[0m")
        print(f"│ Programmés : {rdv['programmes']}")
        print(f"│ Confirmés : {rdv['confirmes']}")
        
        if rdv['expires'] > 0:
            print(f"│ \033[91m⚠ À annuler (expirés) : {rdv['expires']}\033[0m")
        if rdv['a_terminer'] > 0:
            print(f"│ \033[93m⚠ À terminer (>30min) : {rdv['a_terminer']}\033[0m")
        
        print("└" + "─"*78 + "\n")

        # Statistiques Notifications
        notif = self.get_notification_stats()
        print("┌─ NOTIFICATIONS " + "─"*62)
        print(f"│ Total : {notif['total']}")
        print(f"│ Non lues : \033[93m{notif['non_lues']}\033[0m")
        print(f"│ Aujourd'hui : {notif['aujourd_hui']}")
        print("└" + "─"*78 + "\n")

        # Statistiques Tâches
        tasks = self.get_task_stats()
        print("┌─ TÂCHES PÉRIODIQUES " + "─"*57)
        print(f"│ Total : {tasks['total']}")
        print(f"│ Actives : \033[92m{tasks['actives']}\033[0m")
        print(f"│ Inactives : {tasks['inactives']}")
        print("└" + "─"*78 + "\n")

        # Statistiques Utilisateurs
        users = self.get_user_stats()
        print("┌─ UTILISATEURS " + "─"*63)
        print(f"│ Total : {users['total']} (Actifs: {users['actifs']})")
        print(f"│ Patients : {users['patients']} | Médecins : {users['medecins']} | Admins : {users['admins']}")
        print("└" + "─"*78 + "\n")

        # Dernières tâches
        recent_tasks = PeriodicTask.objects.filter(
            enabled=True
        ).order_by('-last_run_at')[:5]
        
        if recent_tasks:
            print("┌─ DERNIÈRES EXÉCUTIONS " + "─"*55)
            for task in recent_tasks:
                if task.last_run_at:
                    time_ago = timezone.now() - task.last_run_at
                    minutes = int(time_ago.total_seconds() / 60)
                    print(f"│ {task.name[:40]:<40} il y a {minutes}min")
            print("└" + "─"*78 + "\n")

    def handle(self, *args, **options):
        refresh_interval = options['refresh']
        
        if refresh_interval == 0:
            # Une seule fois
            self.display_dashboard()
        else:
            # Boucle de rafraîchissement
            self.stdout.write(
                self.style.SUCCESS(
                    f'Dashboard démarré (rafraîchissement: {refresh_interval}s)\n'
                    'Appuyez sur Ctrl+C pour quitter\n'
                )
            )
            
            try:
                while True:
                    self.display_dashboard()
                    print(f"\033[90mRafraîchissement dans {refresh_interval}s... (Ctrl+C pour quitter)\033[0m")
                    time.sleep(refresh_interval)
            except KeyboardInterrupt:
                self.clear_screen()
                self.stdout.write(self.style.SUCCESS('\n✓ Dashboard arrêté\n'))