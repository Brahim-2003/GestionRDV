from datetime import timedelta, datetime, date as date_cls

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
import csv
from django.utils.dateparse import parse_datetime
from django.db.models.functions import TruncMonth, TruncWeek, TruncDay


logger = logging.getLogger(__name__)





# App imports
from users.models import Utilisateur
from .forms import UpdateRDVForm, DisponibiliteHebdoCreateForm, DisponibiliteHebdoEditForm, DisponibiliteSpecifiqueCreateForm, DisponibiliteSpecifiqueEditForm, AnnulerRdvForm, ReporterRdvForm, NotifierRdvForm, RendezVousForm
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
    
    now = timezone.now()
    debut_semaine = now - timezone.timedelta(days=now.weekday())
    debut_mois = now.replace(day=1)
    debut_jour = now.replace(hour=0, minute=0, second=0, microsecond=0)
    jours_semaine = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

    data = {
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


# Les vues pour l'historique des RDV
@login_required
def rdv_history_list(request):
    """
    Vue principale pour afficher l'historique des rendez-vous.
    Gère les filtres par action, date, utilisateur et recherche.
    Supporte les requêtes AJAX pour le chargement dynamique.
    """
    
    # Récupération de tous les historiques (avec optimisation des requêtes)
    # select_related charge les relations en une seule requête SQL
    history_list = RdvHistory.objects.select_related(
        'rdv', 
        'performed_by',
        'rdv__patient',
        'rdv__medecin'
    ).all()
    
    # === FILTRES ===
    
    # Filtre par type d'action (create, confirm, cancel, etc.)
    action_filter = request.GET.get('action', 'all')
    if action_filter and action_filter != 'all':
        history_list = history_list.filter(action=action_filter)
    
    # Filtre par utilisateur (qui a effectué l'action)
    user_filter = request.GET.get('user', '')
    if user_filter:
        history_list = history_list.filter(
            Q(performed_by__nom__icontains=user_filter) | Q(performed_by__prenom__icontains=user_filter)
        )
    # Filtre par période de temps
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from:
        # Filtre les enregistrements à partir de cette date
        history_list = history_list.filter(timestamp__gte=date_from)
    
    if date_to:
        # Filtre les enregistrements jusqu'à cette date (inclus toute la journée)
        from django.utils import timezone
        import datetime
        date_to_obj = datetime.datetime.strptime(date_to, '%Y-%m-%d')
        date_to_end = timezone.make_aware(
            datetime.datetime.combine(date_to_obj, datetime.time.max)
        )
        history_list = history_list.filter(timestamp__lte=date_to_end)
    
    # Recherche globale dans la description
    search_query = request.GET.get('search', '')
    if search_query:
        history_list = history_list.filter(
            Q(description__icontains=search_query) |
            Q(old_value__icontains=search_query) |
            Q(new_value__icontains=search_query) |
            Q(rdv__patient__user__nom__icontains=search_query) |
            Q(rdv__patient__user__prenom__icontains=search_query)
        )
    
    # Filtre par ID de RDV spécifique (utile pour voir l'historique d'un seul RDV)
    rdv_id = request.GET.get('rdv_id', '')
    if rdv_id:
        history_list = history_list.filter(rdv_id=rdv_id)
    
    # === PAGINATION ===
    # On affiche 20 éléments par page pour ne pas surcharger l'interface
    paginator = Paginator(history_list, 20)
    page_number = request.GET.get('page', 1)
    history_page = paginator.get_page(page_number)
    
    # === STATISTIQUES ===
    # Calcul du nombre d'actions par type pour afficher dans l'interface
    action_stats = {}
    all_history = RdvHistory.objects.all()  # Sans filtres pour les stats globales
    for action_code, action_label in RdvHistory.ACTION_CHOICES:
        action_stats[action_code] = all_history.filter(action=action_code).count()
    
    # Total des enregistrements après filtrage
    total_count = history_list.count()
    
    # === CONTEXTE ===
    context = {
        'history_items': history_page,  # Les éléments de la page courante
        'action_stats': action_stats,    # Statistiques par type d'action
        'total_count': total_count,      # Nombre total après filtres
        'current_filter': action_filter, # Filtre actif pour le surlignage dans l'UI
        'current_user_filter': user_filter,
        'current_search': search_query,
        'current_date_from': date_from,
        'current_date_to': date_to,
        'current_rdv_id': rdv_id,
        'action_choices': RdvHistory.ACTION_CHOICES,  # Pour générer les filtres
        'page_obj': history_page,  # Pour la pagination
    }
    
    # === RÉPONSE ===
    # Si c'est une requête AJAX, on renvoie seulement le fragment HTML
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'rdv/admin/history/composants/history_contents.html', context)
    
    # Sinon, on renvoie la page complète avec le template de base
    return render(request, 'rdv/admin/history/rdv_history.html', context)


