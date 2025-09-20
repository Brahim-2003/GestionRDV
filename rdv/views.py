from datetime import timedelta, datetime

# Django imports (groupés et triés)
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder 
from django.db import IntegrityError, transaction
from django.db.models import Q, Count
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods, require_GET
from django.contrib.auth.decorators import login_required, permission_required
import json
import logging
from django.utils.dateparse import parse_datetime



# App imports
from users.models import Utilisateur
from .forms import UpdateRDVForm, DisponibiliteEditForm, DisponibiliteCreateForm, AnnulerRdvForm, ReporterRdvForm, NotifierRdvForm, RendezVousForm
from .models import RendezVous, Notification, Patient, Medecin, Disponibilite, RdvHistory, FavoriMedecin, RechercheSymptome
from . import notifications as notif_helpers
from rdv.utils import user_can_manage_rdv, send_manual_notification





# Create your views here.

def acceuil_view(request):
    return render(request, 'rdv/acceuil.html')

""" Vues pour les notifications """

@login_required(login_url='users:login')
def list_notif(request):
    filter_type = request.GET.get('type', 'all')
    notifications = Notification.objects.filter(user=request.user)
    if filter_type != 'all':
        notifications = notifications.filter(type=filter_type)
    unread_count = notifications.filter(is_read=False).count()

    context = {
        'notifications': notifications,
        'unread_count': unread_count,
        'current_filter': filter_type,
    }

    # fragment injecté par AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'rdv/notifs/notif_contents.html', context)

    # page full selon rôle
    user_type = get_user_type(request.user)
    if user_type == 'admin':
        tpl = 'rdv/admin/notifs/notifications.html'
    elif user_type == 'medecin':
        tpl = 'rdv/doctor/notifications.html'
    else:
        tpl = 'rdv/patient/notifications.html'
    return render(request, tpl, context)



@login_required(login_url='users:login')
@require_POST
def mark_as_read(request, notification_id):
    """Marquer une notification comme lue"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    return redirect('list_notif')

@login_required(login_url='users:login')
@require_POST
def mark_all_as_read(request):
    """Marquer toutes les notifications comme lues"""
    Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True,
        date_read=timezone.now()
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': 'Toutes les notifications ont été marquées comme lues'})
    
    messages.success(request, 'Toutes les notifications ont été marquées comme lues.')
    return redirect('list_notif')

@login_required(login_url='users:login')
@require_POST
def delete_notification(request, notification_id):
    """Supprimer une notification"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    return redirect('list_notif')

@login_required(login_url='users:login')
@require_POST
def delete_all_notifications(request):
    """Supprimer toutes les notifications"""
    Notification.objects.filter(user=request.user).delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': 'Toutes les notifications ont été supprimées'})
    
    messages.success(request, 'Toutes les notifications ont été supprimées.')
    return redirect('list_notif')

@login_required(login_url='users:login')
def get_notification_count(request):
    """API pour récupérer le nombre de notifications non lues"""
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'unread_count': unread_count})

def get_user_type(user):
    """Détermine le type d'utilisateur selon l'attribut 'role' du modèle Utilisateur"""
    if hasattr(user, 'role'):
        if user.role == 'admin':
            return 'admin'
        elif user.role == 'medecin':
            return 'medecin'
        elif user.role == 'patient':
            return 'patient'
    return 'unknown'



""" Les vues de Admin """
def is_admin(user):
    """Vérifier si l'utilisateur est admin"""
    return user.is_authenticated and user.is_staff

# Tableau de bord admin
@login_required(login_url='users:login')
@permission_required('users.can_view_statistics', raise_exception=True)
def dashboard_admin_view(request):
    """Vue du tableau de bord pour l'administrateur"""
    now = timezone.now()
    debut_semaine = now - timezone.timedelta(days=now.weekday())
    debut_mois = now.replace(day=1)
    debut_jour = now.replace(hour=0, minute=0, second=0, microsecond=0)
    jours_semaine = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

    context = {
            'total_utilisateurs': Utilisateur.objects.count(),
            'total_utilisateurs_inscris_semaine': Utilisateur.objects.filter(date_inscription__gte=debut_semaine).count(),
            'total_utilisateurs_inscris_mois': Utilisateur.objects.filter(date_inscription__gte = debut_mois).count(),
            'total_utilisateurs_inscris_aujour': Utilisateur.objects.filter(date_inscription__gte = debut_jour).count(),
            'total_admins': Utilisateur.objects.filter(role='admin').count(),
            'total_patients': Utilisateur.objects.filter(role='patient').count(),
            'total_medecins': Utilisateur.objects.filter(role='medecin').count(),
            

            'total_rendez_vous': RendezVous.objects.count(),
            'total_confirmes': RendezVous.objects.filter(statut='confirme').count(),
            'total_annules': RendezVous.objects.filter(statut='annule').count(),
            'total_en_cours': RendezVous.objects.filter(statut='en_cours').count(),
            'total_programmes': RendezVous.objects.filter(statut='programme').count(),
            'total_termines': RendezVous.objects.filter(statut='termine').count(),

            'rendez_vous_semaine': RendezVous.objects.filter(date_creation__gte=debut_semaine).count(),
            'rendez_vous_mois': RendezVous.objects.filter(date_creation__gte=debut_mois).count(),
            'rendez_vous_aujour': RendezVous.objects.filter(date_creation__gte=debut_jour).count(),
            'jours_semaine': jours_semaine,
            'rendez_vous_jour': [
                RendezVous.objects.filter(date_creation__date=debut_jour + timezone.timedelta(days=i)).count()
                for i in range(7)
            ],
            'notifications': Notification.objects.filter(user=request.user)[:5],
            'rdvs_recents': RendezVous.objects.all().order_by('-date_creation')[:5]
        }
    # Si c'est une requête AJAX, on renvoie JUSTE le fragment
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
       return render(request, 'rdv/admin/dashboard/composants/dash_content.html', context)

    # Sinon on renvoie base.html, qui inclura via {% block content %} ton dashboard.html complet
    return render(request, 'rdv/admin/dashboard/dashboard_admin.html', context)


