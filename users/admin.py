from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Utilisateur
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
        ('Informations personnelles', {'fields': ['nom', 'prenom', 'telephone']}),
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

# Enregistrement du modèle avec la configuration personnalisée
admin.site.register(Utilisateur, UtilisateurAdmin)

# Configuration du site admin
admin.site.site_header = "Administration - Système RDV Médical"
admin.site.site_title = "Admin RDV Médical"
admin.site.index_title = "Panneau d'administration"

# Activer GroupAdmin pour voir toutes les permissions dans l'admin
admin.site.unregister(Group)
admin.site.register(Group, BaseGroupAdmin)
