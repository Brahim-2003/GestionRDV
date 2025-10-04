# users/tasks.py
from celery import shared_task
import logging
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from .models import Utilisateur
from rdv.utils import create_and_send_notification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def notify_admins_on_user_create(self, user_id):
    """
    Notifie tous les admins actifs lors de l'inscription d'un nouvel utilisateur.
    """
    try:
        user = Utilisateur.objects.get(pk=user_id)
    except Utilisateur.DoesNotExist:
        logger.warning(f"notify_admins_on_user_create: user {user_id} introuvable")
        return

    subject = f"Nouvel utilisateur inscrit - {user.get_role_display()}"
    message = (
        f"Un nouveau {user.get_role_display()} vient de s'inscrire :\n\n"
        f"• Nom : {user.nom_complet()}\n"
        f"• Email : {user.email}\n"
        f"• Date d'inscription : {user.date_inscription.strftime('%d/%m/%Y à %H:%M')}"
    )

    admins = Utilisateur.objects.filter(role='admin', is_actif=True)
    notified_count = 0
    
    for admin in admins:
        try:
            # Éviter doublons
            cache_key = f"notif_new_user_{user.id}_to_{admin.id}"
            if cache.get(cache_key):
                continue
            
            create_and_send_notification(
                admin,
                subject,
                message,
                notif_type='info',
                category='system'
            )
            
            # Marquer comme envoyé (expire après 24h)
            cache.set(cache_key, True, 86400)
            notified_count += 1
            
        except Exception as e:
            logger.exception(f"Erreur notification admin {admin.id}: {e}")

    return f"{notified_count} admins notifiés pour user {user_id}"


@shared_task(bind=True, max_retries=3)
def track_failed_login_attempt(self, email, ip_address, user_agent=None):
    """
    Enregistre une tentative de connexion échouée et alerte si seuil dépassé.
    """
    cache_key = f"failed_login_{email}_{ip_address}"
    attempts = cache.get(cache_key, 0)
    attempts += 1
    
    # Stocker pour 1 heure
    cache.set(cache_key, attempts, 3600)
    
    logger.warning(f"Tentative connexion échouée #{attempts} pour {email} depuis {ip_address}")
    
    # Alerter admins si >= 5 tentatives
    if attempts >= 5:
        from rdv.tasks import notify_admins_failed_login
        notify_admins_failed_login.delay(email, ip_address, attempts)
    
    return f"Tentative #{attempts} enregistrée"


@shared_task(bind=True)
def cleanup_inactive_users(self):
    """
    Désactive les comptes patients non vérifiés après 30 jours.
    """
    threshold = timezone.now() - timedelta(days=30)
    
    inactive_users = Utilisateur.objects.filter(
        role='patient',
        is_actif=True,
        date_inscription__lt=threshold,
        # Ajouter un champ 'email_verified' si tu en as un
        # email_verified=False
    )
    
    # Pour l'instant, on notifie juste
    count = 0
    for user in inactive_users:
        try:
            create_and_send_notification(
                user,
                "Compte inactif",
                "Votre compte n'a pas été vérifié depuis 30 jours. "
                "Veuillez vous connecter pour maintenir votre compte actif.",
                notif_type='warning',
                category='system'
            )
            count += 1
        except Exception as e:
            logger.error(f"Erreur notification inactivité user {user.id}: {e}")
    
    return f"{count} utilisateurs inactifs notifiés"


@shared_task(bind=True)
def send_birthday_wishes(self):
    """
    Envoie un message d'anniversaire aux utilisateurs.
    """
    today = timezone.now().date()
    
    birthday_users = Utilisateur.objects.filter(
        date_naissance__month=today.month,
        date_naissance__day=today.day,
        is_actif=True
    )
    
    sent_count = 0
    
    for user in birthday_users:
        try:
            # Vérifier qu'on n'a pas déjà envoyé cette année
            cache_key = f"birthday_{user.id}_{today.year}"
            if cache.get(cache_key):
                continue
            
            create_and_send_notification(
                user,
                "Joyeux anniversaire ! 🎉",
                f"Toute l'équipe vous souhaite un excellent anniversaire, {user.prenom} !",
                notif_type='success',
                category='system'
            )
            
            cache.set(cache_key, True, 86400 * 365)  # Expire dans 1 an
            sent_count += 1
            
        except Exception as e:
            logger.error(f"Erreur envoi anniversaire user {user.id}: {e}")
    
    return f"{sent_count} messages d'anniversaire envoyés"