# vue dashboard ajax
@login_required(login_url='users:login')
@permission_required('users.can_view_statistics', raise_exception=True)
def api_dashboard_stats(request):
    user = request.user
    now = timezone.now()
    debut_semaine = now - timezone.timedelta(days=now.weekday())
    debut_mois = now.replace(day=1)
    debut_jour = now.replace(hour=0, minute=0, second=0, microsecond=0)

    data = {}

    if user.is_admin_role():
        data = {
            'total_utilisateurs': Utilisateur.objects.count(),
            'total_patients': Utilisateur.objects.filter(role='patient').count(),
            'total_medecins': Utilisateur.objects.filter(role='medecin').count(),
            'total_rendez_vous': RendezVous.objects.count(),
            'total_confirmes': RendezVous.objects.filter(statut='confirme').count(),
            'total_programmes': RendezVous.objects.filter(statut='programme').count(),
            'total_annules': RendezVous.objects.filter(statut='annule').count(),
            'total_termines': RendezVous.objects.filter(statut='termine').count(),
            'rdv_cette_semaine': RendezVous.objects.filter(date_heure_rdv__gte=debut_semaine).count(),
            'rdv_ce_mois': RendezVous.objects.filter(date_heure_rdv__gte=debut_mois).count(),
            'rdv_par_jour': [
                RendezVous.objects.filter(date_heure_rdv__date=debut_jour + timezone.timedelta(days=i)).count()
                for i in range(7)
            ]
        }

    elif user.is_medecin():
        try:
            medecin = user.profil_medecin
            data = {
                'total_rdv': RendezVous.objects.filter(medecin=medecin).count(),
                'en_attente': RendezVous.objects.filter(medecin=medecin, statut='programme').count(),
                'du_jour': RendezVous.objects.filter(medecin=medecin, date_heure_rdv__date=now.date()).count()
            }
        except Medecin.DoesNotExist:
            pass

    elif user.is_patient():
        try:
            patient = user.profil_patient
            data = {
                'rdv_passes': RendezVous.objects.filter(patient=patient, date_heure_rdv__lt=now).count(),
                'rdv_a_venir': RendezVous.objects.filter(patient=patient, date_heure_rdv__gte=now).count()
            }
        except Patient.DoesNotExist:
            pass

    return JsonResponse(data)


@login_required(login_url='users:login')
@permission_required('users.can_manage_appointments', raise_exception=True)
def liste_rendez_vous(request):
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_filter = request.GET.get('date', '').strip()  # format YYYY-MM-DD attendu
    # Base queryset
    rdvs = RendezVous.objects.all()

    # Filtre recherche (nom/prénom du patient ou motif)
    if search_query:
        rdvs = rdvs.filter(
            Q(patient__user__nom__icontains=search_query) |
            Q(patient__user__prenom__icontains=search_query) |
            Q(motif__icontains=search_query) |
            Q(medecin__user__nom__icontains=search_query) |
            Q(medecin__user__prenom__icontains=search_query)
        )

    # Filtre statut
    if status_filter:
        rdvs = rdvs.filter(statut=status_filter)

    # Filtre date (si fourni) — on compare la portion date
    if date_filter:
        try:
            rdvs = rdvs.filter(date_heure_rdv__date=date_filter)
        except Exception:
            # ignore invalid date formats
            pass

    # Tri
    rdvs = rdvs.order_by('-date_heure_rdv')

    # Polling JSON endpoint (optimisé)
    if request.GET.get('json') == '1':
        last_count = int(request.GET.get('last_count', '0') or 0)
        current = rdvs.count()
        if last_count == current:
            return JsonResponse({'changed': False})
        # renvoyer un petit payload utile
        data = [{
            'id': r.id,
            'date': r.date_heure_rdv.isoformat(),
            'patient': f"{r.patient.user.nom} {r.patient.user.prenom}",
            'statut': r.statut,
        } for r in rdvs]
        return JsonResponse({'changed': True, 'last_count': current, 'rdvs': data})

    # Pagination / table-only
    paginator = Paginator(rdvs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'rdvs': rdvs,
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'statuses': RendezVous.STATUT_CHOICES,
        'date_filter': date_filter,
    }

    # requête table-only (fragment)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('table-only'):
        return render(request, 'rdv/admin/rdvs/composants/rdvs_table.html', context)

    # AJAX navigation (content)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'rdv/admin/rdvs/composants/rdvs_content.html', context)

    # page complète
    return render(request, 'rdv/admin/rdvs/rdvs.html', context)

# Modifier un rdv
@login_required(login_url='users:login')
@permission_required('users.can_manage_appointments', raise_exception=True)
def edit_rdv(request, rdv_id):
    """Créer un nouvel utilisateur (admin uniquement)"""
    rdv = RendezVous.objects.get(pk=rdv_id)
    if request.method == 'POST':
        form = UpdateRDVForm(request.POST, instance=rdv)
        if form.is_valid():
            rdv = form.save()
            messages.success(request, f'Le Rendez-vous a été modifié avec succès!')
            return redirect('/rdv/rdvs')  # Redirige vers la liste des Rendez-vous
    else:
        form = UpdateRDVForm(instance=rdv)
    
    return render(request, 'rdv/admin/rdvs/modifier.html', {'form': form})


# Supprimer un rdv
@login_required(login_url='users:login')
@permission_required('users.can_manage_appointments', raise_exception=True)
def delete_rdv(request, rdv_id):
    rdv = RendezVous.objects.get(pk=rdv_id)
    rdv.delete()
    messages.success(request, f'Le Rendez-vous a été supprimé avec succès!')
    return redirect('/rdv/rdvs')


# Les vues pour le rapport


