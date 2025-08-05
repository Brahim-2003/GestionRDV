
# rdv/admin.py
from django.contrib import admin
from .models import Patient, Medecin, RendezVous, Disponibilite, Notification, MessageBot

@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('numero_patient', 'user', 'date_naissance')
    search_fields = ['numero_patient', 'utilisateur__nom', 'utilisateur__prenom', 'utilisateur__email']
    list_filter = ['date_naissance',]
    readonly_fields = ('numero_patient',)
    
    fieldsets = (
        ('Informations générales', {
            'fields': ['user', 'numero_patient', 'date_naissance', 'adresse']
            }),
    )

@admin.register(Medecin)
class MedecinAdmin(admin.ModelAdmin):
    list_display = ('user', 'numero_order', 'specialite', 'cabinet')
    search_fields = ['numero_order', 'user__nom', 'user__prenom', 'cabinet']
    list_filter = ['specialite']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ['user', 'numero_order', 'specialite']
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
    list_display = ('medecin', 'jour', 'heure_debut', 'heure_fin')
    search_fields = ['medecin__utilisateur__nom', 'jour']
    list_filter = ['jour', 'heure_debut']


    fieldsets = (
        ('Disponibilité', {
            'fields' : ['medecin', 'jour']
        }),
        ('Horaires', {
            'fields': ['heure_debut', 'heure_fin']
        }),
    )

@admin.register(RendezVous)
class RendezVousAdmin(admin.ModelAdmin):
    list_display = ('patient', 'medecin', 'date_heure_rdv', 'duree_minutes', 'statut', 'motif', 'date_creation')
    search_fields = ['patient__utilisateur__nom', 'medecin__utilisateur__nom', 'motif']
    list_filter = ['statut', 'date_heure_rdv', 'medecin__specialite']
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
    list_display = ('user', 'message', 'type', 'date_envoi')
    search_fields = ['user__nom', 'user__prenom', 'message']
    list_filter = ['date_envoi']
    
    fieldsets = (
        ('Message', {
            'fields': ['user', 'message']
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
