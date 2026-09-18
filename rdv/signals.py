from django.core.cache import cache
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.db import transaction
import logging

from .cache import CACHE_KEY_SPECIALITES_COUNT
from .models import RendezVous, Medecin
from .utils import safe_delay

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

    # Créneau libéré : notifier la liste d'attente (rdv/tasks.py::notify_waitlist_on_cancellation)
    if new_status == 'annule':
        transaction.on_commit(
            lambda: safe_delay("notify_waitlist_on_cancellation", instance.id)
        )


# ==========================
# 📌 INVALIDATION CACHE — nb de médecins par spécialité
# ==========================
# CACHE_KEY_SPECIALITES_COUNT (rdv/cache.py) devient obsolète dès qu'un
# médecin est créé, supprimé, ou modifié (ex. changement de specialite via
# MedecinAdmin ou edit_medecin_view) — on l'invalide immédiatement plutôt
# que d'attendre CACHE_TTL_SPECIALITES_COUNT, pour que le changement soit
# visible tout de suite sur la page "prendre RDV".
@receiver(post_save, sender=Medecin)
@receiver(post_delete, sender=Medecin)
def invalidate_specialites_count_cache(sender, instance, **kwargs):
    cache.delete(CACHE_KEY_SPECIALITES_COUNT)