@login_required(login_url='users:login')
@permission_required('users.can_view_statistics', raise_exception=True)
def statistiques_generales(request):
    """Statistiques générales du système"""
    
    # Compter les utilisateurs par type
    total_patients = Patient.objects.count()
    total_medecins = Medecin.objects.count()
    total_rdv = RendezVous.objects.count()
    
    # RDV par statut
    rdv_par_statut = dict(RendezVous.objects.values('statut').annotate(count=Count('id')))
    
    # RDV du mois en cours
    debut_mois = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    rdv_mois_courant = RendezVous.objects.filter(date_heure_rdv__gte=debut_mois).count()
    
    # RDV d'aujourd'hui
    aujourd_hui = timezone.now().date()
    rdv_aujourd_hui = RendezVous.objects.filter(date_heure_rdv__date=aujourd_hui).count()
    
    # Notifications non lues
    notifs_non_lues = Notification.objects.filter(is_read=False).count()
    
    # Messages bot du jour
    messages_bot_jour = MessageBot.objects.filter(date_echange__date=aujourd_hui).count()
    
    # Croissance des utilisateurs (7 derniers jours)
    il_y_a_7_jours = timezone.now() - timedelta(days=7)
    nouveaux_patients = Patient.objects.filter(user__date_joined__gte=il_y_a_7_jours).count()
    nouveaux_medecins = Medecin.objects.filter(user__date_joined__gte=il_y_a_7_jours).count()
    
    stats = {
        'totaux': {
            'patients': total_patients,
            'medecins': total_medecins,
            'rdv_total': total_rdv,
            'rdv_mois': rdv_mois_courant,
            'rdv_aujourd_hui': rdv_aujourd_hui,
            'notifs_non_lues': notifs_non_lues,
            'messages_bot_jour': messages_bot_jour
        },
        'croissance': {
            'nouveaux_patients': nouveaux_patients,
            'nouveaux_medecins': nouveaux_medecins
        },
        'rdv_par_statut': rdv_par_statut
    }
    
    return JsonResponse(stats, encoder=DjangoJSONEncoder)




""" 
    
    Les vues du medecin 
    
    """

# Tableau de bord du medecin
@login_required(login_url='users:login')
def dashboard_medecin_view(request):
    """Vue du tableau de bord pour le medecin"""
    now = timezone.now()
    debut_semaine = now - timezone.timedelta(days=now.weekday())
    debut_mois = now.replace(day=1)
    debut_jour = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    try:
        med = request.user.profil_medecin
    except Medecin.DoesNotExist:
        return HttpResponseForbidden("Vous n'êtes pas autorisé à accéder à cette page.")


    context = {
        'total_rendez_vous': RendezVous.objects.filter(medecin=med).count(),
        'total_confirmes': RendezVous.objects.filter(statut='confirme', medecin=med).count(),
        'total_annules': RendezVous.objects.filter(statut='annule', medecin=med).count(),
        'total_en_cours': RendezVous.objects.filter(statut='en_cours', medecin=med).count(),
        'total_programmes': RendezVous.objects.filter(statut='programme', medecin=med).count(),
        'total_termines': RendezVous.objects.filter(statut='termine', medecin=med).count(),

        'rendez_vous_semaine': RendezVous.objects.filter(date_creation__gte=debut_semaine, medecin=med).count(),
        'rendez_vous_mois': RendezVous.objects.filter(date_creation__gte=debut_mois, medecin=med).count(),
        'rendez_vous_aujour': RendezVous.objects.filter(date_creation__gte=debut_jour, medecin=med).count(),

         # Notifications récentes
        'notifications': Notification.objects.filter(user=request.user).order_by('-date_envoi')[:5],
    
        # RDV récents
        'rdvs_recents': RendezVous.objects.filter(medecin=med).order_by('-date_heure_rdv')[:5],
    
    }

    # Si c'est une requête AJAX, on renvoie JUSTE le fragment
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
       return render(request, 'rdv/doctor/composants/dashboard/dash_content.html', context)

    # Sinon on renvoie base.html, qui inclura via {% block content %} ton dashboard.html complet
    return render(request, 'rdv/doctor/dash_doctor.html', context)


@login_required(login_url='users:login')
def liste_rdv_medecin(request):
    # Récupérer le profil Medecin lié à l’utilisateur
    try:
        medecin = request.user.profil_medecin
    except Medecin.DoesNotExist:
        return HttpResponseForbidden("Vous n'êtes pas autorisé à accéder à cette page.")

    # Préparer les filtres (lecture des params envoyés par le JS)
    search_query  = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_filter   = request.GET.get('date', '').strip()  # format YYYY-MM-DD

    # Charger uniquement ses propres rendez-vous
    qs = RendezVous.objects.filter(medecin=medecin)

    # Appliquer la recherche (sur nom/prénom du patient seulement)
    if search_query:
        qs = qs.filter(
            Q(patient__user__nom__icontains=search_query) |
            Q(patient__user__prenom__icontains=search_query)
        )

    # Filtrer par statut si fourni (les valeurs doivent être les clés : 'programme', 'confirme', etc.)
    if status_filter:
        qs = qs.filter(statut=status_filter)

    # Filtrer par date si fourni (on compare la date seulement)
    if date_filter:
        try:
            # si date_filter au format YYYY-MM-DD
            qs = qs.filter(date_heure_rdv__date=date_filter)
        except Exception:
            pass

    # Trier
    qs = qs.order_by('-date_heure_rdv')

    # Pagination
    paginator   = Paginator(qs, 25)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    context = {
        'rdvs':          qs,            # utile si les templates anciens s'attendent à rdvs
        'page_obj':      page_obj,
        'search_query':  search_query,
        'status_filter': status_filter,
        'date_filter':   date_filter,
        'statuses':      RendezVous.STATUT_CHOICES,
    }

    # Rendu AJAX table-only : renvoie le fragment du tableau
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('table-only'):
        # Fournir les deux variables pour compatibilité template (rdvs ou page_obj)
        return render(request, 'rdv/doctor/composants/rdvs/rdvs_doctor_table.html', {
            'page_obj': page_obj,
            'rdvs': page_obj.object_list,
        })

    # Rendu AJAX "contenu complet" (filtre + header)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'rdv/doctor/composants/rdvs/rdvs_doctor_content.html', context)

    # Page complète
    return render(request, 'rdv/doctor/rdvs_doctor.html', context)

