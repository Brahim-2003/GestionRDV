from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import transaction
from django.http import HttpResponseRedirect
from .models import Utilisateur
from .signals import RoleChangeBlocked
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin




class UtilisateurAdmin(BaseUserAdmin):
    """Administration personnalisée pour le modèle Utilisateur"""
    
    # Configuration de la liste
    list_display = ('email', 'nom', 'prenom', 'role', 'is_actif', 'is_staff', 'date_inscription')
    list_filter = ['role', 'is_actif', 'is_staff', 'date_inscription']
    search_fields = ['email', 'nom', 'prenom']
    ordering = ('-date_inscription',)
    
    # Configuration des fieldsets pour l'édition
    fieldsets = [
        (None, {'fields': ['email', 'password']}),
        ('Informations personnelles', {'fields': ['nom', 'prenom', 'telephone', 'date_naissance']}),
        ('Permissions', {'fields': ['role', 'is_actif', 'is_staff', 'is_superuser', 'groups', 'user_permissions']}),
        ('Dates importantes', {'fields': ['last_login', 'date_inscription']}),
    ]
    
    # Configuration des fieldsets pour la création
    add_fieldsets = (
        (None, {
            'classes': ['wide'],
            'fields': ['email', 'nom', 'prenom', 'telephone', 'role', 'password1', 'password2'],
        }),
    )
    
    readonly_fields = ('date_inscription', 'last_login')
    filter_horizontal = ('groups', 'user_permissions')

    def save_model(self, request, obj, form, change):
        """Convertit un changement de rôle bloqué par PROTECT (RoleChangeBlocked,
        levée par manage_profiles_on_role_change) en message d'erreur exploitable
        au lieu de laisser remonter une 500 brute — même comportement que
        users.views.edit_user. changeform_view englobe déjà tout l'appel dans
        transaction.atomic() : notre propre transaction.atomic() imbriquée crée
        un savepoint autour de super().save_model() (donc autour de l'UPDATE du
        rôle ET du signal qu'il déclenche) et l'annule proprement quand on capture
        l'exception à l'extérieur du bloc — sans laisser la transaction englobante
        dans un état cassé (TransactionManagementError sur les requêtes suivantes
        de _changeform_view, ex. save_related)."""
        try:
            with transaction.atomic():
                super().save_model(request, obj, form, change)
        except RoleChangeBlocked as exc:
            messages.error(request, str(exc))
            request._role_change_blocked = True

    def response_change(self, request, obj):
        if getattr(request, '_role_change_blocked', False):
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)

# Enregistrement du modèle avec la configuration personnalisée
admin.site.register(Utilisateur, UtilisateurAdmin)

# Configuration du site admin
admin.site.site_header = "Administration - Système RDV Médical"
admin.site.site_title = "Admin RDV Médical"
admin.site.index_title = "Panneau d'administration"

# Activer GroupAdmin pour voir toutes les permissions dans l'admin
admin.site.unregister(Group)
admin.site.register(Group, BaseGroupAdmin)
