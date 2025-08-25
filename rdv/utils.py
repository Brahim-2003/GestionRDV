# rdv/utils.py
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
import logging

from .models import Notification

logger = logging.getLogger(__name__)

def create_and_send_notification(user, message, notif_type='info', category='appointment', rdv=None, subject=None):
    """
    Crée une Notification (base) et tente d'envoyer un e-mail si possible.
    - user: instance de Utilisateur (patient.user)
    - message: texte
    - notif_type: 'info','success','warning','error'
    - category: 'appointment', ...
    - rdv: instance RendezVous (optionnel)
    - subject: sujet de l'email (optionnel)
    Retourne (email_sent_bool, notification_instance)
    """
    notif = Notification.objects.create(
        user=user,
        message=message,
        type=notif_type,
        category=category,
        is_read=False
    )

    sent = False
    try:
        email = getattr(user, 'email', None)
        if email:
            if not subject:
                subject = "Information concernant votre rendez-vous"
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            sent = True
    except Exception as e:
        logger.exception("Erreur envoi email notification: %s", e)
        # on laisse la notification en base pour suivi
    
    return sent, notif
