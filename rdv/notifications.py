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

def notify_appointment_confirmed(rdv, send_email=False, send_email_fn=None):
    """
    Notifie le patient qu'un rendez-vous a été confirmé.
    - rdv: instance de RendezVous
    - send_email: bool si on veut tenter envoi d'email
    - send_email_fn: callable(user, subject, message) optionnel pour envoi
    """
    date_aff = _format_rdv_datetime(rdv)
    patient_user = rdv.patient.user
    medecin_label = f"Dr. {rdv.medecin.user.nom_complet()}"
    message = f"Votre rendez-vous du {date_aff} avec {medecin_label} a été confirmé."
    notif = create_notification(patient_user, message, notification_type='success', category='appointment')
    if send_email and send_email_fn:
        subject = "Rendez-vous confirmé"
        send_email_fn(patient_user, subject, message)
    return notif

def notify_appointment_cancelled(rdv, raison='', send_email=False, send_email_fn=None):
    date_aff = _format_rdv_datetime(rdv)
    patient_user = rdv.patient.user
    medecin_label = f"Dr. {rdv.medecin.user.nom_complet()}"
    message = f"Votre rendez-vous du {date_aff} avec {medecin_label} a été annulé."
    if raison:
        message += f" Raison : {raison}"
    notif = create_notification(patient_user, message, notification_type='warning', category='appointment')
    if send_email and send_email_fn:
        subject = "Rendez-vous annulé"
        send_email_fn(patient_user, subject, message)
    return notif

def notify_new_appointment(rdv, send_email=False, send_email_fn=None):
    date_aff = _format_rdv_datetime(rdv)
    medecin_user = rdv.medecin.user
    patient_label = rdv.patient.user.nom_complet()
    message = f"Nouveau rendez-vous programmé le {date_aff} avec {patient_label}."
    notif = create_notification(medecin_user, message, notification_type='info', category='appointment')
    if send_email and send_email_fn:
        subject = "Nouveau rendez-vous"
        send_email_fn(medecin_user, subject, message)
    return notif
