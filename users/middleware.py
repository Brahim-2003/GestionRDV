# users/middleware.py
from django.core.cache import cache
from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver
from django.db import transaction
import logging

from users.tasks import track_failed_login_attempt

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Récupère l'IP réelle du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@receiver(user_login_failed)
def failed_login_callback(sender, credentials, request, **kwargs):
    """
    Déclenché automatiquement par Django lors d'un échec de connexion.
    """
    email = credentials.get('username', '')
    ip_address = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:200]
    
    # Lancer la tâche asynchrone pour tracker
    transaction.on_commit(
        lambda: track_failed_login_attempt.delay(email, ip_address, user_agent)
    )
    
    logger.warning(f"Échec connexion: {email} depuis {ip_address}")


class SecurityMiddleware:
    """
    Middleware pour surveiller les activités suspectes.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Avant la vue
        ip = get_client_ip(request)
        
        # Vérifier si l'IP est bloquée temporairement
        block_key = f"blocked_ip_{ip}"
        if cache.get(block_key):
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden(
                "Votre IP a été temporairement bloquée en raison d'activités suspectes. "
                "Réessayez dans 1 heure."
            )
        
        response = self.get_response(request)
        
        # Après la vue (optionnel: logger certaines actions)
        
        return response