try:
    from .utils import create_and_send_notification
except Exception:
    create_and_send_notification = None


logger = logging.getLogger(__name__)

@login_required
@require_POST
def confirmer_rdv(request, rdv_id):
    medecin = getattr(request.user, 'profil_medecin', None)
    if medecin is None:
        return HttpResponseForbidden("Accès refusé")

    try:
        with transaction.atomic():
            rdv = RendezVous.objects.select_for_update().get(id=rdv_id)

            if not user_can_manage_rdv(request.user, rdv):
                return HttpResponseForbidden("Accès refusé")

            if not rdv.can_transition_to('confirme'):
                return JsonResponse({'success': False, 'error': 'Transition non autorisée'}, status=400)

            rdv.confirm(by_user=request.user)

            RdvHistory.objects.create(
                rdv=rdv,
                action="confirme",
                performed_by=request.user,
                description="Rendez-vous confirmé"
            )

    except RendezVous.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rendez-vous introuvable'}, status=404)
    except Exception as e:
        logger.exception("Erreur lors de la confirmation RDV %s : %s", rdv_id, e)
        return JsonResponse({'success': False, 'error': 'Erreur serveur'}, status=500)

    return JsonResponse({
        'success': True,
        'statut': rdv.statut,
        'statut_label': rdv.get_statut_display(),
        'rdv_id': rdv.id,
    })

@login_required
@require_http_methods(["GET", "POST"])
def annuler_rdv(request, rdv_id):
    medecin = getattr(request.user, 'profil_medecin', None)
    if medecin is None:
        return HttpResponseForbidden("Accès refusé")

    try:
        rdv = RendezVous.objects.get(id=rdv_id, medecin=medecin)
    except RendezVous.DoesNotExist:
        return HttpResponseForbidden("Rendez-vous introuvable")

    # --- GET ---
    if request.method == 'GET':
        form = AnnulerRdvForm(initial={'description': rdv.raison_annulation or ''})
        return render(
            request,
            'rdv/doctor/composants/rdvs/rdv_cancel_form.html',
            {'rdv': rdv, 'form': form}
        )

    # --- POST ---
    data = {}
    if request.content_type and request.content_type.startswith('application/json'):
        try:
            data = json.loads(request.body.decode('utf-8') or "{}")
        except Exception:
            return HttpResponseBadRequest("Payload JSON invalide")
    else:
        data = request.POST.dict() if request.POST else {}

    form = AnnulerRdvForm(data)
    if not form.is_valid():
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    description = form.cleaned_data.get('description', '').strip()[:1000]

    try:
        with transaction.atomic():
            rdv = RendezVous.objects.select_for_update().get(id=rdv_id)
            if not user_can_manage_rdv(request.user, rdv):
                return HttpResponseForbidden("Accès refusé")
            if not rdv.can_transition_to('annule'):
                return JsonResponse({'success': False, 'error': 'Transition non autorisée'}, status=400)

            rdv.cancel(description=description, by_user=request.user)

            RdvHistory.objects.create(
                rdv=rdv,   # ⚠️ adapter au vrai champ de ton modèle
                action="annule",
                performed_by=request.user,
                description=f"Rendez-vous annulé. Raison: {description}"
            )

    except RendezVous.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rendez-vous introuvable'}, status=404)
    except Exception as e:
        logger.exception("Erreur annuler_rdv %s: %s", rdv_id, e)
        return JsonResponse({'success': False, 'error': 'Erreur serveur'}, status=500)


    return JsonResponse({
        'success': True,
        'statut': rdv.statut,
        'statut_label': rdv.get_statut_display(),
        'rdv_id': rdv.id,
    })


