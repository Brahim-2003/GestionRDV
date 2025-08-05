from multiprocessing import context
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required, permission_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Q, Max
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from .models import Utilisateur
from rdv.models import Patient, Medecin
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from rdv.views import dashboard_admin_view
from .forms import ConnexionForm, RegisterForm, UtilisateurCreationForm, UtilisateurUpdateForm

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
@login_required(login_url='users:login')
def profil_view(request, user_id):
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
    return render(request, 'rdv/admin/users/profil_user.html', context)



# Liste des utilisateurs (admin uniquement)
@login_required(login_url='users:login')
@permission_required('users.can_view_all_users', raise_exception=True)
def liste_utilisateurs(request):
    search_query = request.GET.get('search', '')
    role_filter  = request.GET.get('role', '')
    
    qs = Utilisateur.objects.all()
    
    if search_query:
        qs = qs.filter(
            Q(nom__icontains=search_query) |
            Q(prenom__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    if role_filter:
        qs = qs.filter(role=role_filter)
    
    qs = qs.order_by('-date_inscription')
    
    paginator  = Paginator(qs, 25)
    page_number = request.GET.get('page')
    page_obj    = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'roles': Utilisateur.ROLE,
    }
    # Déterminer quel template renvoyer

    # Si on demande *seulement* le tableau (via fetchTable)
    if request.GET.get('table-only') == '1':
        return render(request, 'rdv/admin/users/composants/users_table.html', context)
    # Si c'est une requête AJAX classique (navigation ou refresh de contenu)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'rdv/admin/users/composants/users_content.html', context)

    # Sinon → page complète (header + navbar + tout)
    return render(request, 'rdv/admin/users/users.html', context)



# Liste des utilisateurs (admin uniquement)
@login_required(login_url='users:login')
@permission_required('users.can_view_all_users', raise_exception=True)
def liste_utilisateurs_ajax(request):
    last_check = request.GET.get('last_version')
    qs = Utilisateur.objects.all()

    # Nombre d'utilisateurs et date max modif/créa
    current_count = qs.count()
    last_update = qs.aggregate(Max('updated_at'))['updated_at__max'] or now()

    # Si le client a une version, on compare
    if last_check:
        try:
            # last_version était encodé "iso|count"
            iso, cnt = last_check.split('|')
            dt = parse_datetime(iso)
            cnt = int(cnt)
        except Exception:
            dt = None
            cnt = None

        # Si ni date ni count n'ont changé → rien à renvoyer
        if dt and cnt is not None:
            if dt >= last_update and cnt == current_count:
                return JsonResponse({'changed': False})

    # Sinon on renvoie
    users_data = [
        {
            'id': u.id,
            'nom': u.nom,
            'prenom': u.prenom,
            'email': u.email,
            'role': u.role,
            'is_actif': u.is_actif,
        }
        for u in qs.order_by('-updated_at')
    ]

    return JsonResponse({
        'changed':     True,
        'last_version': f"{last_update.isoformat()}|{current_count}",
        'users':        users_data,
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
            user = form.save()
            return redirect('users:list_users')  # Redirige vers la liste des utilisateurs
    else:
        form = UtilisateurUpdateForm(instance=user)
    
    return render(request, 'rdv/admin/users/modifier.html', {'form': form})


@login_required(login_url='users:login')
@permission_required('users.can_view_all_users', raise_exception=True)
def supprimer_utilisateur(request, user_id):
    user = Utilisateur.objects.get(pk=user_id)
    user.delete()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status':'success'})
    return redirect('users:list_users')  # Redirige vers la liste des utilisateurs



