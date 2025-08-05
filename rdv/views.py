from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.http import require_POST, require_http_methods
from .models import RendezVous, Notification, Patient, Medecin, Disponibilite
from django.utils import timezone
from users.models import Utilisateur # Importer le modèle Utilisateur
from django.contrib import messages # Importer les messages pour les notifications
from django.contrib.auth.decorators import login_required           # Importer le décorateur pour les vues nécessitant une connexion    
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from .forms import UpdateRDVForm, DisponibiliteForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.template.loader import render_to_string



# Create your views here.

def acceuil_view(request):
    return render(request, 'rdv/acceuil.html')

""" Vues pour les notifications """

@login_required
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



@login_required
@require_POST
def mark_as_read(request, notification_id):
    """Marquer une notification comme lue"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    return redirect('list_notif')

@login_required
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

@login_required
@require_POST
def delete_notification(request, notification_id):
    """Supprimer une notification"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    
    return redirect('list_notif')

@login_required
@require_POST
def delete_all_notifications(request):
    """Supprimer toutes les notifications"""
    Notification.objects.filter(user=request.user).delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'message': 'Toutes les notifications ont été supprimées'})
    
    messages.success(request, 'Toutes les notifications ont été supprimées.')
    return redirect('list_notif')

@login_required
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

# Fonction utilitaire pour créer des notifications
def create_notification(user, message, notification_type='info', category='system'):
    """Crée une nouvelle notification pour un utilisateur"""
    notification = Notification.objects.create(
        user=user,
        message=message,
        type=notification_type,
        category=category
    )
    return notification

# Exemples de notifications spécifiques au système médical
def notify_appointment_confirmed(patient, appointment):
    """Notification de confirmation de rendez-vous pour le patient"""
    message = f"Votre rendez-vous du {appointment.date} à {appointment.heure} avec Dr. {appointment.medecin.nom} a été confirmé."
    create_notification(patient.user, message, 'success', 'appointment')

def notify_appointment_cancelled(patient, appointment):
    """Notification d'annulation de rendez-vous pour le patient"""  
    message = f"Votre rendez-vous du {appointment.date} à {appointment.heure} avec Dr. {appointment.medecin.nom} a été annulé."
    create_notification(patient.user, message, 'warning', 'appointment')

def notify_new_appointment(medecin, appointment):
    """Notification de nouveau rendez-vous pour le médecin"""
    message = f"Nouveau rendez-vous programmé le {appointment.date} à {appointment.heure} avec {appointment.patient.nom}."
    create_notification(medecin.user, message, 'info', 'appointment')




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

            'rendez_vous_semaine': RendezVous.objects.filter(date_heure_rdv__gte=debut_semaine).count(),
            'rendez_vous_mois': RendezVous.objects.filter(date_heure_rdv__gte=debut_mois).count(),
            'rendez_vous_aujour': RendezVous.objects.filter(date_heure_rdv__gte=debut_jour).count(),
            'jours_semaine': jours_semaine,
            'rendez_vous_jour': [
                RendezVous.objects.filter(date_heure_rdv__date=debut_jour + timezone.timedelta(days=i)).count()
                for i in range(7)
            ],
            'notifications': Notification.objects.filter(user=request.user)[:5],
            'rdvs_recents': RendezVous.objects.all().order_by('-date_heure_rdv')[:5]
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

# Liste des rdvs
@login_required(login_url='users:login')
@permission_required('users.can_manage_appointments', raise_exception=True)
def liste_rendez_vous(request):
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    rdvs = RendezVous.objects.all()

    if search_query:
        rdvs = rdvs.filter(
            Q(patient__user__nom__icontains=search_query) |
            Q(patient__user__prenom__icontains=search_query) |
            Q(medecin__user__nom__icontains=search_query) |
            Q(medecin__user__prenom__icontains=search_query)
        )

    if status_filter:
        rdvs = rdvs.filter(statut=status_filter)

    rdvs = rdvs.order_by('-date_heure_rdv')

    # Pagination
    paginator = Paginator(rdvs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'rdvs': rdvs,
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'statuses': RendezVous.STATUT_CHOICES,
    }
    # Si on ne veut que la table
    if request.GET.get('table-only') == '1':
        return render(request, 'rdv/admin/rdvs/composants/rdvs_table.html', context)

    # Si c'est un appel AJAX de navigation
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'rdv/admin/rdvs/composants/rdvs_content.html', context)

    # Sinon Page complète
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




""" Les vues du medecin """

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

        'rendez_vous_semaine': RendezVous.objects.filter(date_heure_rdv__gte=debut_semaine, medecin=med).count(),
        'rendez_vous_mois': RendezVous.objects.filter(date_heure_rdv__gte=debut_mois, medecin=med).count(),
        'rendez_vous_aujour': RendezVous.objects.filter(date_heure_rdv__gte=debut_jour, medecin=med).count(),
    }

    # Si c'est une requête AJAX, on renvoie JUSTE le fragment
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
       return render(request, 'rdv/doctor/composants/dash_content.html', context)

    # Sinon on renvoie base.html, qui inclura via {% block content %} ton dashboard.html complet
    return render(request, 'rdv/doctor/dash_doctor.html', context)