@login_required
@require_http_methods(["GET", "POST"])
def reporter_rdv(request, rdv_id):
    is_medecin = hasattr(request.user, 'profil_medecin') or getattr(request.user, 'role', '') == 'medecin'
    initiator = 'medecin' if is_medecin else 'patient'

    try:
        rdv = RendezVous.objects.get(id=rdv_id)
    except RendezVous.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rendez-vous introuvable'}, status=404)

    if initiator == 'medecin':
        if not hasattr(request.user, 'profil_medecin') or rdv.medecin != request.user.profil_medecin:
            return HttpResponseForbidden("Accès refusé")
    else:
        if not hasattr(request.user, 'profil_patient') or rdv.patient != request.user.profil_patient:
            return HttpResponseForbidden("Accès refusé")

    # --- GET ---
    if request.method == 'GET':
        form = ReporterRdvForm()  # <--- garder ce form uniquement pour l'affichage
        return render(
            request,
            'rdv/doctor/composants/rdvs/rdv_report_form.html',
            {'rdv': rdv, 'form': form}
        )

    # --- POST ---
    data = {}
    if request.content_type and request.content_type.startswith('application/json'):
        try:
            data = json.loads(request.body.decode('utf-8') or "{}")
        except Exception:
            return HttpResponseBadRequest("Payload JSON invalide")
    else:
        data = request.POST.dict() if request.POST else {}

    date_val = data.get('nouvelle_date')
    time_val = data.get('nouvelle_heure')
    raison = (data.get('raison') or '').strip()

    if not date_val or not time_val:
        return JsonResponse({'success': False, 'error': 'Date et heure requises'}, status=400)

    try:
        naive_dt = datetime.fromisoformat(f"{date_val}T{time_val}")
    except Exception:
        try:
            naive_dt = datetime.strptime(f"{date_val} {time_val}", "%Y-%m-%d %H:%M")
        except Exception:
            return JsonResponse({'success': False, 'error': 'Format date/heure invalide'}, status=400)

    tz = timezone.get_current_timezone()
    new_dt = timezone.make_aware(naive_dt, tz) if timezone.is_naive(naive_dt) else naive_dt

    if new_dt <= timezone.now():
        return JsonResponse({'success': False, 'error': 'La nouvelle date doit être dans le futur'}, status=400)

    # Vérification de conflit
    duration = getattr(rdv, 'duree_minutes', 30) or 30
    new_start = new_dt
    new_end = new_dt + timedelta(minutes=duration)

    window_start = new_start - timedelta(days=1)
    window_end = new_end + timedelta(days=1)
    candidates = RendezVous.objects.filter(
        medecin=rdv.medecin,
        date_heure_rdv__gte=window_start,
        date_heure_rdv__lte=window_end
    ).exclude(id=rdv.id)

    for other in candidates:
        other_start = other.date_heure_rdv
        other_duration = getattr(other, 'duree_minutes', 30) or 30
        other_end = other_start + timedelta(minutes=other_duration)
        if other_start < new_end and other_end > new_start:
            return JsonResponse({'success': False, 'error': 'Conflit avec un autre rendez-vous.'}, status=400)

    try:
        with transaction.atomic():
            rdv = RendezVous.objects.select_for_update().get(id=rdv_id)
            if not user_can_manage_rdv(request.user, rdv):
                return HttpResponseForbidden("Accès refusé")
            if not rdv.can_transition_to('reporte'):
                return JsonResponse({'success': False, 'error': 'Transition non autorisée'}, status=400)

            rdv.report(new_dt, raison=raison, initiator=initiator, by_user=request.user)

            RdvHistory.objects.create(
                rdv=rdv,  
                action="reporte",
                performed_by=request.user,
                description=f"Rendez-vous déplacé au {new_dt} (raison: {raison})"
            )

    except RendezVous.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rendez-vous introuvable'}, status=404)
    except Exception as e:
        logger.exception("Erreur reporter_rdv %s: %s", rdv_id, e)
        return JsonResponse({'success': False, 'error': 'Erreur serveur'}, status=500)


    return JsonResponse({
        'success': True,
        'statut': rdv.statut,
        'statut_label': rdv.get_statut_display(),
        'rdv_id': rdv.id,
        'nouvelle_date_iso': rdv.date_heure_rdv.isoformat(),
        'report_initiator': rdv.report_initiator
    })



@login_required
@require_http_methods(["GET", "POST"])
def notifier_rdv(request, rdv_id):
    """
    GET -> renvoie le fragment HTML du formulaire de notification
    POST -> envoie la notification manuelle
    """
    try:
        rdv = RendezVous.objects.get(id=rdv_id)
    except RendezVous.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Rendez-vous introuvable'}, status=404)

    # Seul le médecin propriétaire peut notifier
    if not hasattr(request.user, 'profil_medecin') or rdv.medecin != request.user.profil_medecin:
        return HttpResponseForbidden("Accès refusé")

    # --- GET ---
    if request.method == 'GET':
        form = NotifierRdvForm()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            # fragment uniquement
            return render(request, "rdv/doctor/composants/rdvs/rdv_notif_form.html", {"rdv": rdv, "form": form})
        else:
            # éventuellement wrapper complet si tu veux
            return render(request, "rdv/doctor/composants/rdvs/rdv_notif_form.html", {"rdv": rdv, "form": form})

    # --- POST ---
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({'success': False, 'error': 'Payload JSON invalide'}, status=400)

    subject = data.get("subject", "").strip()
    message = data.get("message", "").strip()

    if not subject or not message:
        return JsonResponse({'success': False, 'error': 'Sujet et message sont requis'}, status=400)

    # Notification manuelle (pas de message par défaut)
    try:
        send_manual_notification(rdv.patient.user, subject, message, rdv=rdv, by_user=request.user)
    except Exception as e:
        logger.exception("Erreur envoi notif manuelle rdv %s: %s", rdv.id, e)
        return JsonResponse({'success': False, 'error': 'Erreur serveur'}, status=500)

    return JsonResponse({'success': True})


@login_required(login_url='users:login')
def disponibilites_list(request):
    # 1. Sécurité
    try:
        medecin = request.user.profil_medecin
    except Medecin.DoesNotExist:
        return HttpResponseForbidden()

    # 2. Base queryset
    qs = Disponibilite.objects.filter(medecin=medecin)

    # 3. Récupère filtres depuis GET
    type_filter = request.GET.get('type', '').strip()        # '', 'ponctuel', 'hebdomadaire'
    jour_filter = request.GET.get('jour', '').strip()        # ex: 'mon','tue',...
    date_filter = request.GET.get('date', '').strip()        # format attendu: 'YYYY-MM-DD'

    # 4. Applique les filtres côté serveur
    # Si type demandé
    if type_filter == 'ponctuel':
        qs = qs.filter(date_specific__isnull=False)
        if date_filter:
            qs = qs.filter(date_specific=date_filter)
    elif type_filter == 'hebdomadaire':
        qs = qs.filter(date_specific__isnull=True)
        if jour_filter:
            qs = qs.filter(jour=jour_filter)
    else:
        # pas de type forcé : appliquer jour/date si fournis
        if date_filter:
            qs = qs.filter(date_specific=date_filter)
        if jour_filter:
            qs = qs.filter(jour=jour_filter, date_specific__isnull=True)

    # 5. Tri
    qs = qs.order_by('date_specific', 'jour', 'heure_debut')

    # 6. Pagination
    page_obj = Paginator(qs, 25).get_page(request.GET.get('page'))

    # 7. JSON polling (respecte les mêmes filtres car 'qs' est filtré)
    if request.GET.get('json') == '1':
        last_count = int(request.GET.get('last_count', '0') or 0)
        current = qs.count()
        if last_count == current:
            return JsonResponse({'changed': False})
        data = [{
            'id': d.id,
            'jour': d.jour or (d.date_specific.isoformat() if d.date_specific else ''),
            'heure_debut': d.heure_debut.strftime('%H:%M'),
            'heure_fin': d.heure_fin.strftime('%H:%M'),
        } for d in qs]
        return JsonResponse({'changed': True, 'last_count': current, 'disponibilites': data})

    # 8. Fragment table-only ?
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('table-only'):
        return render(request, 'rdv/doctor/composants/dispo/dispo_table.html', {
            'page_obj': page_obj,
        })

    # 9. Page complète : passe aussi les valeurs de filtres pour utiliser dans le template (pagination links)
    return render(request, 'rdv/doctor/disponibilites.html', {
        'page_obj': page_obj,
        'type_filter': type_filter,
        'jour_filter': jour_filter,
        'date_filter': date_filter,
    })


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'

