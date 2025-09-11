
# rdv/admin.py
from django.contrib import admin
from .models import Patient, Medecin, RendezVous, Disponibilite, Notification, MessageBot, RdvHistory

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('numero_patient', 'user', 'date_naissance', 'adresse', 'sexe', 'tel')
    search_fields = ['numero_patient', 'user__nom', 'user__prenom', 'user__email']
    list_filter = ['sexe','user__date_inscription']
    readonly_fields = ('numero_patient',)
    
    fieldsets = (
        ('Informations générales', {
            'fields': ['user', 'numero_patient', 'date_naissance', 'adresse', 'sexe', 'tel']
            }),
    )

@admin.register(Medecin)
class MedecinAdmin(admin.ModelAdmin):
    list_display = ('numero_order', 'user', 'specialite', 'cabinet', 'tel')
    search_fields = ['numero_order', 'user__nom', 'user__prenom', 'cabinet']
    list_filter = ['sexe', 'specialite', 'user__date_inscription']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ['user', 'numero_order', 'sexe', 'specialite', 'tel']
            }),
        ('Cabinet', {
            'fields': ['cabinet', 'adresse_cabinet']
        }),
        ('Qualifications', {
            'fields': ['diplomes']
        }),
    )

@admin.register(Disponibilite)
class DisponibiliteAdmin(admin.ModelAdmin):
    list_display = ('medecin', 'jour', 'date_specific', 'heure_debut', 'heure_fin', 'is_active')
    search_fields = ['medecin__utilisateur__nom', 'medecin__utilisateur__prenom', 'jour']
    list_filter = ['jour', 'date_specific', 'is_active', 'created_at']


    fieldsets = (
        ('Disponibilité', {
            'fields' : ['medecin', 'jour', 'date_specific'] 
        }),
        ('Horaires', {
            'fields': ['heure_debut', 'heure_fin']
        }),
        ('Statut', {
            'fields': ['is_active']
        }),
    )

@admin.register(RendezVous)
class RendezVousAdmin(admin.ModelAdmin):
    list_display = ('patient', 'medecin', 'date_heure_rdv', 'duree_minutes', 'statut', 'motif', 'date_creation')
    search_fields = ['patient__utilisateur__nom', 'patient__utilisateur__prenom', 'medecin__utilisateur__nom', 'medecin__utilisateur__prenom', 'motif']
    list_filter = ['statut', 'date_creation']
    date_hierarchy = 'date_heure_rdv'
    
    fieldsets = (
        ('Rendez-vous', {
            'fields': ['patient', 'medecin', 'date_heure_rdv', 'duree_minutes']
        }),
        ('Détails', {
            'fields': ['motif', 'statut', 'date_creation']
        }),
    )
    
    readonly_fields = ('date_creation', 'date_modification')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'type', 'category', 'is_read', 'date_envoi')
    search_fields = ['user__nom', 'user__prenom']
    list_filter = ['date_envoi', 'type', 'is_read']

    readonly_fields = ("date_envoi",)
    
    fieldsets = (
        ('Message', {
            'fields': ['user', 'message']
        }),

        ('Détails', {
            'fields': ['type', 'category', 'is_read']
        }),

        ('Horaires', {
            'fields': ['date_envoi']
        }),
    )


@admin.register(MessageBot)
class MessageBotAdmin(admin.ModelAdmin):
    list_display = ('user', 'contenu', 'intention', 'reponse', 'date_echange')
    search_fields = ['user__nom', 'user__prenom', 'contenu', 'intention']
    list_filter = ['date_echange']
    fieldsets = (
        ('Conversation', {
            'fields': ['user', 'contenu', 'intention', 'reponse']
        }),
    )

@admin.register(RdvHistory)
class RdvHistoryAdmin(admin.ModelAdmin):
    list_display = ('rdv', 'action', 'performed_by', 'timestamp')
    list_filter = ('action', 'performed_by')
    search_fields = ('rdv__id', 'performed_by__email', 'description', 'old_value', 'new_value')
    readonly_fields = ('rdv', 'action', 'performed_by', 'timestamp', 'old_value', 'new_value', 'description', 'extra')
