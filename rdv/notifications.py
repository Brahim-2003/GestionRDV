# rdv/notifications.py
from django.utils import timezone
from django.conf import settings

from .models import Notification
from django.template.loader import render_to_string

def create_notification(user, message, notification_type='info', category='system'):
    """
    Crée et enregistre une Notification (DB).
    Retourne l'instance Notification.
    """
    notif = Notification.objects.create(
        user=user,
        message=message,
        type=notification_type,
        category=category
    )
    return notif

def _format_rdv_datetime(rdv):
    """Retourne date et heure formatées pour affichage dans les messages."""
    try:
        s = rdv.date_heure_rdv.strftime('%d/%m/%Y %H:%M')
    except Exception:
        s = str(rdv.date_heure_rdv)
    return s