def errors_to_dict(errors):
    """
    Normalize Django form/errors/ValidationError into a plain dict of lists.
    Accepts:
      - ErrorDict / form.errors
      - ValidationError with message_dict or messages
    """
    if isinstance(errors, ValidationError):
        md = getattr(errors, 'message_dict', None)
        if md:
            return {k: [str(m) for m in v] for k, v in md.items()}
        return {'__all__': [str(m) for m in errors.messages]}
    # form.errors is an ErrorDict: convert to normal dict of lists
    try:
        return {k: [str(msg) for msg in v] for k, v in errors.items()}
    except Exception:
        # fallback: string
        return {'__all__': [str(errors)]}

@login_required(login_url='users:login')
@require_http_methods(["GET", "POST"])
def disponibilite_add(request):
    """
    GET (AJAX)  -> fragment HTML du formulaire (modal)
    POST (AJAX) -> renvoie JSON (status ok / erreurs)
    POST non-AJAX -> redirect (fallback)
    """
    medecin = get_object_or_404(Medecin, user=request.user)

    # base instance with medecin to avoid RelatedObjectDoesNotExist in model.clean
    base_instance = Disponibilite(medecin=medecin)

    if request.method == 'GET':
        form = DisponibiliteCreateForm(instance=base_instance, medecin=medecin)
        return render(request, 'rdv/doctor/composants/dispo/dispo_add_form.html', {'form': form})

    # POST
    form = DisponibiliteCreateForm(request.POST, instance=base_instance, medecin=medecin)
    if not form.is_valid():
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': errors_to_dict(form.errors)}, status=400)
        # fallback: render fragment with errors (rare if you don't use page)
        return render(request, 'rdv/doctor/composants/dispo/dispo_add_form.html', {'form': form})

    dispo = form.save(commit=False)
    dispo.medecin = medecin
    try:
        with transaction.atomic():
            dispo.full_clean()  # execute model.clean()
            dispo.save()
    except ValidationError as ve:
        errs = errors_to_dict(ve)
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': errs}, status=400)
        # attach to form then re-render fragment
        for f, msgs in errs.items():
            if f == '__all__':
                form.add_error(None, msgs)
            else:
                for m in msgs:
                    form.add_error(f, m)
        return render(request, 'rdv/doctor/composants/dispo/dispo_add_form.html', {'form': form})
    except IntegrityError:
        msg = "Un créneau identique existe déjà pour ce médecin (même jour/date et mêmes heures)."
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': {'__all__': [msg]}}, status=409)
        form.add_error(None, msg)
        return render(request, 'rdv/doctor/composants/dispo/dispo_add_form.html', {'form': form})
    except Exception as e:
        # logger.exception(e)  # si tu as un logger
        msg = "Erreur serveur lors de l'enregistrement."
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': {'__all__': [msg]}}, status=500)
        form.add_error(None, msg)
        return render(request, 'rdv/doctor/composants/dispo/dispo_add_form.html', {'form': form})

    # succès
    if _is_ajax(request):
        return JsonResponse({'status': 'ok', 'id': dispo.id})
    return redirect('rdv:disponibilites_list')


@login_required(login_url='users:login')
@require_http_methods(["GET", "POST"])
def disponibilite_edit(request, pk):
    medecin = get_object_or_404(Medecin, user=request.user)
    dispo = get_object_or_404(Disponibilite, pk=pk, medecin=medecin)

    if request.method == 'GET':
        form = DisponibiliteEditForm(instance=dispo, medecin=medecin)
        return render(request, 'rdv/doctor/composants/dispo/dispo_edit_form.html', {'form': form, 'disponibilite': dispo})

    # POST
    form = DisponibiliteEditForm(request.POST, instance=dispo, medecin=medecin)
    if not form.is_valid():
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': errors_to_dict(form.errors)}, status=400)
        return render(request, 'rdv/doctor/composants/dispo/dispo_edit_form.html', {'form': form, 'disponibilite': dispo})

    try:
        with transaction.atomic():
            updated = form.save(commit=False)
            updated.medecin = medecin
            updated.full_clean()
            updated.save()
    except ValidationError as ve:
        errs = errors_to_dict(ve)
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': errs}, status=400)
        for f, msgs in errs.items():
            if f == '__all__':
                form.add_error(None, msgs)
            else:
                for m in msgs:
                    form.add_error(f, m)
        return render(request, 'rdv/doctor/composants/dispo/dispo_edit_form.html', {'form': form, 'disponibilite': dispo})
    except IntegrityError:
        msg = "Un créneau identique existe déjà pour ce médecin (même jour/date et mêmes heures)."
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': {'__all__': [msg]}}, status=409)
        form.add_error(None, msg)
        return render(request, 'rdv/doctor/composants/dispo/dispo_edit_form.html', {'form': form, 'disponibilite': dispo})
    except Exception as e:
        # logger.exception(e)
        msg = "Erreur serveur lors de la mise à jour."
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': {'__all__': [msg]}}, status=500)
        form.add_error(None, msg)
        return render(request, 'rdv/doctor/composants/dispo/dispo_edit_form.html', {'form': form, 'disponibilite': dispo})

    # succès
    if _is_ajax(request):
        return JsonResponse({'status': 'ok', 'id': dispo.id})
    return redirect('rdv:disponibilites_list')

