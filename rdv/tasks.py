# rdv/tasks.py
from celery import shared_task
from django.utils import timezone
from django.db.models import Q, Count
from django.db import transaction
from datetime import timedelta
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


# ========================================
# TÂCHES APPELÉES PAR LES SIGNAUX
# ========================================

@shared_task(bind=True, max_retries=3)
def notify_medecin_new_rdv(self, rdv_id):
    """
    Notifie le médecin d'un nouveau RDV (appelé par signal post_save).
    """
    try:
        from .models import RendezVous
        from .utils import create_and_send_notification
        
        rdv = RendezVous.objects.select_related('patient__user', 'medecin__user').get(id=rdv_id)
        
        create_and_send_notification(
            rdv.medecin.user,
            "Nouveau rendez-vous programmé",
            f"Un nouveau rendez-vous a été programmé avec {rdv.patient.user.nom_complet()} "
            f"le {timezone.localtime(rdv.date_heure_rdv).strftime('%d/%m/%Y à %H:%M')}.\n"
            f"Motif : {rdv.motif or 'Non précisé'}",
            notif_type='info',
            category='appointment',
            rdv=rdv
        )
        
        logger.info(f"Médecin notifié pour nouveau RDV #{rdv_id}")
        return f"Notification envoyée pour RDV #{rdv_id}"
        
    except Exception as e:
        logger.exception(f"Erreur notification nouveau RDV #{rdv_id}: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def handle_status_change(self, rdv_id, old_status, new_status):
    """
    Gère les notifications selon le changement de statut (appelé par signal).
    CORRECTION: Suppression du double appel à strftime()
    """
    try:
        from .models import RendezVous
        from .utils import create_and_send_notification
        
        rdv = RendezVous.objects.select_related('patient__user', 'medecin__user').get(id=rdv_id)
        
        # Mapping des transitions importantes
        notifications_map = {
            ('programme', 'confirme'): {
                'user': rdv.patient.user,
                'subject': "Rendez-vous confirmé",
                'message': f"Votre rendez-vous du {timezone.localtime(rdv.date_heure_rdv).strftime('%d/%m/%Y à %H:%M')} "
                          f"avec Dr. {rdv.medecin.user.nom_complet()} a été confirmé.",
                'type': 'success'
            },
            ('confirme', 'annule'): {
                'user': rdv.patient.user,
                'subject': "Rendez-vous annulé",
                'message': f"Votre rendez-vous du {timezone.localtime(rdv.date_heure_rdv).strftime('%d/%m/%Y à %H:%M')} "
                          f"a été annulé.\n"
                          f"Raison : {rdv.raison_annulation or 'Non précisée'}",
                'type': 'warning'
            },
            ('programme', 'annule'): {
                'user': rdv.patient.user,
                'subject': "Rendez-vous annulé",
                'message': f"Votre rendez-vous du {timezone.localtime(rdv.date_heure_rdv).strftime('%d/%m/%Y à %H:%M')} "
                          f"a été annulé.",
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
        
        return f"Changement de statut traité pour RDV #{rdv_id}"
        
    except Exception as e:
        logger.exception(f"Erreur handle_status_change RDV #{rdv_id}: {e}")
        raise self.retry(exc=e, countdown=60)

# ========================================
# TÂCHES DE GESTION DES RENDEZ-VOUS
# ========================================


@shared_task(bind=True, max_retries=3)
def auto_cancel_expired_rdv(self):
    """
    Annule automatiquement les RDV 'programmés' ou 'reportés' 
    dont la date est passée.
    VERSION OPTIMISÉE : Ajout d'une fenêtre de grâce de 2h.
    """
    from .models import RendezVous
    
    # AMÉLIORATION : Ajouter une fenêtre de grâce de 2h
    # Ne pas annuler immédiatement si le RDV vient juste de passer
    now = timezone.now()
    grace_period = now - timedelta(hours=2)
    
    expired_rdvs = RendezVous.objects.filter(
        Q(statut='programme') | Q(statut='reporte'),
        date_heure_rdv__lt=grace_period  # Pas "now" mais "grace_period"
    )

    total_cancelled = 0

    for rdv in expired_rdvs:
        try:
            rdv.cancel(
                description=f"Annulation automatique - rendez-vous expiré (date passée de {(now - rdv.date_heure_rdv).days} jours)",
                by_user=None
            )
            total_cancelled += 1
            logger.info(f"RDV #{rdv.id} annulé automatiquement (expiré)")
        except Exception as e:
            logger.error(f"Erreur annulation auto RDV #{rdv.id}: {e}")

    return f"{total_cancelled} rendez-vous expirés annulés"

@shared_task(bind=True, max_retries=3)
def auto_start_rdv(self):
    """
    Passe les RDV 'confirmés' à 'en_cours' quand l'heure arrive.
    """
    from .models import RendezVous
    from .utils import create_and_send_notification
    
    now = timezone.now()
    window_end = now + timedelta(minutes=5)

    rdvs_to_start = RendezVous.objects.filter(
        statut='confirme',
        date_heure_rdv__gte=now,
        date_heure_rdv__lte=window_end
    ).select_related('patient__user', 'medecin__user')

    started_count = 0

    for rdv in rdvs_to_start:
        try:
            with transaction.atomic():
                rdv.statut = 'en_cours'
                rdv.save(update_fields=['statut', 'date_modification'])

                create_and_send_notification(
                    rdv.medecin.user,
                    "Rendez-vous en cours",
                    f"Le rendez-vous avec {rdv.patient.user.nom_complet()} est maintenant en cours.",
                    notif_type='info',
                    category='appointment',
                    rdv=rdv
                )

            started_count += 1
            logger.info(f"RDV #{rdv.id} passé en cours")
        except Exception as e:
            logger.error(f"Erreur démarrage RDV #{rdv.id}: {e}")

    return f"{started_count} rendez-vous démarrés"


@shared_task(bind=True, max_retries=3)
def auto_complete_rdv(self):
    """
    Termine automatiquement les RDV 'en_cours' après leur durée prévue.
    VERSION OPTIMISÉE : Filtre sur la date pour éviter de scanner tous les RDV.
    """
    from .models import RendezVous
    from .utils import create_and_send_notification
    
    now = timezone.now()
    
    # OPTIMISATION : Chercher seulement les RDV en cours qui ont commencé il y a plus de 30 min
    # Au lieu de tous les RDV en_cours
    rdvs_to_complete = RendezVous.objects.filter(
        statut='en_cours',
        date_heure_rdv__lt=now - timedelta(minutes=30)  # Par défaut 30 min
    ).select_related('patient__user', 'medecin__user')

    completed_count = 0

    for rdv in rdvs_to_complete:
        # Vérifier la durée réelle du RDV
        duration = timedelta(minutes=rdv.duree_minutes)
        end_time = rdv.date_heure_rdv + duration
        
        if now >= end_time:
            try:
                with transaction.atomic():
                    rdv.statut = 'termine'
                    rdv.save(update_fields=['statut', 'date_modification'])

                    create_and_send_notification(
                        rdv.patient.user,
                        "Rendez-vous terminé",
                        f"Votre rendez-vous avec Dr. {rdv.medecin.user.nom_complet()} est terminé. Merci de votre visite.",
                        notif_type='success',
                        category='appointment',
                        rdv=rdv
                    )

                completed_count += 1
                logger.info(f"RDV #{rdv.id} terminé automatiquement")
            except Exception as e:
                logger.error(f"Erreur finalisation RDV #{rdv.id}: {e}")

    return f"{completed_count} rendez-vous terminés"

# ========================================
# TÂCHES DE RAPPEL
# ========================================


@shared_task(bind=True, max_retries=3)
def send_rdv_reminder_24h(self):
    """
    Envoie un rappel 24h avant le RDV aux patients.
    VERSION OPTIMISÉE : Fenêtre plus précise et meilleure gestion des doublons.
    """
    from .models import RendezVous, Notification
    from .utils import create_and_send_notification
    
    now = timezone.now()
    tomorrow = now + timedelta(hours=24)
    
    # OPTIMISATION : Fenêtre de 15 minutes au lieu de 60
    window_start = tomorrow - timedelta(minutes=15)
    window_end = tomorrow + timedelta(minutes=15)

    rdvs = RendezVous.objects.filter(
        statut__in=['confirme', 'programme'],
        date_heure_rdv__gte=window_start,
        date_heure_rdv__lte=window_end
    ).select_related('patient__user', 'medecin__user')

    sent_count = 0

    for rdv in rdvs:
        try:
            # AMÉLIORATION : Vérifier avec un identifiant unique pour ce RDV
            cache_key = f"reminder_24h_{rdv.id}_{rdv.date_heure_rdv.date()}"
            
            # Vérifier dans le cache d'abord (plus rapide que DB)
            from django.core.cache import cache
            if cache.get(cache_key):
                continue
            
            # Double vérification en DB pour sécurité
            already_sent = Notification.objects.filter(
                user=rdv.patient.user,
                category='reminder',
                message__contains=f"rendez-vous du {rdv.date_heure_rdv.strftime('%d/%m/%Y')}",
                date_envoi__gte=now - timedelta(hours=25)
            ).exists()

            if not already_sent:
                create_and_send_notification(
                    rdv.patient.user,
                    "Rappel : Rendez-vous demain",
                    f"Rappel de votre rendez-vous du {timezone.localtime(rdv.date_heure_rdv).strftime('%d/%m/%Y à %H:%M')} "
                    f"avec Dr. {rdv.medecin.user.nom_complet()}.\n"
                    f"Adresse : {rdv.medecin.adresse_cabinet or 'Cabinet médical'}",
                    notif_type='info',
                    category='reminder',
                    rdv=rdv
                )
                
                # Marquer comme envoyé dans le cache (expire dans 26h)
                cache.set(cache_key, True, 60*60*26)
                sent_count += 1
                
        except Exception as e:
            logger.error(f"Erreur rappel 24h RDV #{rdv.id}: {e}")

    return f"{sent_count} rappels 24h envoyés"


@shared_task(bind=True, max_retries=3)
def send_rdv_reminder_2h(self):
    """
    Envoie un rappel 2h avant le RDV aux patients.
    """
    from .models import RendezVous, Notification
    from .utils import create_and_send_notification
    
    now = timezone.now()
    in_2h = now + timedelta(hours=2)
    window_start = in_2h - timedelta(minutes=15)
    window_end = in_2h + timedelta(minutes=15)

    rdvs = RendezVous.objects.filter(
        statut__in=['confirme', 'programme'],
        date_heure_rdv__gte=window_start,
        date_heure_rdv__lte=window_end
    ).select_related('patient__user', 'medecin__user')

    sent_count = 0

    for rdv in rdvs:
        try:
            date_str = rdv.date_heure_rdv.strftime('%d/%m/%Y')
            already_sent = Notification.objects.filter(
                user=rdv.patient.user,
                date_envoi__gte=now - timedelta(hours=3)
            ).filter(
                Q(message__contains="dans 2 heures") & Q(message__contains=date_str)
            ).exists()

            if not already_sent:
                create_and_send_notification(
                    rdv.patient.user,
                    "Rappel : Rendez-vous dans 2 heures",
                    f"Rappel : Votre rendez-vous avec Dr. {rdv.medecin.user.nom_complet()} "
                    f"est prévu dans 2 heures ({timezone.localtime(rdv.date_heure_rdv).strftime('%H:%M')}).\n"
                    f"Adresse : {rdv.medecin.adresse_cabinet or 'Cabinet médical'}",
                    notif_type='warning',
                    category='reminder',
                    rdv=rdv
                )
                sent_count += 1
        except Exception as e:
            logger.error(f"Erreur rappel 2h RDV #{rdv.id}: {e}")

    return f"{sent_count} rappels 2h envoyés"


# ========================================
# TÂCHES DE NOTIFICATION ADMIN
# ========================================

@shared_task(bind=True, max_retries=3)
def notify_admins_failed_login(self, email, ip_address, attempt_count):
    """
    Notifie les admins en cas de tentatives de connexion suspectes.
    """
    from users.models import Utilisateur
    from .utils import create_and_send_notification
    
    if attempt_count < 5:
        return "Pas assez de tentatives pour alerter"

    admins = Utilisateur.objects.filter(role='admin', is_actif=True)

    for admin in admins:
        try:
            create_and_send_notification(
                admin,
                "Tentatives de connexion suspectes",
                f"Alerte sécurité : {attempt_count} tentatives de connexion échouées "
                f"pour l'email {email} depuis l'IP {ip_address}.",
                notif_type='warning',
                category='system'
            )
        except Exception as e:
            logger.error(f"Erreur notification admin tentative connexion: {e}")

    return f"Admins notifiés pour {email}"


@shared_task(bind=True, max_retries=3)
def check_high_cancellation_rate(self):
    """
    Vérifie le taux d'annulation par médecin et alerte si élevé.
    """
    from .models import Medecin
    from users.models import Utilisateur
    from .utils import create_and_send_notification
    
    week_ago = timezone.now() - timedelta(days=7)

    medecins = Medecin.objects.annotate(
        total_rdv=Count('rendez_vous', filter=Q(rendez_vous__date_creation__gte=week_ago)),
        annules=Count('rendez_vous', filter=Q(
            rendez_vous__statut='annule',
            rendez_vous__date_creation__gte=week_ago
        ))
    ).filter(total_rdv__gte=5)  # Au moins 5 RDV

    admins = Utilisateur.objects.filter(role='admin', is_actif=True)
    alerts_sent = 0

    for medecin in medecins:
        if medecin.total_rdv > 0:
            taux = (medecin.annules / medecin.total_rdv) * 100

            if taux >= 30:
                message = (
                    f"Alerte : Taux d'annulation élevé\n"
                    f"Dr. {medecin.user.nom_complet()} : {taux:.1f}% d'annulations "
                    f"({medecin.annules}/{medecin.total_rdv} RDV cette semaine)"
                )

                for admin in admins:
                    try:
                        create_and_send_notification(
                            admin,
                            "Taux d'annulation élevé détecté",
                            message,
                            notif_type='warning',
                            category='system'
                        )
                        alerts_sent += 1
                    except Exception as e:
                        logger.error(f"Erreur notification taux annulation: {e}")

    return f"{alerts_sent} alertes envoyées pour taux d'annulation"


@shared_task(bind=True, max_retries=3)
def alert_unconfirmed_rdv_to_doctors(self):
    """
    Alerte les médecins pour les RDV programmés dans les 48h qui ne sont pas confirmés.
    """
    from .models import RendezVous
    from .utils import create_and_send_notification
    
    now = timezone.now()
    window_48h = now + timedelta(hours=48)

    rdvs_unconfirmed = RendezVous.objects.filter(
        statut='programme',
        date_heure_rdv__gte=now,
        date_heure_rdv__lte=window_48h
    ).select_related('medecin__user', 'patient__user')

    rdvs_by_medecin = defaultdict(list)

    for rdv in rdvs_unconfirmed:
        rdvs_by_medecin[rdv.medecin].append(rdv)

    alerted_count = 0

    for medecin, rdvs in rdvs_by_medecin.items():
        try:
            rdv_list = "\n".join([
                f"• {rdv.patient.user.nom_complet()} - {timezone.localtime(rdv.date_heure_rdv).strftime('%d/%m/%Y à %H:%M')}"
                for rdv in rdvs[:5]
            ])

            more_text = f"\n... et {len(rdvs) - 5} autre(s)" if len(rdvs) > 5 else ""

            message = (
                f"Vous avez {len(rdvs)} rendez-vous non confirmé(s) dans les 48 prochaines heures :\n\n"
                f"{rdv_list}{more_text}\n\n"
                f"Pensez à les confirmer pour éviter les no-show."
            )

            create_and_send_notification(
                medecin.user,
                f"{len(rdvs)} RDV à confirmer",
                message,
                notif_type='warning',
                category='appointment'
            )

            alerted_count += 1

        except Exception as e:
            logger.error(f"Erreur alerte RDV non confirmés médecin {medecin.id}: {e}")

    return f"{alerted_count} médecins alertés pour RDV non confirmés"


@shared_task(bind=True, max_retries=3)
def send_weekly_stats_to_doctors(self):
    """
    Envoie des statistiques hebdomadaires aux médecins.
    """
    from .models import Medecin, RendezVous
    from .utils import create_and_send_notification
    
    now = timezone.now()
    week_start = now - timedelta(days=7)

    medecins = Medecin.objects.all()
    sent_count = 0

    for medecin in medecins:
        try:
            rdvs_week = RendezVous.objects.filter(
                medecin=medecin,
                date_creation__gte=week_start
            )

            total_rdv = rdvs_week.count()
            if total_rdv == 0:
                continue

            rdv_confirmes = rdvs_week.filter(statut='confirme').count()
            rdv_termines = rdvs_week.filter(statut='termine').count()
            rdv_annules = rdvs_week.filter(statut='annule').count()
            rdv_programmes = rdvs_week.filter(statut='programme').count()

            taux_confirmation = (rdv_confirmes / total_rdv * 100) if total_rdv > 0 else 0
            taux_completion = (rdv_termines / total_rdv * 100) if total_rdv > 0 else 0
            taux_annulation = (rdv_annules / total_rdv * 100) if total_rdv > 0 else 0

            patients_vus = rdvs_week.filter(
                statut__in=['termine', 'en_cours']
            ).values('patient').distinct().count()

            rdv_a_venir = RendezVous.objects.filter(
                medecin=medecin,
                date_heure_rdv__gte=now,
                date_heure_rdv__lte=now + timedelta(days=7),
                statut__in=['confirme', 'programme']
            ).count()

            warning_text = "Attention : Taux d'annulation élevé" if taux_annulation > 20 else "✔ Bonne performance"

            message = (
                f"Rapport hebdomadaire - Semaine du {week_start.strftime('%d/%m/%Y')}\n\n"
                f"ACTIVITÉ\n"
                f"• Total rendez-vous : {total_rdv}\n"
                f"• Patients vus : {patients_vus}\n"
                f"• RDV à venir (7j) : {rdv_a_venir}\n\n"
                f"RÉPARTITION\n"
                f"• Confirmés : {rdv_confirmes} ({taux_confirmation:.0f}%)\n"
                f"• Terminés : {rdv_termines} ({taux_completion:.0f}%)\n"
                f"• Annulés : {rdv_annules} ({taux_annulation:.0f}%)\n"
                f"• Programmés : {rdv_programmes}\n\n"
                f"{warning_text}\n"
            )

            create_and_send_notification(
                medecin.user,
                "Votre rapport hebdomadaire",
                message,
                notif_type='info',
                category='system'
            )

            sent_count += 1

        except Exception as e:
            logger.error(f"Erreur envoi stats hebdo médecin {medecin.id}: {e}")

    return f"{sent_count} rapports hebdomadaires envoyés"


# ========================================
# TÂCHES DE MAINTENANCE
# ========================================

@shared_task(bind=True)
def cleanup_old_notifications(self):
    """
    Supprime les notifications lues de plus de 30 jours.
    VERSION OPTIMISÉE : Suppression par lots pour éviter le verrouillage.
    """
    from .models import Notification
    
    threshold = timezone.now() - timedelta(days=30)
    batch_size = 1000
    total_deleted = 0

    while True:
        # Récupérer un lot d'IDs à supprimer
        ids = list(Notification.objects.filter(
            is_read=True,
            date_read__lt=threshold
        ).values_list('id', flat=True)[:batch_size])
        
        if not ids:
            break
        
        # Supprimer le lot
        deleted_count = Notification.objects.filter(id__in=ids).delete()[0]
        total_deleted += deleted_count
        
        logger.info(f"Supprimé {deleted_count} notifications (total: {total_deleted})")
        
        # Petit délai pour éviter de surcharger la DB
        if deleted_count == batch_size:
            import time
            time.sleep(0.1)

    logger.info(f"Nettoyage terminé : {total_deleted} notifications supprimées")
    return f"{total_deleted} notifications nettoyées"


@shared_task(bind=True)
def generate_daily_stats_report(self):
    """
    Génère un rapport quotidien des statistiques.
    """
    from .models import Patient, RendezVous
    from users.models import Utilisateur
    from .utils import create_and_send_notification
    
    today = timezone.now().date()

    stats = {
        'nouveaux_patients': Patient.objects.filter(
            user__date_inscription__date=today
        ).count(),
        'rdv_crees': RendezVous.objects.filter(
            date_creation__date=today
        ).count(),
        'rdv_annules': RendezVous.objects.filter(
            statut='annule',
            date_modification__date=today
        ).count(),
        'rdv_termines': RendezVous.objects.filter(
            statut='termine',
            date_modification__date=today
        ).count(),
    }

    # Notifier admins
    admins = Utilisateur.objects.filter(role='admin', is_actif=True)

    message = (
        f"  Rapport quotidien du {today.strftime('%d/%m/%Y')}\n\n"
        f"• Nouveaux patients : {stats['nouveaux_patients']}\n"
        f"• RDV créés : {stats['rdv_crees']}\n"
        f"• RDV terminés : {stats['rdv_termines']}\n"
        f"• RDV annulés : {stats['rdv_annules']}"
    )

    for admin in admins:
        try:
            create_and_send_notification(
                admin,
                "Rapport quotidien",
                message,
                notif_type='info',
                category='system'
            )
        except Exception as e:
            logger.error(f"Erreur envoi rapport quotidien: {e}")

    return stats