from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
import logging

from .models import RendezVous

logger = logging.getLogger(__name__)


# ==========================
# 📌 STOCKER ANCIEN STATUT
# ==========================
@receiver(pre_save, sender=RendezVous)
def store_previous_status(sender, instance, **kwargs):
    """
    Sauvegarde le statut précédent pour détecter les changements.
    Optimisé : ne fait une requête que si nécessaire.
    """
    if not instance.pk:
        instance._previous_statut = None
        return

    try:
        old = sender.objects.only("statut").get(pk=instance.pk)
        instance._previous_statut = old.statut
    except sender.DoesNotExist:
        instance._previous_statut = None


# ==========================
# 📌 SIGNAL PRINCIPAL
# ==========================
@receiver(post_save, sender=RendezVous)
def rdv_status_change_notification(sender, instance, created, **kwargs):
    """
    Déclenche des notifications via Celery.
    Sécurisé + évite les appels inutiles.
    """

    # Nouveau RDV
    if created:
        transaction.on_commit(lambda: safe_delay("notify_medecin_new_rdv", instance.id))
        return

    # Vérifier changement de statut
    old_status = getattr(instance, "_previous_statut", None)
    new_status = instance.statut

    if old_status == new_status:
        return

    transaction.on_commit(
        lambda: safe_delay("handle_status_change", instance.id, old_status, new_status)
    )


# ==========================
# 🔒 SAFE CELERY CALL
# ==========================
def safe_delay(task_name, *args):
    """
    Appel Celery sécurisé (évite crash si broker down).
    """
    try:
        from django.apps import apps

        task = apps.get_app_config("rdv").module.__dict__.get(task_name)
        if task:
            task.delay(*args)
    except Exception as e:
        logger.exception(f"Erreur Celery ({task_name}): {e}")


# ==========================
# 🧠 TASKS CELERY
# ==========================
from celery import shared_task


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=60)
def notify_medecin_new_rdv(self, rdv_id):
    """
    Notifie le médecin d'un nouveau RDV.
    """
    try:
        from django.utils import timezone
        from rdv.models import RendezVous
        from rdv.utils import create_and_send_notification

        rdv = RendezVous.objects.select_related(
            "patient__user", "medecin__user"
        ).get(id=rdv_id)

        create_and_send_notification(
            rdv.medecin.user,
            "Nouveau rendez-vous programmé",
            f"Nouveau RDV avec {rdv.patient.user.nom_complet()} le "
            f"{timezone.localtime(rdv.date_heure_rdv).strftime('%d/%m/%Y à %H:%M')}",
            notif_type="info",
            category="appointment",
            rdv=rdv,
        )

        logger.info(f"Notification médecin envoyée (RDV #{rdv_id})")
        return True

    except RendezVous.DoesNotExist:
        logger.warning(f"RDV #{rdv_id} introuvable")
        return False


@shared_task(bind=True, max_retries=3, autoretry_for=(Exception,), retry_backoff=60)
def handle_status_change(self, rdv_id, old_status, new_status):
    """
    Gère les notifications selon le changement de statut.
    """
    try:
        from django.utils import timezone
        from rdv.models import RendezVous
        from rdv.utils import create_and_send_notification

        rdv = RendezVous.objects.select_related(
            "patient__user", "medecin__user"
        ).get(id=rdv_id)

        notifications_map = {
            ("programme", "confirme"): (
                rdv.patient.user,
                "Rendez-vous confirmé",
                f"Votre RDV du {timezone.localtime(rdv.date_heure_rdv).strftime('%d/%m/%Y à %H:%M')} est confirmé",
                "success",
            ),
            ("confirme", "annule"): (
                rdv.patient.user,
                "Rendez-vous annulé",
                f"RDV annulé. Raison : {rdv.raison_annulation or 'Non précisée'}",
                "warning",
            ),
            ("en_cours", "termine"): (
                rdv.patient.user,
                "Rendez-vous terminé",
                "Votre consultation est terminée",
                "success",
            ),
        }

        data = notifications_map.get((old_status, new_status))

        if not data:
            return False

        user, subject, message, notif_type = data

        create_and_send_notification(
            user,
            subject,
            message,
            notif_type=notif_type,
            category="appointment",
            rdv=rdv,
        )

        logger.info(f"Notification statut envoyée ({old_status} → {new_status})")
        return True

    except RendezVous.DoesNotExist:
        logger.warning(f"RDV #{rdv_id} introuvable")
        return False