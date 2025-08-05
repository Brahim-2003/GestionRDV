from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group, Permission
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.models import ContentType
import re

# Create your models here.

class UtilisateurManager(BaseUserManager):

    # Manager personnalisé pour le modèle Utilisateur
    def create_user(self, email, nom, prenom, mot_de_passe=None, **extra_fields):

        # Crée et sauvegarde un utilisateur avec l'email, nom et prénom donnés
        if not email:
            raise ValueError("L'email est obligatoire")
        
        if not nom:
            raise ValueError("Le nom est obligatoire")
        
        if not prenom:
            raise ValueError("Le prénom est obligatoire")
        
        email = self.normalize_email(email)
        user = self.model(email=email, nom=nom, prenom=prenom, **extra_fields)
        user.set_password(mot_de_passe)
        user.save(using=self._db)

        # Assigner automatiquement les permissions selon le rôle
        self._assign_role_permissions(user)

        return user

    def create_superuser(self, email, nom, prenom, mot_de_passe=None, **extra_fields):

        # Crée et sauvegarde un superutilisateur
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_actif', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Le superutilisateur doit avoir is_staff=True !")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Le superutilisateur doit avoir is_superuser=True !")
        
        return self.create_user(email, nom, prenom, mot_de_passe, **extra_fields)

    # Fonction qui assigne automatiquement les permissions selon le rôle
    def _assign_role_permissions(self, user):

        # Supprimer l'utilisateur de tous les groupes existants
        user.groups.clear()
        
        role_group = {
            'patient': 'Patients',
            'medecin': 'Médecins',
            'admin': 'Administrateurs'
        }.get(user.role)
        if role_group:
            group, _ = Group.objects.get_or_create(name=role_group)
            user.groups.add(group)





class Utilisateur(AbstractBaseUser, PermissionsMixin):
    ROLE = [
        ('patient', 'Patient'),
        ('medecin', 'Médecin'),
        ('admin', 'Administrateur')
    ]
    username = None
    email = models.EmailField(unique=True, verbose_name="Email")
    nom = models.CharField(max_length=53, verbose_name="Nom")
    prenom = models.CharField(max_length=53, verbose_name="Prénom")
    telephone = models.CharField(max_length=20, verbose_name="Téléphone")
    role = models.CharField(max_length=20, choices=ROLE, default='patient', verbose_name="Rôle")
    date_inscription = models.DateTimeField(auto_now_add=True, verbose_name="Date d'inscription")

    is_actif = models.BooleanField(default=True, verbose_name="Actif")
    is_staff = models.BooleanField(default=False, verbose_name="Staff")

    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date de mise à jour")

    objects = UtilisateurManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nom', 'prenom']

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

            # Permissions personnalisées
        permissions = [
            ("can_view_all_users", "Peut voir tous les utilisateurs"),
            ("can_manage_patients", "Peut gérer les patients"),
            ("can_manage_medecins", "Peut gérer les médecins"),
            ("can_view_statistics", "Peut voir les statistiques"),
            ("can_export_data", "Peut exporter les données"),
            ("can_manage_appointments", "Peut gérer les rendez-vous"),
        ]


    def __str__(self):
        return f"{self.nom} {self.prenom}"

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.role})"
    
    def nom_complet(self):
        return f"{self.nom} {self.prenom}"
    
    # Vérifie si l'utilisateur a un rôle spécifique
    def has_role(self, role):
        return self.role == role
    
    # Attribue le role patient
    def is_patient(self):
        return self.role == 'patient'
    
    # Attribue le role médecin
    def is_medecin(self):
        return self.role == 'medecin'
    
    # Attribue le role administrateur
    def is_admin_role(self):
        return self.role == 'admin'
    
    
    def save(self, *args, **kwargs):

        # Définir is_staff et is_active selon le rôle
        if self.role == 'admin':
            self.is_staff = True
        elif self.role in ['medecin', 'patient']:
            self.is_staff = False
        
        super().save(*args, **kwargs)

        
    def clean(self):
        super().clean()
        if self.telephone and not re.match(r'^\+?[0-9\s\-\(\)]+$', self.telephone):
            raise ValidationError({'telephone':'Format de téléphone  invalide !'})
        
    





