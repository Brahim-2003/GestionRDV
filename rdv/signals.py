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
    Les tâches elles-mêmes vivent dans rdv.tasks (source unique de vérité,
    y compris pour les tâches déclenchées par ces signaux).
    """
    try:
        from rdv import tasks as rdv_tasks

        task = getattr(rdv_tasks, task_name, None)
        if task:
            task.delay(*args)
        else:
            logger.error(f"Tâche Celery inconnue dans rdv.tasks : {task_name}")
    except Exception as e:
        logger.exception(f"Erreur Celery ({task_name}): {e}")