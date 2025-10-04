from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator 
from django.db.models import Q, Max
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from django.views.decorators.http import require_POST, require_http_methods


# App imports
from .models import Utilisateur
from rdv.models import Patient, Medecin
from .forms import ConnexionForm, RegisterForm, UtilisateurCreationForm, UtilisateurUpdateForm, UserEditForm, PatientEditForm, MedecinEditForm, CustomPasswordChangeForm
from users.tasks import notify_admins_on_user_create


# Create your views here.

# ================== Décorateurs personnalisés ==================


# Vérifie si l'utilisateur est administrateur
def is_admin(user):
    return user.is_authenticated and user.role == 'admin'


# Décorateur pour vérifier le rôle de l'utilisateur
def role_required(allowed_roles):

    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('users:login')
            
            if request.user.role not in allowed_roles:
                messages.error(request, 'Vous n\'avez pas les permissions pour accéder à cette page.')
                return redirect('users:dashboard')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

# Décorateur qui renvoie 403 au lieu de rediriger vers login
def permission_required_with_403(perm):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('users:login')
            
            if not request.user.has_perm(perm):
                return HttpResponseForbidden("Vous n'avez pas la permission d'accéder à cette ressource.")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def permission_denied_view(request, exception=None):
    return HttpResponseForbidden(
        render(request, 'users/403.html'),
        content_type='text/html'
    )




# ================== Vues d'authentification ==================

# Vue de connexion

def connecter(request):
    # Si déjà connecté, redirige selon le rôle
    if request.user.is_authenticated:
        if request.user.role == 'admin':
            return redirect('rdv:dashboard_redirect')
        try:
            _ = request.user.profil_medecin
            return redirect('rdv:dashboard_medecin')
        except Medecin.DoesNotExist:
            pass
        try:
            _ = request.user.profil_patient
            return redirect('rdv:dashboard_patient')
        except Patient.DoesNotExist:
            pass
        return redirect('rdv:acceuil')

    form = ConnexionForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email    = form.cleaned_data['email']
        password = form.cleaned_data['password']
        user     = authenticate(request, username=email, password=password)

        if user and user.is_actif:
            login(request, user)
            if user.role == 'admin':
                return redirect('rdv:dashboard_redirect')
            try:
                _ = user.profil_medecin
                return redirect('rdv:dashboard_medecin')
            except Medecin.DoesNotExist:
                pass
            try:
                _ = user.profil_patient
                return redirect('rdv:dashboard_patient')
            except Patient.DoesNotExist:
                pass
            return redirect('rdv:acceuil')
        messages.error(request,
                       'Email ou mot de passe incorrect.' 
                       if not user else 
                       'Votre compte est désactivé.')
    
    return render(request, 'users/login.html', {'form': form})

