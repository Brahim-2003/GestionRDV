# rdv/utils.py
from django.core.mail import send_mail, BadHeaderError
from django.conf import settings
from django.utils import timezone
import logging
from django.db import DataError

from .models import Notification, RdvHistory

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {'info', 'success', 'warning', 'error'}
ALLOWED_CATEGORIES = {'appointment', 'system', 'profile', 'reminder'}

def _safe_choice(value, allowed, default):
    if not value:
        return default
    v = str(value)
    return v if v in allowed else default

def create_and_send_notification(user, subject, message, notif_type='info', category='system', rdv=None, include_default=True):
    """
    Crée une Notification en base et, si la config l'autorise, tente d'envoyer un email.
    - Si NOTIFY_SEND_EMAIL = False dans settings, on NE TENTE PAS l'envoi.
    - Aucune exception d'envoi/DB ne remontera: on logge et on retourne (sent_bool, notif_or_None).
    """
    # Lire le flag tout de suite (evite toute tentative d'envoi si False)
    send_email_flag = getattr(settings, 'NOTIFY_SEND_EMAIL', True)
    if not send_email_flag:
        logger.debug("create_and_send_notification: envoi email désactivé par NOTIFY_SEND_EMAIL=False")
    notif = None
    sent = False

    notif_type = _safe_choice(notif_type, ALLOWED_TYPES, 'info')
    category = _safe_choice(category, ALLOWED_CATEGORIES, 'system')

    safe_subject = str(subject or '')[:200]
    safe_message = str(message or '')

    # 1) Creer la notification (toujours essayer, même si envoi email désactivé)
    try:
        notif = Notification.objects.create(
            user=user,
            message=safe_message,
            type=notif_type,
            category=category
        )
    except DataError as e:
        logger.warning("DataError création Notification pour user %s : %s - fallback court", getattr(user,'id',user), e)
        try:
            notif = Notification.objects.create(
                user=user,
                message=safe_message[:200],
                type='info',
                category='system'
            )
        except Exception as ee:
            logger.warning("Fallback Notification échoué pour user %s : %s", getattr(user,'id',user), ee)
            notif = None
    except Exception as e:
        logger.warning("Erreur création Notification pour user %s : %s", getattr(user,'id',user), e)
        notif = None

    # 2) Si l'envoi est désactivé, sortir proprement ici (aucun appel à send_mail)
    if not send_email_flag:
        return False, notif

    # 3) Envoyer l'email seulement si le flag est True et que l'utilisateur a un email
    try:
        email = getattr(user, 'email', None)
        if email:
            send_mail(
                safe_subject or "Notification",
                safe_message,
                getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                [email],
                fail_silently=False,
            )
            sent = True
    except (ConnectionRefusedError, OSError) as e:
        # connexion refusée, serveur SMTP absent -> log warning (pas d'exception bloquante)
        logger.warning("Erreur envoi email pour notification user %s : %s", getattr(user,'id',user), e)
        sent = False
    except BadHeaderError as e:
        logger.warning("BadHeaderError envoi email pour user %s : %s", getattr(user,'id',user), e)
        sent = False
    except Exception as e:
        logger.warning("Erreur inconnue envoi email pour user %s : %s", getattr(user,'id',user), e)
        sent = False

    return sent, notif


# rdv/utils.py (nouvelle fonction d'autorisation)
def user_can_manage_rdv(user, rdv, action=None):
    """
    Retourne True si `user` peut exécuter `action` sur `rdv`.
    Règles :
      - superuser ou staff -> ok
      - medecin propriétaire -> ok pour actions médecin
      - patient propriétaire -> ok pour actions patient (report request)
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True

    # medecin owner
    med_profil = getattr(user, 'profil_medecin', None)
    if med_profil and rdv.medecin_id == med_profil.id:
        return True

    # patient owner (ex: reporter by patient on his RDV)
    pat_profil = getattr(user, 'profil_patient', None)
    if pat_profil and rdv.patient_id == pat_profil.id:
        # allow patient-specific actions
        # Here we allow patient to request report; for other actions you may restrict further
        if action in (None, 'request_report', 'view'):
            return True
    return False



def send_manual_notification(user, subject, message, rdv=None, by_user=None):
    """
    Envoie une notification manuelle (créée dans la base et envoyée par email si activé).
    - user : destinataire (instance de User)
    - subject : sujet du message
    - message : contenu texte brut
    - rdv : rendez-vous lié (optionnel)
    - by_user : utilisateur qui a initié l'envoi (optionnel, pour audit)
    """
    notif = Notification.objects.create(
        user=user,
        subject=subject,
        message=message,
        rdv=rdv,
        type='manual',
        category='appointment',
    )

    # Historique (audit)
    if by_user and rdv:
        try:
            RdvHistory.objects.create(
                rdv=rdv,
                action="notifier",
                performed_by=by_user,
                description=f"Notification manuelle envoyée à {user} (sujet: '{subject}')"
            )
        except Exception as e:
            logger.warning("Impossible d'enregistrer l'historique pour la notif manuelle RDV %s : %s", rdv.id, e)

    # Email si activé
    if getattr(settings, "NOTIFY_SEND_EMAIL", False):
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
            )
        except Exception as e:
            logger.exception("Erreur envoi email notif manuelle user %s : %s", user.id, e)

    return notif