@login_required(login_url='users:login')
@require_POST
def disponibilite_delete(request, pk):
    medecin = get_object_or_404(Medecin, user=request.user)
    disponibilite = get_object_or_404(Disponibilite, pk=pk, medecin=medecin)
    disponibilite.delete()
    return JsonResponse({'success': True})







""" 
    
    Les vues du Patient 
    
    """

@login_required(login_url='users:login')
def dashboard_patient_view(request):
    """Vue du tableau de bord pour le patient"""
    now = timezone.now()
    debut_semaine = now - timezone.timedelta(days=now.weekday())
    debut_mois = now.replace(day=1)
    debut_jour = now.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        patient = request.user.profil_patient
    except Patient.DoesNotExist:
        return HttpResponseForbidden("Vous n'êtes pas autorisé à accéder à cette page.")

    context = {
        # Statistiques générales
        'total_rdv': RendezVous.objects.filter(patient=patient).count(),
        'rdv_a_venir': RendezVous.objects.filter(patient=patient, date_heure_rdv__gte=now).count(),
        'rdv_passes': RendezVous.objects.filter(patient=patient, date_heure_rdv__lt=now).count(),

        # Statuts détaillés
        'total_confirmes': RendezVous.objects.filter(patient=patient, statut='confirme').count(),
        'total_annules': RendezVous.objects.filter(patient=patient, statut='annule').count(),
        'total_programmes': RendezVous.objects.filter(patient=patient, statut='programme').count(),
        'total_reportes': RendezVous.objects.filter(patient=patient, statut='reporte').count(),

        # Périodes
        'rdv_semaine': RendezVous.objects.filter(patient=patient, date_creation__gte=debut_semaine).count(),
        'rdv_mois': RendezVous.objects.filter(patient=patient, date_creation__gte=debut_mois).count(),
        'rdv_aujour': RendezVous.objects.filter(patient=patient, date_creation__date=now.date()).count(),

        # Notifications récentes
        'notifications': Notification.objects.filter(user=request.user).order_by('-date_envoi')[:5],

        # RDV récents
        'rdvs_recents': RendezVous.objects.filter(patient=patient).order_by('-date_heure_rdv')[:5],
    }

    # Requête AJAX → fragment HTML uniquement
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'rdv/patient/composants/dashboard/dash_content.html', context)

    # Page complète
    return render(request, 'rdv/patient/dash_patient.html', context)



@login_required(login_url='users:login')
def liste_rdv_patient(request):
    # Récupérer le profil Patient lié à l’utilisateur
    try:
        patient = request.user.profil_patient
    except Patient.DoesNotExist:
        return HttpResponseForbidden("Vous n'êtes pas autorisé à accéder à cette page.")

    # Préparer les filtres (lecture des params envoyés par le JS)
    search_query  = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_filter   = request.GET.get('date', '').strip()  # format YYYY-MM-DD

    # Charger uniquement ses propres rendez-vous
    qs = RendezVous.objects.filter(patient=patient)

    # Appliquer la recherche (sur nom/prénom du Médecin seulement)
    if search_query:
        qs = qs.filter(
            Q(medecin__user__nom__icontains=search_query) |
            Q(medecin__user__prenom__icontains=search_query)
        )

    # Filtrer par statut si fourni (les valeurs doivent être les clés : 'programme', 'confirme', etc.)
    if status_filter:
        qs = qs.filter(statut=status_filter)

    # Filtrer par date si fourni (on compare la date seulement)
    if date_filter:
        try:
            # si date_filter au format YYYY-MM-DD
            qs = qs.filter(date_heure_rdv__date=date_filter)
        except Exception:
            pass

    # Trier
    qs = qs.order_by('-date_heure_rdv')

    # Pagination
    paginator   = Paginator(qs, 25)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    context = {
        'rdvs':          qs,           
        'page_obj':      page_obj,
        'search_query':  search_query,
        'status_filter': status_filter,
        'date_filter':   date_filter,
        'statuses':      RendezVous.STATUT_CHOICES,
    }

    # Rendu AJAX table-only : renvoie le fragment du tableau
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('table-only'):
        # Fournir les deux variables pour compatibilité template (rdvs ou page_obj)
        return render(request, 'rdv/patient/composants/rdvs/rdvs_patient_table.html', {
            'page_obj': page_obj,
            'rdvs': page_obj.object_list,
        })
    
    # Rendu AJAX "contenu complet" (filtre + header)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'rdv/patient/composants/rdvs/rdvs_patient_content.html', context)

    # Page complète
    return render(request, 'rdv/patient/rdvs_patient.html', context)


@login_required
def prendre_rdv(request):
    """Interface principale pour prendre RDV"""
    patient = get_object_or_404(Patient, user=request.user)
    
    # Médecins favoris
    favoris = FavoriMedecin.objects.filter(patient=patient).select_related('medecin__user')
    
    # Historique des RDV pour suggestions
    historique = RendezVous.objects.filter(
        patient=patient,
        statut='termine'
    ).values('medecin__specialite').annotate(count=Count('id')).order_by('-count')[:3]

    from types import SimpleNamespace
    medecins_par_specialite = Medecin.objects.values('specialite').annotate(count=Count('id'))
    counts_dict = {item['specialite']: item['count'] for item in medecins_par_specialite}
    medecins_counts = SimpleNamespace(**counts_dict)

    context = {
        'medecins_counts': medecins_counts,
        'medecins': Medecin.objects.all(),
        'specialites': Medecin.SPECIALITES,
        'medecins_favoris': favoris,
        'specialites_frequentes': historique,
        'patient': patient
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'rdv/patient/composants/prendre_rdv/prendre_rdv_content.html', context)
    return render(request, 'rdv/patient/prendre_rdv.html', context)

