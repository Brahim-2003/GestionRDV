# users/apps.py
from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    verbose_name = 'Utilisateurs'
    
    def ready(self):
        """
        Importe les signaux lors du démarrage de l'application.
        """
        import users.signals  # noqa