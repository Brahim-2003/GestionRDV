from django.conf import settings
from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.apps import apps
from django.utils.translation import gettext_lazy
import uuid

from rdv.models import Patient, Medecin
from users.models import Utilisateur


def generate_unique_numero_patient():
    """Génère un numéro unique pour un patient."""
    while True:
        numero = f'PAT{uuid.uuid4().hex[:8].upper()}'
        if not Patient.objects.filter(numero_patient=numero).exists():
            return numero


def generate_unique_numero_medecin():
    """Génère un numéro unique pour un médecin."""
    while True:
        numero = f'MED{uuid.uuid4().hex[:8].upper()}'
        if not Medecin.objects.filter(numero_order=numero).exists():
            return numero


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def manage_profiles_on_role_change(sender, instance, **kwargs):
    """
    À chaque sauvegarde de User, crée ou supprime les profils Patient/Médecin
    en fonction de instance.role.
    """
    role = getattr(instance, 'role', None)

    if role == 'patient':
        # Crée un profil Patient si absent
        Patient.objects.get_or_create(
            user=instance,
            defaults={'numero_patient': generate_unique_numero_patient()}
        )
        # Supprime tout profil Médecin
        Medecin.objects.filter(user=instance).delete()

    elif role == 'medecin':
        # Crée un profil Médecin si absent
        Medecin.objects.get_or_create(
            user=instance,
            defaults={
                'numero_order': generate_unique_numero_medecin(),
                'specialite': 'generaliste'
            }
        )
        # Supprime tout profil Patient
        Patient.objects.filter(user=instance).delete()

    else:
        # Pour les autres rôles, on nettoie les deux profils
        Patient.objects.filter(user=instance).delete()
        Medecin.objects.filter(user=instance).delete()


@receiver(post_migrate)
def create_default_groups_and_permissions(sender, **kwargs):
    """
    Crée les groupes et permissions par défaut après migrations.
    """
    # Création des groupes
    patients_group, _ = Group.objects.get_or_create(name='Patients')
    medecins_group, _ = Group.objects.get_or_create(name='Médecins')
    admins_group, _   = Group.objects.get_or_create(name='Administrateurs')

    # Définition des permissions par modèle
    models_permissions = {
        'rdv.RendezVous': ['add', 'change', 'delete', 'view'],
        'rdv.Patient':   ['add', 'change', 'view'],
        'rdv.Medecin':   ['add', 'change', 'view'],
        'users.Utilisateur': ['add', 'change', 'delete', 'view'],
    }

    for model_path, actions in models_permissions.items():
        app_label, model_name = model_path.split('.')
        Model = apps.get_model(app_label, model_name)
        content_type = ContentType.objects.get_for_model(Model)

        for action in actions:
            codename = f"{action}_{model_name.lower()}"
            try:
                perm = Permission.objects.get(codename=codename, content_type=content_type)
                if model_name == 'RendezVous' and action in ['add', 'change', 'view']:
                    medecins_group.permissions.add(perm)
                    patients_group.permissions.add(perm)
                elif model_name == 'Patient' and action in ['add', 'change', 'view']:
                    admins_group.permissions.add(perm)
                    medecins_group.permissions.add(perm)
                elif model_name == 'Medecin' and action in ['add', 'change', 'view']:
                    admins_group.permissions.add(perm)
                elif model_name == 'Utilisateur':
                    if action == 'view':
                        patients_group.permissions.add(perm)
                        medecins_group.permissions.add(perm)
                    admins_group.permissions.add(perm)
            except Permission.DoesNotExist:
                print(f"[WARNING] Permission '{codename}' non trouvée pour {model_name}")

    # Permissions personnalisées
    custom_permissions = {
        'can_manage_appointments': gettext_lazy('Peut gérer les rendez-vous'),
        'can_view_all_users':      gettext_lazy('Peut voir tous les utilisateurs'),
        'can_manage_patients':     gettext_lazy('Peut gérer les patients'),
        'can_manage_medecins':     gettext_lazy('Peut gérer les médecins'),
        'can_view_statistics':     gettext_lazy('Peut consulter les statistiques'),
        'can_export_data':         gettext_lazy('Peut exporter les données'),
    }
    utilisateur_model = apps.get_model('users', 'Utilisateur')
    ct_users = ContentType.objects.get_for_model(utilisateur_model)

    for codename, name in custom_permissions.items():
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            content_type=ct_users,
            defaults={'name': name}
        )

    # Affectation aux groupes
    def assign(group, codenames):
        for cd in codenames:
            try:
                p = Permission.objects.get(codename=cd, content_type=ct_users)
                group.permissions.add(p)
            except Permission.DoesNotExist:
                print(f"[WARNING] Custom perm '{cd}' not found")

    assign(patients_group, ['view_utilisateur'])
    assign(medecins_group,  ['view_utilisateur', 'can_manage_appointments'])
    assign(admins_group,    [
        'add_utilisateur','change_utilisateur','delete_utilisateur','view_utilisateur',
        'can_view_all_users','can_manage_patients','can_manage_medecins',
        'can_view_statistics','can_export_data','can_manage_appointments'
    ])
