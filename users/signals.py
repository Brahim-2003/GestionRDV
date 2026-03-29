from asyncio.log import logger
from django.conf import settings
from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.apps import apps
from django.utils.translation import gettext_lazy
import uuid
from django.db import transaction

from rdv.models import Patient, Medecin
from users.models import Utilisateur
from users.tasks import notify_admins_on_user_create


def generate_unique_numero_patient():
    """Génère un numéro unique pour un patient."""
    while True:
        numero = f'PAT{uuid.uuid4().hex[:8].upper()}'
        if not Patient.objects.filter(numero_patient=numero).exists():
            return numero



@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def manage_profiles_on_role_change(sender, instance, created, **kwargs):
    role = getattr(instance, 'role', None)

    if role == 'patient':
        Patient.objects.get_or_create(
            user=instance,
            defaults={
                'date_naissance': instance.date_naissance,
                'tel': instance.telephone,
                'numero_patient': generate_unique_numero_patient()
            }
        )
        Medecin.objects.filter(user=instance).delete()

    elif role == 'medecin':
        Medecin.objects.get_or_create(
            user=instance,
            defaults={
                'date_naissance': instance.date_naissance,
                'tel': instance.telephone,
                'specialite': 'generaliste'
            }
        )
        Patient.objects.filter(user=instance).delete()

    else:
        Patient.objects.filter(user=instance).delete()
        Medecin.objects.filter(user=instance).delete()

    # Attribution du groupe
    instance.groups.clear()
    role_group = {
        'patient': 'Patients',
        'medecin': 'Médecins',
        'admin': 'Administrateurs'
    }.get(role)

    if role_group:
        group, _ = Group.objects.get_or_create(name=role_group)
        instance.groups.add(group)

    if created and instance.role == 'patient':
        try:
            transaction.on_commit(
            lambda: notify_admins_on_user_create.delay(instance.id)
            )
        except Exception as exc:
            # ne pas laisser une erreur de broker casser la requête utilisateur
            logger.exception("Impossible de planifier notify_admins_on_user_create: %s", exc)

        
@receiver(post_migrate)
def create_default_groups_and_permissions(sender, **kwargs):
    """
    Crée les groupes et permissions UNE SEULE FOIS,
    après que TOUTES les migrations soient terminées.
    """

    # 🔒 Ne s'exécute qu'une seule fois (app users uniquement)
    if sender.label != "users":
        return

    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType
    from django.apps import apps

    # Création des groupes
    patients_group, _ = Group.objects.get_or_create(name='Patients')
    medecins_group, _ = Group.objects.get_or_create(name='Médecins')
    admins_group, _   = Group.objects.get_or_create(name='Administrateurs')

    # Helper sécurisé (évite les warnings)
    def get_perm(app_label, model_name, action):
        try:
            model = apps.get_model(app_label, model_name)
            ct = ContentType.objects.get_for_model(model)
            return Permission.objects.get(
                codename=f"{action}_{model_name.lower()}",
                content_type=ct
            )
        except Permission.DoesNotExist:
            return None

    # Permissions standards
    permissions_map = [
        # (app, model, action, groupes)
        ('rdv', 'RendezVous', 'add',   [patients_group, medecins_group]),
        ('rdv', 'RendezVous', 'change',[patients_group, medecins_group]),
        ('rdv', 'RendezVous', 'view',  [patients_group, medecins_group]),

        ('rdv', 'Patient', 'add',   [admins_group, medecins_group]),
        ('rdv', 'Patient', 'change',[admins_group, medecins_group]),
        ('rdv', 'Patient', 'view',  [admins_group, medecins_group]),

        ('rdv', 'Medecin', 'add',   [admins_group]),
        ('rdv', 'Medecin', 'change',[admins_group]),
        ('rdv', 'Medecin', 'view',  [admins_group]),

        ('users', 'Utilisateur', 'add',    [admins_group]),
        ('users', 'Utilisateur', 'change', [admins_group]),
        ('users', 'Utilisateur', 'delete', [admins_group]),
        ('users', 'Utilisateur', 'view',   [admins_group, patients_group, medecins_group]),
    ]

    for app_label, model, action, groups in permissions_map:
        perm = get_perm(app_label, model, action)
        if perm:
            for group in groups:
                group.permissions.add(perm)

    # 🔹 Permissions personnalisées
    utilisateur_model = apps.get_model('users', 'Utilisateur')
    ct_users = ContentType.objects.get_for_model(utilisateur_model)

    custom_permissions = {
        'can_manage_appointments': "Peut gérer les rendez-vous",
        'can_view_all_users': "Peut voir tous les utilisateurs",
        'can_manage_patients': "Peut gérer les patients",
        'can_manage_medecins': "Peut gérer les médecins",
        'can_view_statistics': "Peut consulter les statistiques",
        'can_export_data': "Peut exporter les données",
    }

    created_perms = {}
    for codename, name in custom_permissions.items():
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            content_type=ct_users,
            defaults={'name': name}
        )
        created_perms[codename] = perm

    # Attribution propre (sans erreurs)
    patients_group.permissions.add(
        get_perm('users', 'Utilisateur', 'view')
    )

    medecins_group.permissions.add(
        get_perm('users', 'Utilisateur', 'view'),
        created_perms['can_manage_appointments']
    )

    admins_group.permissions.add(
        get_perm('users', 'Utilisateur', 'add'),
        get_perm('users', 'Utilisateur', 'change'),
        get_perm('users', 'Utilisateur', 'delete'),
        get_perm('users', 'Utilisateur', 'view'),
        *created_perms.values()
    )