@login_required
def api_search_medecins(request):
    """API recherche médecins avec filtres"""
    specialite = request.GET.get('specialite')
    search = request.GET.get('q', '')
    disponible_semaine = request.GET.get('dispo_semaine') == '1'
    
    medecins = Medecin.objects.filter(accepte_nouveaux_patients=True)
    
    if specialite:
        medecins = medecins.filter(specialite=specialite)
    
    if search:
        medecins = medecins.filter(
            Q(user__nom__icontains=search) |
            Q(user__prenom__icontains=search) |
            Q(cabinet__icontains=search)
        )
    
    # Calcul disponibilités si demandé
    if disponible_semaine:
        fin_semaine = timezone.now() + timedelta(days=7)
        medecins_ids = []
        for m in medecins:
            if m.prochaine_disponibilite and m.prochaine_disponibilite <= fin_semaine:
                medecins_ids.append(m.id)
        medecins = medecins.filter(id__in=medecins_ids)
    
    # Limiter résultats
    medecins = medecins[:20]
    
    data = []
    for m in medecins:
        prochaine = m.prochaine_disponibilite
        data.append({
            'id': m.id,
            'nom': m.user.nom_complet(),
            'specialite': m.specialite, 
            'specialite_label': m.get_specialite_display(),
            'cabinet': m.cabinet,
            'photo_url': m.photo.url if m.photo else None,
            'tarif': str(m.tarif_consultation) if m.tarif_consultation else None,
            'langues': m.langues_parlees,
            'prochaine_dispo': prochaine.isoformat() if prochaine else None,
            'delai_moyen': m.delai_moyen_rdv
        })
    
    return JsonResponse({'medecins': data})

@login_required
def api_creneaux_medecin(request, medecin_id):
    """API créneaux disponibles d'un médecin"""
    medecin = get_object_or_404(Medecin, id=medecin_id)
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    if not date_debut:
        date_debut = timezone.now()
    else:
        date_debut = datetime.fromisoformat(date_debut)
    
    if not date_fin:
        date_fin = date_debut + timedelta(days=30)
    else:
        date_fin = datetime.fromisoformat(date_fin)
    
    # Récupérer disponibilités
    creneaux = []
    current = date_debut.date()
    
    while current <= date_fin.date():
        # Disponibilités hebdomadaires
        jour_semaine = ['mon','tue','wed','thu','fri','sat','sun'][current.weekday()]
        dispos_jour = Disponibilite.objects.filter(
            medecin=medecin,
            jour=jour_semaine,
            is_active=True,
            date_specific__isnull=True
        )
        
        # Disponibilités spécifiques
        dispos_spec = Disponibilite.objects.filter(
            medecin=medecin,
            date_specific=current,
            is_active=True
        )
        
        for dispo in list(dispos_jour) + list(dispos_spec):
            # Générer créneaux de 30 min
            heure = dispo.heure_debut
            while heure < dispo.heure_fin:
                dt = timezone.make_aware(
                    datetime.combine(current, heure)
                )
                
                # Vérifier si créneau libre
                if not RendezVous.objects.filter(
                    medecin=medecin,
                    date_heure_rdv=dt,
                    statut__in=['programme', 'confirme', 'en_cours']
                ).exists():
                    creneaux.append({
                        'datetime': dt.isoformat(),
                        'date': current.isoformat(),
                        'heure': heure.strftime('%H:%M'),
                        'disponible': True
                    })
                
                # Incrémenter de 30 min
                heure = (datetime.combine(current, heure) + timedelta(minutes=30)).time()
        
        current += timedelta(days=1)
    
    return JsonResponse({
        'medecin_id': medecin.id,
        'creneaux': creneaux
    })

@login_required
@require_POST
def api_reserver_rdv(request):
    """API pour confirmer la réservation"""
    data = json.loads(request.body)
    patient = get_object_or_404(Patient, user=request.user)
    medecin = get_object_or_404(Medecin, id=data['medecin_id'])
    
    # Parser datetime
    dt = datetime.fromisoformat(data['datetime'])
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    
    # Vérifier disponibilité
    if RendezVous.objects.filter(
        medecin=medecin,
        date_heure_rdv=dt,
        statut__in=['programme', 'confirme']
    ).exists():
        return JsonResponse({'success': False, 'error': 'Créneau déjà pris'}, status=400)
    
    # Créer RDV
    rdv = RendezVous.objects.create(
        patient=patient,
        medecin=medecin,
        date_heure_rdv=dt,
        motif=data.get('motif', ''),
        statut='programme',
        duree_minutes=30
    )
    
    # Notification
    from rdv.utils import create_and_send_notification
    create_and_send_notification(
        patient.user,
        "Rendez-vous programmé",
        f"Votre RDV avec Dr. {medecin.user.nom_complet()} le {dt.strftime('%d/%m/%Y à %H:%M')} est confirmé.",
        rdv=rdv
    )
    
    return JsonResponse({
        'success': True,
        'rdv_id': rdv.id,
        'message': 'Rendez-vous réservé avec succès'
    })

@login_required
@require_POST  
def api_toggle_favori(request, medecin_id):
    """Ajouter/retirer médecin des favoris"""
    patient = get_object_or_404(Patient, user=request.user)
    medecin = get_object_or_404(Medecin, id=medecin_id)
    
    favori, created = FavoriMedecin.objects.get_or_create(
        patient=patient,
        medecin=medecin
    )
    
    if not created:
        favori.delete()
        return JsonResponse({'added': False})
    
    return JsonResponse({'added': True})