@login_required
def rdv_detail_history(request, rdv_id):
    """
    Vue pour afficher l'historique complet d'un rendez-vous spécifique.
    Utile pour voir toutes les modifications d'un RDV particulier.
    """
    try:
        rdv = RendezVous.objects.get(id=rdv_id)
    except RendezVous.DoesNotExist:
        from django.http import HttpResponseNotFound
        return HttpResponseNotFound("Rendez-vous non trouvé")
    
    # Récupère tout l'historique de ce RDV
    history_list = RdvHistory.objects.filter(rdv=rdv).select_related(
        'performed_by'
    ).order_by('-timestamp')
    
    context = {
        'rdv': rdv,
        'history_items': history_list,
        'total_count': history_list.count(),
    }
    
    # Support AJAX pour charger dynamiquement
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'rdv/admin/history/composants/history_detail_contents.html', context)
    
    return render(request, 'rdv/admin/history/rdv_history_detail.html', context)


# Les vues pour le rapport

@login_required
def dashboard_stats(request):
    """Vue principale du dashboard (template page rapports)."""
    try:
        total_patients = Patient.objects.count()
        total_medecins = Medecin.objects.count()
        total_rdv = RendezVous.objects.count()
        # utilise la date locale/aware
        rdv_aujourd_hui = RendezVous.objects.filter(
            date_heure_rdv__date=timezone.localdate()
        ).count()

        context = {
            'total_patients': total_patients,
            'total_medecins': total_medecins,
            'total_rdv': total_rdv,
            'rdv_aujourd_hui': rdv_aujourd_hui,
        }
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return render(request, 'rdv/admin/rapport/composants/rapport_content.html', context)

        # Vérifie que le template existe à ce chemin ; adapte si nécessaire
        return render(request, 'rdv/admin/rapport/rapport.html', context)
    except Exception as e:
        logger.exception("Erreur dashboard_stats : %s", e)
        # page d'erreur simplifiée (évite 500 brut)
        return render(request, 'rdv/admin/rapport/rapport.html', {'error': 'Impossible de charger le dashboard.'})