# Liste des rdvs du medecin
@login_required(login_url='users:login')
def liste_rdv_medecin(request):
    # Récupérer le profil Medecin lié à l’utilisateur
    try:
        medecin = request.user.profil_medecin
    except Medecin.DoesNotExist:
        return HttpResponseForbidden("Vous n'êtes pas autorisé à accéder à cette page.")

    # Préparer les filtres
    search_query  = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    # Charger uniquement ses propres rendez-vous
    rdvs = RendezVous.objects.filter(medecin=medecin)

    # Appliquer la recherche (sur nom/prénom du patient et motif)
    if search_query:
        rdvs = rdvs.filter(
            Q(patient__user__nom__icontains=search_query) |
            Q(patient__user__prenom__icontains=search_query) |
            Q(motif__icontains=search_query)
        )

    # Filtrer par statut si besoin
    if status_filter:
        rdvs = rdvs.filter(statut=status_filter)

    # Trier et paginer
    rdvs = rdvs.order_by('-date_heure_rdv')
    paginator   = Paginator(rdvs, 25)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)

    context = {
        'rdvs':          rdvs,
        'page_obj':      page_obj,
        'search_query':  search_query,
        'status_filter': status_filter,
        'statuses':      RendezVous.STATUT_CHOICES,
    }

    # Rendu AJAX ou complet
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return render(request, 'rdv/doctor/composants/rdvs_doctor_content.html', context)
    return render(request, 'rdv/doctor/rdvs_doctor.html', context)

@login_required(login_url='users:login')
def disponibilites_list(request):
    # 1. Sécurité
    try:
        medecin = request.user.profil_medecin
    except Medecin.DoesNotExist:
        return HttpResponseForbidden()

    # 2. Filtre et recherche
    qs = Disponibilite.objects.filter(medecin=medecin, is_active=True)
    search = request.GET.get('search','')
    if search:
        qs = qs.filter(Q(jour__icontains=search) | Q(date_specific__icontains=search))

    # 3. Tri
    qs = qs.order_by('date_specific','jour','heure_debut')

    # 4. Pagination (HTML/table fragment)
    page_obj = Paginator(qs, 25).get_page(request.GET.get('page'))

    # 5. JSON polling ?
    if request.GET.get('json') == '1':
        last_count = int(request.GET.get('last_count','0') or 0)
        current = qs.count()
        if last_count == current:
            return JsonResponse({'changed': False})
        data = [{
            'id': d.id,
            'jour': d.jour or d.date_specific.isoformat(),
            'heure_debut': d.heure_debut.strftime('%H:%M'),
            'heure_fin': d.heure_fin.strftime('%H:%M'),
        } for d in qs]
        return JsonResponse({'changed': True, 'last_count': current, 'disponibilites': data})

    # 6. Fragment table-only ?
    if request.headers.get('X-Requested-With')=='XMLHttpRequest' and request.GET.get('table-only'):
        return render(request, 'rdv/doctor/composants/dispo_table_fragment.html', {
            'page_obj': page_obj,
        })

    # 7. Calendrier FullCalendar ?
    if request.GET.get('calendar') == '1':
        events = []
        for d in qs:
            for start,end in d.get_slot_datetimes():
                events.append({
                    'id': d.id,
                    'title': str(d),
                    'start': start.isoformat(),
                    'end': end.isoformat(),
                })
        return JsonResponse(events, safe=False)

    # 8. Page complète
    return render(request, 'rdv/doctor/disponibilites.html', {
        'page_obj':      page_obj,
        'search_query':  search,
        'form':          DisponibiliteForm(),
    })


# Ajouter une disponibilite par medecin
@login_required(login_url='users:login')
@require_http_methods(["GET", "POST"])
def disponibilite_add(request):
    # Récupère le médecin ou interdit l’accès
    medecin = get_object_or_404(Medecin, user=request.user)

    # Instancie le form, en POST ou vide en GET
    form = DisponibiliteForm(request.POST or None)

    # Si c’est un POST et que le form est valide
    if request.method == 'POST' and form.is_valid():
        dispo = form.save(commit=False)
        dispo.medecin = medecin
        dispo.save()

        # Si AJAX, on renvoie juste JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok', 'id': dispo.id})

        # Sinon, on redirige vers la liste classique
        return redirect('rdv:disponibilites_list')

    # Sur GET ou si form invalide, on renvoie uniquement le fragment du form
    return render(
        request,
        'rdv/doctor/composants/dispo_add_form.html',
        {'form': form}
    )

@login_required(login_url='users:login')
@require_POST
def disponibilite_edit(request, pk):
    medecin = get_object_or_404(Medecin, user=request.user)
    disponibilite = get_object_or_404(Disponibilite, pk=pk, medecin=medecin)
    form = DisponibiliteForm(request.POST, instance=disponibilite)
    if form.is_valid():
        form.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'errors': form.errors})

@login_required(login_url='users:login')
@require_POST
def disponibilite_delete(request, pk):
    medecin = get_object_or_404(Medecin, user=request.user)
    disponibilite = get_object_or_404(Disponibilite, pk=pk, medecin=medecin)
    disponibilite.delete()
    return JsonResponse({'success': True})