# Vue d'inscription 
def inscription(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Votre compte a été créé !')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # on renvoie un JSON minimal
                return JsonResponse({'status': 'ok', 'user_id': user.id})
            return redirect('users:login')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # on renvoie les erreurs
                return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
    else:
        form = RegisterForm()
    return render(request, 'users/register.html', {'form': form})


# Vue de déconnexion
@login_required(login_url='users:login')
def deconnecter(request):
    logout(request)
    messages.info(request, 'Vous avez été déconnecté avec succès.')
    return redirect('users:login')



# Vue du profil utilisateur

# Vue du profil utilisateur
@login_required(login_url='users:login')
def profil_user(request, user_id):
    us = Utilisateur.objects.get(pk=user_id)
    if us.ROLE=='patient':  
        us_profil = Utilisateur.objects.filter(pk=user_id)
    elif us.ROLE=='medecin':
        us_profil = Utilisateur.objects.filter(pk=user_id)
    else:
        us_profil = us
    context = {"utilisateur" : get_object_or_404(Utilisateur, pk=user_id),
               "user_profil" : us_profil,
               }
    
    # si requête AJAX (navigation fragment)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'rdv/profil/profil_content.html', context)

    # Sinon page complète
    return render(request, 'rdv/admin/users/profil_user.html', context)


@login_required(login_url='users:login')
def profil_view(request):
    user = request.user

    # Récupérer le profil lié selon le rôle
    if user.role == 'patient':
        try:
            profil = user.profil_patient
        except:
            profil = None
    elif user.role == 'medecin':
        try:
            profil = user.profil_medecin
        except:
            profil = None
    else:
        profil = None  # admin n'a pas de profil associé

    context = {
        "utilisateur": user,
        "user_profil": profil,
    }

    # si requête AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'rdv/profil/mon_profil.html', context)

    # page complète selon rôle
    if user.role == 'admin':
        tpl = 'rdv/admin/users/profil.html'
    elif user.role == 'medecin':
        tpl = 'rdv/doctor/profil.html'
    else:
        tpl = 'rdv/patient/profil.html'

    return render(request, tpl, context)

@login_required
@require_http_methods(["GET", "POST"])
def edit_user_view(request):
    """Éditer les infos utilisateur (communes)"""
    user = request.user
    if request.method == "POST":
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return JsonResponse({"success": True, "message": "Informations utilisateur mises à jour."})
    else:
        form = UserEditForm(instance=user)

    return render(request, "rdv/profil/forms/edit_user_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def edit_patient_view(request):
    """Éditer les infos patient"""
    if not hasattr(request.user, "profil_patient"):
        return HttpResponseForbidden("Vous n'êtes pas un patient.")

    patient = request.user.profil_patient
    if request.method == "POST":
        form = PatientEditForm(request.POST, instance=patient)
        if form.is_valid():
            form.save()
            return JsonResponse({"success": True, "message": "Informations patient mises à jour."})
    else:
        form = PatientEditForm(instance=patient)

    return render(request, "rdv/profil/forms/edit_patient_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def edit_medecin_view(request):
    """Éditer les infos médecin"""
    if not hasattr(request.user, "profil_medecin"):
        return HttpResponseForbidden("Vous n'êtes pas un médecin.")

    medecin = request.user.profil_medecin
    if request.method == "POST":
        form = MedecinEditForm(request.POST, instance=medecin)
        if form.is_valid():
            form.save()
            return JsonResponse({"success": True, "message": "Informations médecin mises à jour."})
    else:
        form = MedecinEditForm(instance=medecin)

    return render(request, "rdv/profil/forms/edit_medecin_form.html", {"form": form})



@login_required
def edit_password(request):
    if request.method == "POST":
        form = CustomPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()  # 🔑 met à jour le mot de passe
            update_session_auth_hash(request, user)  # évite la déconnexion

            # AJAX → JSON
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": True})

            # fallback classique
            return redirect("users:profile")
        else:
            # si POST avec erreurs → AJAX renvoie fragment, sinon page complète
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return render(request, "rdv/profil/forms/edit_password.html", {"form": form})

    else:
        form = CustomPasswordChangeForm(user=request.user)

    # fallback page entière seulement
    return render(request, "rdv/profil/forms/edit_password.html", {"form": form})






@login_required(login_url='users:login')
@permission_required('users.can_view_all_users', raise_exception=True)
def liste_utilisateurs(request):
    # paramètres
    search_query = (request.GET.get('search') or '').strip()
    role_filter = (request.GET.get('role') or '').strip()
    active_param = (request.GET.get('active') or '').strip()

    # base queryset
    qs = Utilisateur.objects.all()

    # recherche
    if search_query:
        qs = qs.filter(
            Q(nom__icontains=search_query) |
            Q(prenom__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    # filtre role (attend la clé de rôle)
    if role_filter:
        qs = qs.filter(role=role_filter)

    # filtre actif : accepte plusieurs formats
    if active_param != '':
        ap = active_param.lower()
        if ap in ('1', 'true', 't', 'yes', 'y', 'actif', 'active'):
            qs = qs.filter(is_actif=True)
        elif ap in ('0', 'false', 'f', 'no', 'n', 'inactif', 'inactive'):
            qs = qs.filter(is_actif=False)
        # sinon : ignore (ne pas lever d'erreur)

    # tri & pagination
    qs = qs.order_by('-date_inscription')
    paginator = Paginator(qs, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'active_filter': active_param,
        'roles': Utilisateur.ROLE,  # utile pour rendre le select côté template
    }

    # si on demande *seulement* le tableau (via fetchTable AJAX)
    if request.GET.get('table-only') == '1':
        return render(request, 'rdv/admin/users/composants/users_table.html', context)

    # si requête AJAX (navigation fragment)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'rdv/admin/users/composants/users_content.html', context)

    # sinon page complète
    return render(request, 'rdv/admin/users/users.html', context)


# Liste des utilisateurs (admin uniquement)
@login_required(login_url='users:login')
@permission_required('users.can_view_all_users', raise_exception=True)
def liste_utilisateurs_ajax(request):
    # Query de base
    qs = Utilisateur.objects.all()
    
    # Infos actuelles
    current_count = qs.count()
    last_update = qs.aggregate(Max('updated_at'))['updated_at__max'] or timezone.now()

    last_version = request.GET.get('last_version')
    if last_version:
        try:
            iso, cnt = last_version.split('|', 1)
            client_dt = parse_datetime(iso)
            client_cnt = int(cnt)
        except Exception:
            client_dt = None
            client_cnt = None

        if client_dt is not None and client_cnt is not None:
            # Si rien n'a changé par rapport à la version client
            if client_dt >= last_update and client_cnt == current_count:
                return JsonResponse({'changed': False})

    # Sinon on renvoie les données (ou un résumé si tu préfères)
    users_data = [
        {
            'id': u.id,
            'nom': u.nom,
            'prenom': u.prenom,
            'email': u.email,
            'role': u.role,
            'is_actif': u.is_actif,
            'updated_at': (u.updated_at.isoformat() if getattr(u, 'updated_at', None) else None),
        }
        for u in qs.order_by('-updated_at')[:1000]  # limite raisonnable
    ]

    return JsonResponse({
        'changed': True,
        'last_version': f"{last_update.isoformat()}|{current_count}",
        'users': users_data,
    })



@login_required(login_url='users:login')
@permission_required('users.can_view_all_users', raise_exception=True)
def creer_utilisateur(request):
    form = UtilisateurCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status':'ok'})
        return redirect('users:list_users')
    # Sur GET ou erreurs, renvoie **seulement** le template du form
    template = 'rdv/admin/users/composants/user_form.html'
    return render(request, template, {'form': form})


@login_required(login_url='users:login')
@permission_required('users.can_view_all_users', raise_exception=True)
def modifier_utilisateur(request, user_id):
    """Modifier un utilisateur (admin uniquement)"""
    user = Utilisateur.objects.get(pk=user_id)
    if request.method == 'POST':
        form = UtilisateurUpdateForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return JsonResponse({"success": True, "message": "Informations utilisateur mises à jour."})
    else:
        form = UtilisateurUpdateForm(instance=user)
    
    return render(request, 'rdv/admin/users/composants/edit_user_form.html', {'form': form})



@login_required(login_url='users:login')
@permission_required('users.can_view_all_users', raise_exception=True)
def supprimer_utilisateur(request, user_id):
    user = Utilisateur.objects.get(pk=user_id)
    user.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status':'success'})
    return redirect('users:list_users')  # Redirige vers la liste des utilisateurs



