# rdv/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
import logging
from celery import shared_task


from rdv.utils import create_and_send_notification
from .models import RendezVous

logger = logging.getLogger(__name__)


@receiver(post_save, sender=RendezVous)
def rdv_status_change_notification(sender, instance, created, **kwargs):
    """
    Déclenche des notifications lors de changements de statut importants.
    """
    if created:
        # Nouveau RDV créé - notifier le médecin
        transaction.on_commit(
            lambda: notify_medecin_new_rdv.delay(instance.id)
        )
    else:
        # RDV modifié - vérifier les changements de statut
        if hasattr(instance, '_previous_statut'):
            old_status = instance._previous_statut
            new_status = instance.statut
            
            if old_status != new_status:
                transaction.on_commit(
                    lambda: handle_status_change.delay(instance.id, old_status, new_status)
                )


@receiver(pre_save, sender=RendezVous)
def store_previous_status(sender, instance, **kwargs):
    """
    Sauvegarde le statut précédent pour détecter les changements.
    """
    if instance.pk:
        try:
            old_instance = RendezVous.objects.get(pk=instance.pk)
            instance._previous_statut = old_instance.statut
        except RendezVous.DoesNotExist:
            instance._previous_statut = None
    else:
        instance._previous_statut = None


# === Tâches déclenchées par les signaux ===

@shared_task(bind=True, max_retries=3)
def notify_medecin_new_rdv(self, rdv_id):
    """
    Notifie le médecin d'un nouveau RDV.
    """
    try:
        rdv = RendezVous.objects.select_related('patient__user', 'medecin__user').get(id=rdv_id)
        
        create_and_send_notification(
            rdv.medecin.user,
            "Nouveau rendez-vous programmé",
            f"Un nouveau rendez-vous a été programmé avec {rdv.patient.user.nom_complet()} "
            f"le {rdv.date_heure_rdv.strftime('%d/%m/%Y à %H:%M')}.\n"
            f"Motif : {rdv.motif or 'Non précisé'}",
            notif_type='info',
            category='appointment',
            rdv=rdv
        )
        
        logger.info(f"Médecin notifié pour nouveau RDV #{rdv_id}")
        return True
        
    except RendezVous.DoesNotExist:
        logger.error(f"RDV #{rdv_id} introuvable pour notification")
    except Exception as e:
        logger.exception(f"Erreur notification nouveau RDV #{rdv_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def handle_status_change(self, rdv_id, old_status, new_status):
    """
    Gère les notifications selon le changement de statut.
    """
    try:
        rdv = RendezVous.objects.select_related('patient__user', 'medecin__user').get(id=rdv_id)
        
        # Mapping des transitions importantes
        notifications_map = {
            ('programme', 'confirme'): {
                'user': rdv.patient.user,
                'subject': "Rendez-vous confirmé",
                'message': f"Votre rendez-vous du {rdv.date_heure_rdv.strftime('%d/%m/%Y à %H:%M')} "
                          f"avec Dr. {rdv.medecin.user.nom_complet()} a été confirmé.",
                'type': 'success'
            },
            ('confirme', 'annule'): {
                'user': rdv.patient.user,
                'subject': "Rendez-vous annulé",
                'message': f"Votre rendez-vous du {rdv.date_heure_rdv.strftime('%d/%m/%Y à %H:%M')} "
                          f"a été annulé.\n"
                          f"Raison : {rdv.raison_annulation or 'Non précisée'}",
                'type': 'warning'
            },
            ('en_cours', 'termine'): {
                'user': rdv.patient.user,
                'subject': "Rendez-vous terminé",
                'message': f"Merci pour votre visite. Votre rendez-vous avec "
                          f"Dr. {rdv.medecin.user.nom_complet()} est terminé.",
                'type': 'success'
            },
        }
        
        notification_data = notifications_map.get((old_status, new_status))
        
        if notification_data:
            create_and_send_notification(
                notification_data['user'],
                notification_data['subject'],
                notification_data['message'],
                notif_type=notification_data['type'],
                category='appointment',
                rdv=rdv
            )
            logger.info(f"Notification envoyée pour changement {old_status} -> {new_status} (RDV #{rdv_id})")
        
        return True
        
    except RendezVous.DoesNotExist:
        logger.error(f"RDV #{rdv_id} introuvable pour handle_status_change")
    except Exception as e:
        logger.exception(f"Erreur handle_status_change RDV #{rdv_id}: {e}")
        raise self.retry(exc=e, countdown=60)