# ----------------------
# API: Overview (général)
# ----------------------
@login_required
def stats_api_overview(request):
    """
    Renvoie un JSON regroupant :
    - overview (counts)
    - rdv_statuts (counts par statut)
    - nouveaux_patients (6 derniers mois, format [{'month': 'YYYY-MM', 'count': n}, ...])
    - rdv_par_mois (6 derniers mois)
    - top_medecins (liste avec total_rdv / rdv_confirmes / rdv_annules)
    - specialites_stats (top spécialités par nombre de RDV)
    """
    try:
        # Overview
        total_patients = Patient.objects.count()
        total_medecins = Medecin.objects.count()
        total_rdv = RendezVous.objects.count()
        rdv_aujourd_hui = RendezVous.objects.filter(date_heure_rdv__date=timezone.localdate()).count()

        # RDV par statut
        rdv_statuts_qs = RendezVous.objects.values('statut').annotate(count=Count('id')).order_by('statut')
        rdv_statuts = list(rdv_statuts_qs)

        # 6 derniers mois
        six_months_ago = timezone.now() - timedelta(days=180)

        # Nouveaux patients par mois (on utilise Utilisateur.role == 'patient')
        nouveaux_patients_qs = (
            Utilisateur.objects
            .filter(role='patient', date_inscription__gte=six_months_ago)
            .annotate(month=TruncMonth('date_inscription'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        nouveaux_patients = [
            {'month': item['month'].strftime('%Y-%m'), 'count': item['count']} for item in nouveaux_patients_qs
        ]

        # RDV par mois (6 derniers mois)
        rdv_par_mois_qs = (
            RendezVous.objects
            .filter(date_creation__gte=six_months_ago)
            .annotate(month=TruncMonth('date_creation'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        rdv_par_mois = [
            {'month': item['month'].strftime('%Y-%m'), 'count': item['count']} for item in rdv_par_mois_qs
        ]

        # Top médecins (total rdv, confirmés, annulés) — format compatible JS attendu
        top_medecins_qs = (
            Medecin.objects
            .annotate(
                total_rdv=Count('rendez_vous'),
                rdv_confirmes=Count('rendez_vous', filter=Q(rendez_vous__statut='confirme')),
                rdv_annules=Count('rendez_vous', filter=Q(rendez_vous__statut='annule'))
            )
            .values(
                'user__nom',
                'user__prenom',
                'specialite',
                'total_rdv',
                'rdv_confirmes',
                'rdv_annules'
            )
            .order_by('-total_rdv')[:10]
        )
        top_medecins = list(top_medecins_qs)

        # Spécialités les plus demandées (depuis les RDV)
        specialites_qs = (
            RendezVous.objects
            .values('medecin__specialite')
            .annotate(count=Count('id'))
            .order_by('-count')[:10]
        )
        specialites_stats = [{'specialite': s['medecin__specialite'], 'count': s['count']} for s in specialites_qs]

        return JsonResponse({
            'overview': {
                'total_patients': total_patients,
                'total_medecins': total_medecins,
                'total_rdv': total_rdv,
                'rdv_aujourd_hui': rdv_aujourd_hui
            },
            'rdv_statuts': rdv_statuts,
            'nouveaux_patients': nouveaux_patients,
            'rdv_par_mois': rdv_par_mois,
            'top_medecins': top_medecins,
            'specialites_stats': specialites_stats
        })
    except Exception as e:
        logger.exception("Erreur stats_api_overview : %s", e)
        return JsonResponse({'error': 'Erreur serveur lors de la construction de l\'overview.'}, status=500)


# ----------------------
# API: RDV (timeline / annulation / par statut)
# ----------------------
@login_required
def stats_api_rdv(request):
    """
    Paramètre GET:
      - periode: '7', '30', '90', '365' (jours) — default '30'
    Retour:
      - rdv_timeline: [{'period': 'YYYY-MM-DD', 'count': n}, ...]
      - rdv_statuts_periode: [{'statut': 'confirme', 'count': n}, ...]
      - annulation_stats: [{ 'medecin__user__nom': ..., 'medecin__user__prenom': ..., 'total_rdv':n, 'annules':m, 'taux_annulation':x }, ...]
      - periode: valeur retournée (string)
    """
    try:
        periode = request.GET.get('periode', '30')
        now = timezone.now()

        if periode == '7':
            date_debut = now - timedelta(days=7)
            truncate_func = TruncDay
        elif periode == '30':
            date_debut = now - timedelta(days=30)
            truncate_func = TruncDay
        elif periode == '90':
            date_debut = now - timedelta(days=90)
            truncate_func = TruncWeek
        else:  # '365' ou autre
            date_debut = now - timedelta(days=365)
            truncate_func = TruncMonth

        # Timeline
        rdv_timeline_qs = (
            RendezVous.objects
            .filter(date_creation__gte=date_debut)
            .annotate(period=truncate_func('date_creation'))
            .values('period')
            .annotate(count=Count('id'))
            .order_by('period')
        )

        rdv_timeline = []
        for item in rdv_timeline_qs:
            period_val = item['period']
            # period_val peut être datetime.date ou datetime
            if hasattr(period_val, 'strftime'):
                # Pour TruncMonth on veut YYYY-MM (ou YYYY-MM-01)
                if truncate_func is TruncMonth:
                    rdv_timeline.append({'period': period_val.strftime('%Y-%m'), 'count': item['count']})
                else:
                    rdv_timeline.append({'period': period_val.strftime('%Y-%m-%d'), 'count': item['count']})
            else:
                rdv_timeline.append({'period': str(period_val), 'count': item['count']})

        # RDV par statut dans la période
        rdv_statuts_periode_qs = (
            RendezVous.objects
            .filter(date_creation__gte=date_debut)
            .values('statut')
            .annotate(count=Count('id'))
        )
        rdv_statuts_periode = list(rdv_statuts_periode_qs)

        # Annulation par médecin (top 10 par total rdv)
        annulation_qs = (
            RendezVous.objects
            .filter(date_creation__gte=date_debut)
            .values('medecin__user__nom', 'medecin__user__prenom')
            .annotate(
                total_rdv=Count('id'),
                annules=Count('id', filter=Q(statut='annule'))
            )
            .order_by('-total_rdv')[:10]
        )
        annulation_stats = []
        for item in annulation_qs:
            total = item.get('total_rdv', 0) or 0
            annules = item.get('annules', 0) or 0
            taux = round((annules / total) * 100, 2) if total > 0 else 0
            annulation_stats.append({
                'medecin__user__nom': item.get('medecin__user__nom'),
                'medecin__user__prenom': item.get('medecin__user__prenom'),
                'total_rdv': total,
                'annules': annules,
                'taux_annulation': taux
            })

        return JsonResponse({
            'rdv_timeline': rdv_timeline,
            'rdv_statuts_periode': rdv_statuts_periode,
            'annulation_stats': annulation_stats,
            'periode': periode
        })
    except Exception as e:
        logger.exception("Erreur stats_api_rdv : %s", e)
        return JsonResponse({'error': 'Erreur serveur lors de la récupération des stats RDV.'}, status=500)


# ----------------------
# API: Patients
# ----------------------
@login_required
def stats_api_patients(request):
    """
    Renvoie:
      - patients_sexe: [{'sexe': 'M', 'count': n}, ...]
      - ages_data: [{'age_group': '0-18', 'count': n}, ...]
      - patients_actifs: [{'user__nom': ..., 'user__prenom': ..., 'nombre_rdv': n}, ...]
      - inscriptions_evolution: [{'month': 'YYYY-MM', 'count': n}, ...]
    """
    try:
        # Répartition par sexe
        patients_sexe_qs = Patient.objects.values('sexe').annotate(count=Count('id'))
        patients_sexe = list(patients_sexe_qs)

        # Répartition par âge (calcul simple)
        today = timezone.localdate()
        ages_stats = {
            '0-18': 0,
            '19-30': 0,
            '31-50': 0,
            '51-70': 0,
            '70+': 0
        }

        patients = Patient.objects.select_related('user').all()
        for p in patients:
            try:
                dob = p.date_naissance
                # age calcul robuste
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            except Exception:
                age = 0
            if age <= 18:
                ages_stats['0-18'] += 1
            elif age <= 30:
                ages_stats['19-30'] += 1
            elif age <= 50:
                ages_stats['31-50'] += 1
            elif age <= 70:
                ages_stats['51-70'] += 1
            else:
                ages_stats['70+'] += 1

        ages_data = [{'age_group': k, 'count': v} for k, v in ages_stats.items()]

        # Patients les plus actifs (par nombre de RDV)
        patients_actifs_qs = (
            Patient.objects
            .annotate(nombre_rdv=Count('rendez_vous'))
            .filter(nombre_rdv__gt=0)
            .values('user__nom', 'user__prenom', 'nombre_rdv')
            .order_by('-nombre_rdv')[:10]
        )
        patients_actifs = list(patients_actifs_qs)

        # Evolution inscriptions (6 derniers mois) -> Utilisateur.role == 'patient'
        six_months_ago = timezone.now() - timedelta(days=180)
        inscriptions_qs = (
            Utilisateur.objects
            .filter(role='patient', date_inscription__gte=six_months_ago)
            .annotate(month=TruncMonth('date_inscription'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        inscriptions_evolution = [
            {'month': item['month'].strftime('%Y-%m'), 'count': item['count']} for item in inscriptions_qs
        ]

        return JsonResponse({
            'patients_sexe': patients_sexe,
            'ages_data': ages_data,
            'patients_actifs': patients_actifs,
            'inscriptions_evolution': inscriptions_evolution
        })
    except Exception as e:
        logger.exception("Erreur stats_api_patients : %s", e)
        return JsonResponse({'error': 'Erreur serveur lors de la récupération des stats patients.'}, status=500)


# ----------------------
# API: Médecins
# ----------------------
@login_required
def stats_api_medecins(request):
    """
    Renvoie:
      - specialites_repartition
      - medecins_performance (total_rdv, rdv_confirmes, rdv_annules + taux)
      - medecins_sexe
      - disponibilites_stats (nombre disponibilités actives)
    """
    try:
        # Répartition par spécialité (médecins)
        specialites_repartition_qs = Medecin.objects.values('specialite').annotate(count=Count('id')).order_by('-count')
        specialites_repartition = list(specialites_repartition_qs)

        # Performance des médecins
        medecins_perf_qs = (
            Medecin.objects
            .annotate(
                total_rdv=Count('rendez_vous'),
                rdv_confirmes=Count('rendez_vous', filter=Q(rendez_vous__statut='confirme')),
                rdv_annules=Count('rendez_vous', filter=Q(rendez_vous__statut='annule'))
            )
            .values(
                'user__nom',
                'user__prenom',
                'specialite',
                'total_rdv',
                'rdv_confirmes',
                'rdv_annules'
            )
            .order_by('-total_rdv')[:15]
        )
        medecins_performance = []
        for m in medecins_perf_qs:
            total = m.get('total_rdv', 0) or 0
            confirms = m.get('rdv_confirmes', 0) or 0
            annules = m.get('rdv_annules', 0) or 0
            taux_confirmation = round((confirms / total) * 100, 2) if total > 0 else 0
            taux_annulation = round((annules / total) * 100, 2) if total > 0 else 0
            medecins_performance.append({
                **m,
                'taux_confirmation': taux_confirmation,
                'taux_annulation': taux_annulation
            })

        # Médecins par sexe
        medecins_sexe_qs = Medecin.objects.values('sexe').annotate(count=Count('id'))
        medecins_sexe = list(medecins_sexe_qs)

        # Disponibilités moyennes / nombre de disponibilités actives
        disponibilites_qs = (
            Medecin.objects
            .annotate(nombre_disponibilites=Count('disponibilites', filter=Q(disponibilites__is_active=True)))
            .values('user__nom', 'user__prenom', 'specialite', 'nombre_disponibilites')
            .order_by('-nombre_disponibilites')[:10]
        )
        disponibilites_stats = list(disponibilites_qs)

        return JsonResponse({
            'specialites_repartition': specialites_repartition,
            'medecins_performance': medecins_performance,
            'medecins_sexe': medecins_sexe,
            'disponibilites_stats': disponibilites_stats
        })
    except Exception as e:
        logger.exception("Erreur stats_api_medecins : %s", e)
        return JsonResponse({'error': 'Erreur serveur lors de la récupération des stats médecins.'}, status=500)


# ----------------------
# Export CSV simple (général)
# ----------------------
@login_required
def export_stats(request):
    """Génère un CSV téléchargeable des principales métriques."""
    try:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="statistiques.csv"'

        writer = csv.writer(response)
        writer.writerow(['Type', 'Métrique', 'Valeur', 'Date'])

        # Général
        today = timezone.localdate()
        writer.writerow(['Général', 'Total Patients', Patient.objects.count(), today])
        writer.writerow(['Général', 'Total Médecins', Medecin.objects.count(), today])
        writer.writerow(['Général', 'Total RDV', RendezVous.objects.count(), today])

        # RDV par statut
        for s in RendezVous.objects.values('statut').annotate(count=Count('id')):
            writer.writerow(['RDV par statut', s['statut'], s['count'], today])

        # Spécialités (depuis rendez-vous)
        for spec in RendezVous.objects.values('medecin__specialite').annotate(count=Count('id')).order_by('-count'):
            writer.writerow(['Spécialités', spec['medecin__specialite'], spec['count'], today])

        return response
    except Exception as e:
        logger.exception("Erreur export_stats : %s", e)
        return HttpResponse("Erreur lors de l'export", status=500)


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
        'notifications': Notification.objects.filter(user=request.user).order_by('-date_envoi')[:3],
    
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
                rdv=rdv,   
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

    # --- Autorisations ---
    if initiator == 'medecin':
        if not hasattr(request.user, 'profil_medecin') or rdv.medecin != request.user.profil_medecin:
            return HttpResponseForbidden("Accès refusé")
    else:
        if not hasattr(request.user, 'profil_patient') or rdv.patient != request.user.profil_patient:
            return HttpResponseForbidden("Accès refusé")

    # --- GET ---
    if request.method == 'GET':
        form = ReporterRdvForm()
        return render(
            request,
            'rdv/doctor/composants/rdvs/rdv_report_form.html',
            {'rdv': rdv, 'form': form}
        )

    # --- POST ---
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

    # Conversion date + heure en datetime
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

    # Durée du RDV
    duration = getattr(rdv, 'duree_minutes', 30) or 30
    new_start = new_dt
    new_end = new_dt + timedelta(minutes=duration)

    # --- Vérification disponibilité du médecin ---
    weekday_map = {
        0: "mon", 1: "tue", 2: "wed", 3: "thu",
        4: "fri", 5: "sat", 6: "sun"
    }
    jour_code = weekday_map[new_start.weekday()]

    # Vérifier d'abord s’il existe une **exception spécifique inactive** (blocage ponctuel)
    exception_negative = Disponibilite.objects.filter(
        medecin=rdv.medecin,
        date_specific=new_start.date(),
        is_active=False
    ).exists()

    if exception_negative:
        return JsonResponse({'success': False, 'error': "Le médecin n'est pas disponible ce jour-là (exception)."}, status=400)

    # Chercher les dispos valides (spécifiques ou récurrentes)
    disponibilites = Disponibilite.objects.filter(
        medecin=rdv.medecin,
        is_active=True
    ).filter(
        Q(date_specific=new_start.date()) |
        Q(date_specific__isnull=True, jour=jour_code)
    )

    dispo_match = False
    for dispo in disponibilites:
        if dispo.heure_debut <= new_start.time() and dispo.heure_fin >= new_end.time():
            dispo_match = True
            break

    if not dispo_match:
        return JsonResponse({'success': False, 'error': 'Le médecin n\'est pas disponible à ce créneau.'}, status=400)

    # --- Vérification chevauchements RDV ---
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

    # --- Application du report ---
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


# vues pour la gestion des disponibilités du médecin
JOURS_SEMAINE = {
    'monday': 'Lundi',
    'tuesday': 'Mardi', 
    'wednesday': 'Mercredi',
    'thursday': 'Jeudi',
    'friday': 'Vendredi',
    'saturday': 'Samedi',
    'sunday': 'Dimanche'
}

# Mapping pour les choix du modèle Django (supposé)
JOURS_MAPPING = {
    'monday': 'mon',
    'tuesday': 'tue',
    'wednesday': 'wed',
    'thursday': 'thu',
    'friday': 'fri',
    'saturday': 'sat',
    'sunday': 'sun',
}
@login_required
def disponibilites_list(request):
    """Vue principale avec gestion des onglets"""
    type_filter = request.GET.get('type', '')
    jour_filter = request.GET.get('jour', '')
    date_filter = request.GET.get('date', '')
    page_num = request.GET.get('page', 1)

    medecin = get_object_or_404(Medecin, user=request.user)

    # Créneaux hebdomadaires groupés par jour
    weekly_slots = {}
    if not type_filter or type_filter == 'hebdomadaire':
        hebdo_dispos = medecin.disponibilites.filter(
            date_specific__isnull=True
        ).order_by('jour', 'heure_debut')
        
        # Grouper par jour (conversion mapping si nécessaire)
        for dispo in hebdo_dispos:
            # Si votre modèle utilise 'mon', 'tue', etc., convertir vers 'monday', etc.
            jour_key = None
            for eng_day, fr_day in JOURS_MAPPING.items():
                if dispo.jour == fr_day:  # 'mon' -> 'monday'
                    jour_key = eng_day
                    break
            
            if jour_key:
                if jour_key not in weekly_slots:
                    weekly_slots[jour_key] = []
                weekly_slots[jour_key].append(dispo)
    
    # Créneaux ponctuels avec filtrage
    ponctuel_query = medecin.disponibilites.filter(date_specific__isnull=False)
    
    if jour_filter:
        # Filtrer les ponctuels par jour de semaine si nécessaire
        pass  # Implémentation selon vos besoins
    
    if date_filter:
        ponctuel_query = ponctuel_query.filter(date_specific=date_filter)
    
    ponctuel_dispos = ponctuel_query.order_by('date_specific', 'heure_debut')
    
    # Pagination pour ponctuels
    paginator = Paginator(ponctuel_dispos, 10)
    page_obj = paginator.get_page(page_num)
    
    # AJAX pour table-only
    if request.GET.get('table-only') == '1':
        if type_filter == 'hebdomadaire':
            return render(request, 'rdv/doctor/composants/dispo/weekly_calendar.html', {
                'weekly_slots': weekly_slots,
                'days': JOURS_SEMAINE
            })
        else:
            return render(request, 'rdv/doctor/composants/dispo/dispo_table.html', {
                'page_obj': page_obj
            })
    
    context = {
        'weekly_slots': weekly_slots,
        'ponctuel_dispos': ponctuel_dispos,
        'page_obj': page_obj,
        'days': JOURS_SEMAINE,
        'type_filter': type_filter,
        'jour_filter': jour_filter,
        'date_filter': date_filter,
    }
    return render(request, 'rdv/doctor/disponibilites.html', context)



@login_required
@require_http_methods(["POST"])
def toggle_dispo_status(request, dispo_id):
    """Toggle l'état actif/inactif d'une disponibilité"""
    try:
        # CORRECTION : Récupérer via le médecin, pas directement via user
        medecin = get_object_or_404(Medecin, user=request.user)
        dispo = get_object_or_404(medecin.disponibilites, id=dispo_id)
        
        # Lire les données JSON
        data = json.loads(request.body)
        new_status = data.get('is_active')
        
        if new_status is not None:
            dispo.is_active = new_status
        else:
            # Fallback : toggle automatique
            dispo.is_active = not dispo.is_active
            
        dispo.save()
        
        return JsonResponse({
            'success': True,
            'is_active': dispo.is_active,
            'message': f"Créneau {'activé' if dispo.is_active else 'désactivé'}"
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Données JSON invalides'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

@login_required
def weekly_calendar_view(request):
    """Vue pour le fragment calendrier hebdomadaire"""
    medecin = get_object_or_404(Medecin, user=request.user)
    
    weekly_slots = {}
    hebdo_dispos = medecin.disponibilites.filter(
        date_specific__isnull=True
    ).order_by('jour', 'heure_debut')
    
    for dispo in hebdo_dispos:
        jour_key = None
        for eng_day, fr_day in JOURS_MAPPING.items():
            if dispo.jour == fr_day:
                jour_key = eng_day
                break
        
        if jour_key:
            if jour_key not in weekly_slots:
                weekly_slots[jour_key] = []
            weekly_slots[jour_key].append(dispo)
    
    return render(request, 'rdv/doctor/composants/dispo/weekly_calendar.html', {
        'weekly_slots': weekly_slots,
        'days': JOURS_SEMAINE
    })


@login_required
@require_http_methods(["GET", "POST"])
def disponibilite_hebdo_add(request, day_key):
    medecin = get_object_or_404(Medecin, user=request.user)
    
    
    if day_key not in JOURS_MAPPING:
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': {'__all__': ['Jour invalide']}}, status=400)
        return redirect('rdv:disponibilites_list')

    jour_model = JOURS_MAPPING[day_key]

    if request.method == 'GET':
        # Créer le formulaire avec le jour pré-sélectionné
        form = DisponibiliteHebdoCreateForm(medecin=medecin)
        form.initial['jour'] = jour_model
        
        return render(request, 'rdv/doctor/composants/dispo/dispo_hebdo_add.html', {
            'form': form,
            'day_key': day_key,
            'day_name': JOURS_SEMAINE.get(day_key, day_key.title()),
        })
    
    # POST - Créer une copie des données POST et forcer le jour
    post_data = request.POST.copy()
    post_data['jour'] = jour_model
    
    form = DisponibiliteHebdoCreateForm(post_data, medecin=medecin)
    
    if form.is_valid():
        try:
            with transaction.atomic():
                dispo = form.save(commit=False)
                dispo.medecin = medecin
                dispo.jour = jour_model  # Double assurance
                dispo.date_specific = None
                dispo.full_clean()
                dispo.save()
                
            if _is_ajax(request):
                return JsonResponse({'status': 'ok', 'id': dispo.id})
            return redirect('rdv:disponibilites_list')
            
        except Exception as e:
            if _is_ajax(request):
                return JsonResponse({'status': 'error', 'errors': {'__all__': [str(e)]}}, status=400)
            form.add_error(None, str(e))
    
    # En cas d'erreur
    if _is_ajax(request):
        return JsonResponse({'status': 'error', 'errors': errors_to_dict(form.errors)}, status=400)
    
    return render(request, 'rdv/doctor/composants/dispo/dispo_hebdo_add.html', {
        'form': form,
        'day_key': day_key,
        'day_name': JOURS_SEMAINE.get(day_key, day_key.title()),
    })



@login_required(login_url='users:login')
@require_http_methods(["GET", "POST"])
def disponibilite_hebdo_edit(request, pk):
    medecin = get_object_or_404(Medecin, user=request.user)
    dispo = get_object_or_404(Disponibilite, pk=pk, medecin=medecin)

    if request.method == "GET":
        form = DisponibiliteHebdoEditForm(instance=dispo)
        return render(request, 'rdv/doctor/composants/dispo/dispo_hebdo_edit_form.html', {
            'form': form,
            'disponibilite': dispo
        })

    # POST
    form = DisponibiliteHebdoEditForm(request.POST, instance=dispo)
    if form.is_valid():
        form.save()
        if _is_ajax(request):
            return JsonResponse({'status': 'ok', 'id': dispo.id})
        return redirect('rdv:disponibilites_list')

    # erreurs
    if _is_ajax(request):
        return JsonResponse({'status': 'error', 'errors': errors_to_dict(form.errors)}, status=400)
    return render(request, 'rdv/doctor/composants/dispo/dispo_hebdo_edit_form.html', {
        'form': form,
        'disponibilite': dispo
    })


@login_required
@require_http_methods(["POST"])  
def disponibilite_hebdo_delete(request, dispo_id):
    """Supprimer un créneau hebdomadaire"""
    medecin = get_object_or_404(Medecin, user=request.user)
    try:
        dispo = get_object_or_404(
            medecin.disponibilites.filter(date_specific__isnull=True), 
            id=dispo_id
        )
        dispo.delete()
        return JsonResponse({'success': True, 'message': 'Créneau supprimé'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


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
def disponibilite_specifique_add(request):
    """
    GET (AJAX)  -> fragment HTML du formulaire (modal)
    POST (AJAX) -> renvoie JSON (status ok / erreurs)
    POST non-AJAX -> redirect (fallback)
    """
    medecin = get_object_or_404(Medecin, user=request.user)

    # base instance with medecin to avoid RelatedObjectDoesNotExist in model.clean
    base_instance = Disponibilite(medecin=medecin)

    if request.method == 'GET':
        form = DisponibiliteSpecifiqueCreateForm(instance=base_instance, medecin=medecin)
        return render(request, 'rdv/doctor/composants/dispo/dispo_specifique_add.html', {'form': form})

    # POST
    form = DisponibiliteSpecifiqueCreateForm(request.POST, instance=base_instance, medecin=medecin)
    if not form.is_valid():
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': errors_to_dict(form.errors)}, status=400)
        # fallback: render fragment with errors (rare if you don't use page)
        return render(request, 'rdv/doctor/composants/dispo/dispo_specifique_add.html', {'form': form})

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
        return render(request, 'rdv/doctor/composants/dispo/dispo_specifique_add.html', {'form': form})
    except IntegrityError:
        msg = "Un créneau identique existe déjà pour ce médecin (même date et mêmes heures)."
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': {'__all__': [msg]}}, status=409)
        form.add_error(None, msg)
        return render(request, 'rdv/doctor/composants/dispo/dispo_specifique_add.html', {'form': form})
    except Exception as e:
        # logger.exception(e)  # si tu as un logger
        msg = "Erreur serveur lors de l'enregistrement."
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': {'__all__': [msg]}}, status=500)
        form.add_error(None, msg)
        return render(request, 'rdv/doctor/composants/dispo/dispo_specifique_add.html', {'form': form})

    # succès
    if _is_ajax(request):
        return JsonResponse({'status': 'ok', 'id': dispo.id})
    return redirect('rdv:disponibilites_list')


@login_required(login_url='users:login')
@require_http_methods(["GET", "POST"])
def disponibilite_specifique_edit(request, pk):
    medecin = get_object_or_404(Medecin, user=request.user)
    dispo = get_object_or_404(Disponibilite, pk=pk, medecin=medecin)

    if request.method == 'GET':
        form = DisponibiliteSpecifiqueEditForm(instance=dispo, medecin=medecin)
        return render(request, 'rdv/doctor/composants/dispo/dispo_specifique_edit.html', {'form': form, 'disponibilite': dispo})

    # POST
    form = DisponibiliteSpecifiqueEditForm(request.POST, instance=dispo, medecin=medecin)
    if not form.is_valid():
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': errors_to_dict(form.errors)}, status=400)
        return render(request, 'rdv/doctor/composants/dispo/dispo_specifique_edit.html', {'form': form, 'disponibilite': dispo})

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
        return render(request, 'rdv/doctor/composants/dispo/dispo_specifique_edit.html', {'form': form, 'disponibilite': dispo})
    except IntegrityError:
        msg = "Un créneau identique existe déjà pour ce médecin (même date et mêmes heures)."
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': {'__all__': [msg]}}, status=409)
        form.add_error(None, msg)
        return render(request, 'rdv/doctor/composants/dispo/dispo_specifique_edit.html', {'form': form, 'disponibilite': dispo})
    except Exception as e:
        # logger.exception(e)
        msg = "Erreur serveur lors de la mise à jour."
        if _is_ajax(request):
            return JsonResponse({'status': 'error', 'errors': {'__all__': [msg]}}, status=500)
        form.add_error(None, msg)
        return render(request, 'rdv/doctor/composants/dispo/dispo_specifique_edit.html', {'form': form, 'disponibilite': dispo})

    # succès
    if _is_ajax(request):
        return JsonResponse({'status': 'ok', 'id': dispo.id})
    return redirect('rdv:disponibilites_list')

@login_required(login_url='users:login')
@require_POST
def disponibilite_specifique_delete(request, pk):
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
        'patient': patient,
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
        'notifications': Notification.objects.filter(user=request.user).order_by('-date_envoi')[:3],

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
    """API créneaux disponibles d'un médecin (robuste)"""
    medecin = get_object_or_404(Medecin, id=medecin_id)
    tz = timezone.get_current_timezone()

    # Dates de début et fin
    date_debut_str = request.GET.get('date_debut')
    date_fin_str = request.GET.get('date_fin')

    try:
        date_debut = datetime.fromisoformat(date_debut_str) if date_debut_str else timezone.now()
        date_fin = datetime.fromisoformat(date_fin_str) if date_fin_str else date_debut + timedelta(days=30)
    except Exception:
        return JsonResponse({'success': False, 'error': 'Format date invalide'}, status=400)

    # Convertir en aware datetime
    if timezone.is_naive(date_debut):
        date_debut = timezone.make_aware(date_debut, tz)
    if timezone.is_naive(date_fin):
        date_fin = timezone.make_aware(date_fin, tz)

    creneaux = []
    current = date_debut.date()
    end_date = date_fin.date()

    while current <= end_date:
        # --- Vérifier exceptions spécifiques ---
        dispos_spec = Disponibilite.objects.filter(
            medecin=medecin,
            date_specific=current,
            is_active=True
        )

        # Vérifier si une exception négative existe (date_specific inactive)
        has_negative_exception = Disponibilite.objects.filter(
            medecin=medecin,
            date_specific=current,
            is_active=False
        ).exists()

        creneaux_jour = []

        if dispos_spec.exists():
            # Utiliser uniquement les disponibilités spécifiques actives
            for dispo in dispos_spec:
                heure = dispo.heure_debut
                while heure < dispo.heure_fin:
                    new_start = timezone.make_aware(datetime.combine(current, heure), tz)
                    new_end = new_start + timedelta(minutes=30)
                    
                    # Vérifier si créneau libre
                    conflict = RendezVous.objects.filter(
                        medecin=medecin,
                        date_heure_rdv__lt=new_end,
                        date_heure_rdv__gte=new_start,
                        statut__in=['programme', 'confirme', 'en_cours']
                    ).exists()
                    if not conflict:
                        creneaux_jour.append({
                            'datetime': new_start.isoformat(),
                            'date': current.isoformat(),
                            'heure': heure.strftime('%H:%M'),
                            'disponible': True
                        })
                    heure = (datetime.combine(current, heure) + timedelta(minutes=30)).time()

        elif not has_negative_exception:
            # Aucune disponibilité spécifique → utiliser les disponibilités récurrentes
            jour_semaine = ['mon','tue','wed','thu','fri','sat','sun'][current.weekday()]
            dispos_jour = Disponibilite.objects.filter(
                medecin=medecin,
                jour=jour_semaine,
                is_active=True,
                date_specific__isnull=True
            )
            for dispo in dispos_jour:
                heure = dispo.heure_debut
                while heure < dispo.heure_fin:
                    new_start = timezone.make_aware(datetime.combine(current, heure), tz)
                    new_end = new_start + timedelta(minutes=30)

                    conflict = RendezVous.objects.filter(
                        medecin=medecin,
                        date_heure_rdv__lt=new_end,
                        date_heure_rdv__gte=new_start,
                        statut__in=['programme', 'confirme', 'en_cours']
                    ).exists()
                    if not conflict:
                        creneaux_jour.append({
                            'datetime': new_start.isoformat(),
                            'date': current.isoformat(),
                            'heure': heure.strftime('%H:%M'),
                            'disponible': True
                        })
                    heure = (datetime.combine(current, heure) + timedelta(minutes=30)).time()

        # Ajouter les créneaux du jour
        creneaux.extend(creneaux_jour)
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
    
    # Parser datetime - CORRECTION ICI
    dt_str = data['datetime']
    
    # Si le format contient 'T', c'est un ISO local
    if 'T' in dt_str:
        # Parser la date locale (sans timezone)
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        
        # Si elle est naive (pas de timezone), la rendre aware avec la timezone locale
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
    else:
        # Fallback pour autres formats
        dt = datetime.fromisoformat(dt_str)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
    
    # Vérifier disponibilité
    end_time = dt + timedelta(minutes=30)
    if RendezVous.objects.filter(
        medecin=medecin,
        date_heure_rdv__lt=end_time,
        date_heure_rdv__gte=dt,
        statut__in=['programme', 'confirme']
    ).exists():
        return JsonResponse({'success': False, 'error': 'Créneau déjà pris'}, status=400)
    
    # Créer RDV
    rdv = RendezVous.objects.create(
        patient=patient,
        medecin=medecin,
        date_heure_rdv=dt,  # dt est maintenant correctement aware
        motif=data.get('motif', ''),
        statut='programme',
        duree_minutes=30
    )
    RdvHistory.objects.create(
        rdv=rdv,
        action="create",
        performed_by=request.user,
        description="Rendez-vous créé"
    )
    
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