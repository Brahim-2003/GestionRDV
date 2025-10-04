# rdv/apps.py
from django.apps import AppConfig


class RdvConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rdv'
    verbose_name = 'Gestion des Rendez-vous'
    
    def ready(self):
        """
        Importe les signaux lors du démarrage de l'application.
        Cela active les notifications automatiques.
        """
        import rdv.signals  # noqa

