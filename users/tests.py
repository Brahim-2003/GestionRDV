# users/tests.py
import os
from unittest import mock
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model, authenticate
from django.core.management import call_command
from django.utils import timezone
from datetime import date, timedelta
from rdv.models import Patient, Medecin, RendezVous, RdvHistory

Utilisateur = get_user_model()


class UtilisateurModelTest(TestCase):
    """Tests du modèle Utilisateur"""
    
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'nom': 'Dupont',
            'prenom': 'Jean',
            'date_naissance': date(1990, 1, 15),
            'telephone': '+33612345678',
            'mot_de_passe': 'TestPass123!'
        }
    
    def test_create_user(self):
        """Création d'un utilisateur standard"""
        user = Utilisateur.objects.create_user(**self.user_data)
        
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.nom, 'Dupont')
        self.assertEqual(user.prenom, 'Jean')
        self.assertEqual(user.role, 'patient')  # Rôle par défaut
        self.assertTrue(user.is_actif)
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password('TestPass123!'))
    
    def test_create_superuser(self):
        """Création d'un superutilisateur"""
        admin = Utilisateur.objects.create_superuser(
            email='admin@example.com',
            nom='Admin',
            prenom='Super',
            date_naissance=date(1985, 5, 20),
            mot_de_passe='AdminPass123!'
        )
        
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, 'admin')
        self.assertTrue(admin.is_actif)
    
    def test_email_required(self):
        """Email obligatoire"""
        with self.assertRaises(ValueError):
            Utilisateur.objects.create_user(
                email='',
                nom='Test',
                prenom='User',
                date_naissance=date(1990, 1, 1)
            )
    
    def test_email_unique(self):
        """Unicité de l'email"""
        Utilisateur.objects.create_user(**self.user_data)
        
        with self.assertRaises(Exception):  # IntegrityError
            Utilisateur.objects.create_user(**self.user_data)
    
    def test_nom_complet(self):
        """Méthode nom_complet()"""
        user = Utilisateur.objects.create_user(**self.user_data)
        self.assertEqual(user.nom_complet(), 'Jean Dupont')
    
    def test_has_role(self):
        """Méthode has_role()"""
        user = Utilisateur.objects.create_user(**self.user_data)
        
        self.assertTrue(user.has_role('patient'))
        self.assertFalse(user.has_role('medecin'))
        self.assertFalse(user.has_role('admin'))
    
    def test_is_patient(self):
        """Méthode is_patient()"""
        user = Utilisateur.objects.create_user(**self.user_data)
        self.assertTrue(user.is_patient())
    
    def test_is_medecin(self):
        """Méthode is_medecin()"""
        user = Utilisateur.objects.create_user(
            **{**self.user_data, 'email': 'medecin@test.com'}
        )
        user.role = 'medecin'
        user.save()
        
        self.assertTrue(user.is_medecin())
        self.assertFalse(user.is_patient())
    
    def test_is_admin_role(self):
        """Méthode is_admin_role()"""
        admin = Utilisateur.objects.create_superuser(
            email='admin@test.com',
            nom='Admin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            mot_de_passe='admin123'
        )
        
        self.assertTrue(admin.is_admin_role())


class CreateSuperuserManagementCommandTest(TestCase):
    """Régression : la commande standard `createsuperuser` de Django passe toujours
    le mot de passe sous la clé `password`, jamais `mot_de_passe`. Un test qui appelle
    le manager directement avec `mot_de_passe=` ne peut pas détecter ce bug puisqu'il
    contourne exactement le chemin défectueux : il faut passer par la vraie commande."""

    def test_createsuperuser_command_produces_usable_login(self):
        env = {
            'DJANGO_SUPERUSER_EMAIL': 'cli-admin@test.com',
            'DJANGO_SUPERUSER_PASSWORD': 'CliAdminPass123!',
            'DJANGO_SUPERUSER_NOM': 'Admin',
            'DJANGO_SUPERUSER_PRENOM': 'CLI',
            'DJANGO_SUPERUSER_DATE_NAISSANCE': '1990-01-01',
        }
        with mock.patch.dict(os.environ, env):
            call_command('createsuperuser', interactive=False)

        admin = Utilisateur.objects.get(email='cli-admin@test.com')
        self.assertTrue(admin.has_usable_password())
        self.assertIsNotNone(
            authenticate(username='cli-admin@test.com', password='CliAdminPass123!')
        )


class SoftDeleteUtilisateurTest(TestCase):
    """Soft-delete (conformité dossier médical) : un compte supprimé ne
    doit plus jamais être trouvable/connectable, mais ses RDV et son
    historique doivent rester intacts et consultables par un admin via
    Utilisateur.all_objects — aucun CASCADE ne doit se déclencher."""

    def setUp(self):
        self.patient_user = Utilisateur.objects.create_user(
            email='soft_delete_patient@test.com',
            nom='Patient', prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='SoftPass123!',
        )
        self.medecin_user = Utilisateur.objects.create_user(
            email='soft_delete_medecin@test.com',
            nom='Medecin', prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='test123',
        )
        self.rdv = RendezVous.objects.create(
            patient=self.patient_user.profil_patient,
            medecin=self.medecin_user.profil_medecin,
            date_heure_rdv=timezone.now() + timedelta(days=3),
            statut='programme',
            motif='Test',
        )
        self.history = RdvHistory.objects.create(
            rdv=self.rdv,
            action='create',
            performed_by=self.patient_user,
            description='Rendez-vous créé',
        )

    def test_soft_deleted_user_cannot_login(self):
        self.patient_user.soft_delete()

        response = self.client.post(reverse('users:login'), {
            'email': 'soft_delete_patient@test.com',
            'password': 'SoftPass123!',
        })

        self.assertEqual(response.status_code, 200)  # formulaire réaffiché, pas de redirection
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_soft_deleted_user_excluded_from_default_manager(self):
        user_id = self.patient_user.pk
        self.patient_user.soft_delete()

        self.assertFalse(Utilisateur.objects.filter(pk=user_id).exists())
        with self.assertRaises(Utilisateur.DoesNotExist):
            Utilisateur.objects.get(pk=user_id)

        # Toujours accessible via le manager non filtré (usage admin).
        deleted = Utilisateur.all_objects.get(pk=user_id)
        self.assertIsNotNone(deleted.deleted_at)

    def test_soft_deleted_user_excluded_from_admin_user_list(self):
        admin = Utilisateur.objects.create_superuser(
            email='soft_delete_admin@test.com',
            nom='Admin', prenom='Test',
            date_naissance=date(1970, 1, 1),
            mot_de_passe='admin123',
        )
        self.patient_user.soft_delete()

        client = Client()
        client.force_login(admin)
        response = client.get(reverse('users:list_users'))

        self.assertEqual(response.status_code, 200)
        emails = [u.email for u in response.context['page_obj'].object_list]
        self.assertNotIn('soft_delete_patient@test.com', emails)

    def test_rdv_history_survives_soft_delete_and_stays_consultable(self):
        history_id = self.history.pk
        rdv_id = self.rdv.pk
        user_id = self.patient_user.pk

        self.patient_user.soft_delete()

        # Rien n'a été détruit en cascade.
        self.assertTrue(RendezVous.objects.filter(pk=rdv_id).exists())
        self.assertTrue(RdvHistory.objects.filter(pk=history_id).exists())

        # Consultable pour un admin, à partir du compte supprimé lui-même.
        deleted_user = Utilisateur.all_objects.get(pk=user_id)
        history_qs = RdvHistory.objects.filter(rdv__patient__user=deleted_user)
        self.assertEqual(history_qs.count(), 1)
        self.assertEqual(history_qs.first().description, 'Rendez-vous créé')


class SignalProfileCreationTest(TestCase):
    """Tests des signaux de création de profils"""
    
    def test_patient_profile_created_on_user_creation(self):
        """Signal crée automatiquement le profil Patient"""
        user = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1992, 3, 10),
            role='patient',
            mot_de_passe='test123'
        )
        
        self.assertTrue(hasattr(user, 'profil_patient'))
        self.assertIsNotNone(user.profil_patient)
        self.assertIsNotNone(user.profil_patient.numero_patient)
        self.assertTrue(user.profil_patient.numero_patient.startswith('PAT'))
    
    def test_medecin_profile_created_on_role_change(self):
        """Signal crée le profil Medecin lors du changement de rôle"""
        user = Utilisateur.objects.create_user(
            email='user@test.com',
            nom='User',
            prenom='Test',
            date_naissance=date(1985, 6, 15),
            role='patient',
            mot_de_passe='test123'
        )
        
        # Changement de rôle
        user.role = 'medecin'
        user.save()
        
        # Vérifie que le profil médecin est créé et patient supprimé
        self.assertTrue(hasattr(user, 'profil_medecin'))
        self.assertFalse(Patient.objects.filter(user=user).exists())
        self.assertTrue(Medecin.objects.filter(user=user).exists())
    
    def test_admin_has_no_profile(self):
        """Admin n'a ni profil patient ni médecin"""
        admin = Utilisateur.objects.create_superuser(
            email='admin@test.com',
            nom='Admin',
            prenom='Super',
            date_naissance=date(1980, 1, 1),
            mot_de_passe='admin123'
        )
        
        self.assertFalse(Patient.objects.filter(user=admin).exists())
        self.assertFalse(Medecin.objects.filter(user=admin).exists())


class RoleChangeProtectionTest(TestCase):
    """PROTECT en filet de sécurité : changer le rôle d'un patient/médecin
    qui a des rendez-vous ne doit jamais réussir à moitié. transaction.atomic
    (dans manage_profiles_on_role_change ET dans la vue d'édition) garantit
    que ni le rôle sur Utilisateur, ni son profil, ne changent si le retrait
    de l'ancien profil est bloqué par PROTECT."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            email='role_admin@test.com',
            nom='Admin', prenom='Test',
            date_naissance=date(1980, 1, 1),
            mot_de_passe='admin123',
        )
        self.patient_user = Utilisateur.objects.create_user(
            email='role_patient@test.com',
            nom='Patient', prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='test123',
        )
        self.medecin_user = Utilisateur.objects.create_user(
            email='role_medecin@test.com',
            nom='Medecin', prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='test123',
        )
        RendezVous.objects.create(
            patient=self.patient_user.profil_patient,
            medecin=self.medecin_user.profil_medecin,
            date_heure_rdv=timezone.now() + timedelta(days=3),
            statut='programme',
            motif='Test',
        )

    def test_role_change_blocked_when_old_profile_has_rdv(self):
        client = Client()
        client.force_login(self.admin)

        response = client.post(
            reverse('users:edit_user_admin', kwargs={'user_id': self.patient_user.id}),
            data={
                'nom': 'Patient',
                'prenom': 'Test',
                'email': 'role_patient@test.com',
                'telephone': '+23500000000',
                'role': 'medecin',
                'is_actif': 'on',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)

        # Le rôle n'a pas changé : la transaction a bien tout annulé.
        self.patient_user.refresh_from_db()
        self.assertEqual(self.patient_user.role, 'patient')

        # Le profil Patient existe toujours intact, aucun profil Medecin créé.
        self.assertTrue(Patient.objects.filter(user=self.patient_user).exists())
        self.assertFalse(Medecin.objects.filter(user=self.patient_user).exists())

        # Un message d'erreur clair est retourné.
        messages_list = [str(m) for m in response.context['messages']]
        self.assertIn(
            "Ce patient a des rendez-vous existants et ne peut pas devenir "
            "médecin sans traitement séparé de son historique.",
            messages_list,
        )


class NativeAdminRoleChangeProtectionTest(TestCase):
    """La changeform admin Django native (/admin/users/utilisateur/<id>/change/,
    pas le panneau admin de l'app) englobe déjà son POST dans transaction.atomic
    (ModelAdmin.changeform_view) : ce filet suffit à garantir qu'aucun état
    partiel n'est possible. Mais rien n'y rattrapait RoleChangeBlocked, qui
    remontait donc en 500 brute. UtilisateurAdmin.save_model/response_change
    la convertit maintenant en message clair + réaffichage du formulaire,
    comme users.views.edit_user."""

    def setUp(self):
        self.admin = Utilisateur.objects.create_superuser(
            email='native_admin@test.com',
            nom='Admin', prenom='Test',
            date_naissance=date(1980, 1, 1),
            mot_de_passe='admin123',
        )
        self.patient_user = Utilisateur.objects.create_user(
            email='native_patient@test.com',
            nom='Patient', prenom='Test',
            date_naissance=date(1990, 1, 1),
            telephone='+235111',
            role='patient',
            mot_de_passe='test123',
        )
        self.medecin_user = Utilisateur.objects.create_user(
            email='native_medecin@test.com',
            nom='Medecin', prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='test123',
        )
        RendezVous.objects.create(
            patient=self.patient_user.profil_patient,
            medecin=self.medecin_user.profil_medecin,
            date_heure_rdv=timezone.now() + timedelta(days=3),
            statut='programme',
            motif='Test',
        )

    def test_native_admin_role_change_blocked_shows_clear_message(self):
        client = Client()
        client.force_login(self.admin)
        url = reverse('admin:users_utilisateur_change', args=[self.patient_user.pk])
        data = {
            'email': 'native_patient@test.com',
            'nom': 'Patient', 'prenom': 'Test',
            'telephone': '+235111',
            'date_naissance': '1990-01-01',
            'role': 'medecin',
            'is_actif': 'on',
            'groups': [],
            'user_permissions': [],
            '_continue': 'Save and continue editing',
        }

        # Pas d'exception non gérée : la requête aboutit normalement (pas de 500).
        response = client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Un message d'erreur clair est affiché.
        messages_list = [str(m) for m in response.context['messages']]
        self.assertIn(
            "Ce patient a des rendez-vous existants et ne peut pas devenir "
            "médecin sans traitement séparé de son historique.",
            messages_list,
        )

        # Le formulaire est réaffiché avec les données du patient bloqué.
        self.assertContains(response, 'native_patient@test.com')
        self.assertEqual(response.context['adminform'].form.initial['role'], 'patient')

        # Aucun état partiel : ni le rôle, ni le profil n'ont changé.
        self.patient_user.refresh_from_db()
        self.assertEqual(self.patient_user.role, 'patient')
        self.assertTrue(Patient.objects.filter(user=self.patient_user).exists())
        self.assertFalse(Medecin.objects.filter(user=self.patient_user).exists())


class AuthenticationViewsTest(TestCase):
    """Tests des vues d'authentification"""
    
    def setUp(self):
        self.client = Client()
        self.user = Utilisateur.objects.create_user(
            email='test@example.com',
            nom='Test',
            prenom='User',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='testpass123'
        )
    
    def test_login_view_get(self):
        """Affichage du formulaire de connexion"""
        response = self.client.get(reverse('users:login'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')
        self.assertContains(response, 'email')
    
    def test_login_success(self):
        """Connexion réussie"""
        response = self.client.post(reverse('users:login'), {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        
        # Vérifie la redirection
        self.assertEqual(response.status_code, 302)
        
        # Vérifie que l'utilisateur est connecté
        self.assertTrue(self.client.session.get('_auth_user_id'))
    
    def test_login_failure_wrong_password(self):
        """Connexion échouée - mauvais mot de passe"""
        response = self.client.post(reverse('users:login'), {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email ou mot de passe incorrect')
    
    def test_login_failure_inactive_user(self):
        """Connexion échouée - compte désactivé"""
        self.user.is_actif = False
        self.user.save()
        
        response = self.client.post(reverse('users:login'), {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'désactivé')
    
    def test_logout(self):
        """Déconnexion"""
        self.client.login(email='test@example.com', password='testpass123')
        
        response = self.client.get(reverse('users:logout'))
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.client.session.get('_auth_user_id'))
    
    def test_register_view_get(self):
        """Affichage du formulaire d'inscription"""
        response = self.client.get(reverse('users:register'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/register.html')
    
    def test_register_success(self):
        """Inscription réussie"""
        response = self.client.post(reverse('users:register'), {
            'email': 'newuser@test.com',
            'nom': 'New',
            'prenom': 'User',
            'date_naissance': '1995-05-15',
            'telephone': '+33698765432',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'role': 'patient'
        })
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Utilisateur.objects.filter(email='newuser@test.com').exists())


class RateLimitingTest(TestCase):
    """
    Vérifie le rate limiting (chantier cache/rate limiting/load balancing) sur
    connecter/inscription : une limite se déclenche bien au-delà du seuil
    (RATELIMIT_LOGIN / RATELIMIT_INSCRIPTION, users/views.py) et un usage
    normal, sous le seuil, n'est jamais bloqué à tort. Distinct de
    BruteForceProtectionTest : ici on plafonne le nombre TOTAL de requêtes,
    pas seulement les échecs d'authentification.
    """

    def setUp(self):
        from django.core.cache import cache
        self.cache = cache
        self.cache.clear()
        self.user = Utilisateur.objects.create_user(
            email='rl@test.com',
            nom='Rate',
            prenom='Limit',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='testpass123'
        )

    def tearDown(self):
        self.cache.clear()

    def test_login_not_blocked_under_threshold(self):
        """RATELIMIT_LOGIN = 10/m : 5 tentatives ne déclenchent jamais le 429."""
        client = Client(REMOTE_ADDR='198.51.100.10')
        for _ in range(5):
            response = client.post(reverse('users:login'), {
                'email': 'rl@test.com',
                'password': 'wrongpassword',
            })
            self.assertNotEqual(response.status_code, 429)

    def test_login_blocked_beyond_threshold(self):
        """Au-delà de RATELIMIT_LOGIN (10/m), la vue renvoie 429 avec un message clair."""
        client = Client(REMOTE_ADDR='198.51.100.11')
        responses = [
            client.post(reverse('users:login'), {
                'email': 'rl@test.com',
                'password': 'wrongpassword',
            })
            for _ in range(11)
        ]
        self.assertTrue(any(r.status_code == 429 for r in responses))
        blocked = next(r for r in responses if r.status_code == 429)
        self.assertContains(blocked, 'Trop de tentatives de connexion', status_code=429)

    def test_inscription_not_blocked_under_threshold(self):
        """RATELIMIT_INSCRIPTION = 5/h : 3 tentatives ne déclenchent jamais le 429."""
        client = Client(REMOTE_ADDR='198.51.100.20')
        for i in range(3):
            response = client.post(reverse('users:register'), {
                'email': f'rl-under-{i}@test.com',
                'nom': 'New', 'prenom': 'User',
                'date_naissance': '1995-05-15',
                'telephone': '+33698765432',
                'password1': 'SecurePass123!',
                'password2': 'SecurePass123!',
                'role': 'patient',
            })
            self.assertNotEqual(response.status_code, 429)

    def test_inscription_blocked_beyond_threshold(self):
        """Au-delà de RATELIMIT_INSCRIPTION (5/h), la vue renvoie 429 avec un message clair."""
        client = Client(REMOTE_ADDR='198.51.100.21')
        responses = [
            client.post(reverse('users:register'), {
                'email': f'rl-over-{i}@test.com',
                'nom': 'New', 'prenom': 'User',
                'date_naissance': '1995-05-15',
                'telephone': '+33698765432',
                'password1': 'SecurePass123!',
                'password2': 'SecurePass123!',
                'role': 'patient',
            }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            for i in range(6)
        ]
        self.assertTrue(any(r.status_code == 429 for r in responses))
        blocked = next(r for r in responses if r.status_code == 429)
        self.assertIn("Trop de tentatives d'inscription", blocked.json()['error'])


class UserManagementTest(TestCase):
    """Tests de gestion des utilisateurs (admin)"""
    
    def setUp(self):
        self.client = Client()
        self.admin = Utilisateur.objects.create_superuser(
            email='admin@test.com',
            nom='Admin',
            prenom='Super',
            date_naissance=date(1980, 1, 1),
            mot_de_passe='admin123'
        )
        self.client.force_login(self.admin)
    def test_liste_utilisateurs_access(self):
        """Accès à la liste des utilisateurs"""
        response = self.client.get(reverse('users:list_users'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'rdv/admin/users/users.html')
    
    def test_liste_utilisateurs_forbidden_for_patient(self):
        """Accès refusé pour patient"""
        patient = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='patient123'
        )
        
        self.client.logout()
        self.client.login(email='patient@test.com', password='patient123')
        
        response = self.client.get(reverse('users:list_users'))
        self.assertEqual(response.status_code, 403)
    
    def test_create_user_by_admin(self):
        """Création d'utilisateur par admin"""
        response = self.client.post(reverse('users:creer_utilisateur'), {
            'email': 'created@test.com',
            'nom': 'Created',
            'prenom': 'User',
            'telephone': '+235 612345678',
            'date_naissance': '1992-08-20',
            'role': 'patient',
            'password1': 'Pass123!',
            'password2': 'Pass123!'
        })
        # Debug oublié : `response.context` est None sur une redirection
        # (la création réussit bien, cf. les deux assertions ci-dessous),
        # donc `response.context['form']` levait TypeError avant même
        # d'atteindre ces assertions.
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Utilisateur.objects.filter(email='created@test.com').exists())

    def test_supprimer_utilisateur_rejects_get(self):
        """La suppression d'un utilisateur n'est plus déclenchable en GET"""
        target = Utilisateur.objects.create_user(
            email='target@test.com',
            nom='Target',
            prenom='User',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='target123'
        )
        response = self.client.get(reverse('users:supprimer_utilisateur', kwargs={'user_id': target.id}))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Utilisateur.objects.filter(pk=target.id).exists())

    def test_supprimer_utilisateur_forbidden_for_patient(self):
        """Un patient ne peut pas supprimer un utilisateur"""
        target = Utilisateur.objects.create_user(
            email='target2@test.com',
            nom='Target',
            prenom='Two',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='target123'
        )
        patient = Utilisateur.objects.create_user(
            email='patient2@test.com',
            nom='Patient',
            prenom='Two',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='patient123'
        )
        self.client.logout()
        self.client.login(email='patient2@test.com', password='patient123')

        response = self.client.post(reverse('users:supprimer_utilisateur', kwargs={'user_id': target.id}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Utilisateur.objects.filter(pk=target.id).exists())


class PasswordChangeTest(TestCase):
    """Tests de changement de mot de passe"""
    
    def setUp(self):
        self.client = Client()
        self.user = Utilisateur.objects.create_user(
            email='user@test.com',
            nom='User',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            mot_de_passe='oldpass123'
        )
        self.client.login(email='user@test.com', password='oldpass123')
    
    def test_change_password_success(self):
        """Changement de mot de passe réussi"""
        response = self.client.post(reverse('users:edit_password'), {
            'old_password': 'oldpass123',
            'new_password1': 'NewSecurePass123!',
            'new_password2': 'NewSecurePass123!'
        })

        # Requête non-AJAX réussie : la vue redirige (PRG), elle ne rend pas
        # de page directement (comportement identique à test_login_success).
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('users:mon_profil'))

        # Vérifie que le mot de passe a changé
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecurePass123!'))
    
    def test_change_password_wrong_old_password(self):
        """Échec - mauvais ancien mot de passe"""
        response = self.client.post(reverse('users:edit_password'), {
            'old_password': 'wrongpass',
            'new_password1': 'NewPass123!',
            'new_password2': 'NewPass123!'
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Vérifie que le mot de passe n'a pas changé
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpass123'))


class ProfileViewTest(TestCase):
    """Tests des vues de profil"""
    
    def setUp(self):
        self.client = Client()
        self.patient = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='patient123'
        )
        self.client.login(email='patient@test.com', password='patient123')
    
    def test_view_own_profile(self):
        """Affichage de son propre profil"""
        response = self.client.get(reverse('users:mon_profil'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Patient')
        self.assertContains(response, 'Test')
    
    def test_edit_user_info(self):
        """Modification des informations utilisateur"""
        # UserEditForm.Meta.fields = ["nom", "prenom", "email", "telephone"] :
        # 'email' est un champ requis du modèle (EmailField sans blank=True).
        # Sans lui, form.is_valid() est False, la vue retombe sur son rendu
        # de formulaire (200 aussi) sans jamais appeler .save() — d'où
        # l'échec silencieux. On soumet ici le jeu de champs réellement requis.
        response = self.client.post(reverse('users:edit_user'), {
            'nom': 'Updated',
            'prenom': 'Name',
            'email': self.patient.email,
            'telephone': '+33612345678'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('success'))

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.nom, 'Updated')
        self.assertEqual(self.patient.prenom, 'Name')


class BruteForceProtectionTest(TestCase):
    """
    Vérifie que la protection anti-bruteforce (chantier 4) est réellement
    active de bout en bout : middleware enregistré, signal user_login_failed
    connecté, compteur d'échecs, et blocage effectif de l'IP après 5 échecs.
    """

    def setUp(self):
        from django.core.cache import cache
        from GestionRDV.celery import app as celery_app

        self.cache = cache
        self.cache.clear()

        self.celery_app = celery_app
        self._previous_eager = celery_app.conf.task_always_eager
        self._previous_propagates = celery_app.conf.task_eager_propagates
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = True

        self.victim = Utilisateur.objects.create_user(
            email='victim@test.com',
            nom='Victim',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='correct-password'
        )

    def tearDown(self):
        self.celery_app.conf.task_always_eager = self._previous_eager
        self.celery_app.conf.task_eager_propagates = self._previous_propagates
        self.cache.clear()

    def test_ip_blocked_after_five_failed_logins(self):
        """5 échecs de connexion depuis la même IP bloquent les tentatives suivantes."""
        client = Client(REMOTE_ADDR='203.0.113.42')

        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(5):
                response = client.post(reverse('users:login'), {
                    'email': 'victim@test.com',
                    'password': 'mauvais-mot-de-passe',
                })
                self.assertEqual(response.status_code, 200)  # formulaire réaffiché

        # Même avec les bons identifiants, l'IP est désormais bloquée.
        response = client.post(reverse('users:login'), {
            'email': 'victim@test.com',
            'password': 'correct-password',
        })
        self.assertEqual(response.status_code, 403)

    def test_ip_not_blocked_before_threshold(self):
        """Moins de 5 échecs ne bloque pas l'IP."""
        client = Client(REMOTE_ADDR='203.0.113.99')

        with self.captureOnCommitCallbacks(execute=True):
            for _ in range(4):
                client.post(reverse('users:login'), {
                    'email': 'victim@test.com',
                    'password': 'mauvais-mot-de-passe',
                })

        response = client.post(reverse('users:login'), {
            'email': 'victim@test.com',
            'password': 'correct-password',
        })
        self.assertEqual(response.status_code, 302)  # connexion acceptée, redirection

    def test_login_failure_survives_broker_unavailable(self):
        """
        Régression : si Redis/Celery est indisponible, .delay() lève une erreur
        de connexion. Un simple mot de passe mal tapé par un utilisateur légitime
        ne doit jamais se traduire par une 500 (safe_delay doit absorber l'échec).
        """
        client = Client(REMOTE_ADDR='203.0.113.7')

        with mock.patch(
            'users.middleware.track_failed_login_attempt.delay',
            side_effect=ConnectionError("Broker Redis indisponible"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                response = client.post(reverse('users:login'), {
                    'email': 'victim@test.com',
                    'password': 'mauvais-mot-de-passe',
                })

        # La page de connexion reste fonctionnelle : formulaire réaffiché, pas de 500.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form', status_code=200)


class ProfilUserViewTest(TestCase):
    """Vérifie que profil_user() ne plante plus sur la comparaison us.ROLE (corrigée en us.role)."""

    def setUp(self):
        self.client = Client()
        self.admin = Utilisateur.objects.create_superuser(
            email='admin@test.com',
            nom='Admin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            mot_de_passe='admin123'
        )
        self.patient = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='patient123'
        )
        self.client.login(email='admin@test.com', password='admin123')

    def test_profil_user_for_patient_role(self):
        """Consultation par un admin du profil d'un utilisateur avec le rôle patient."""
        response = self.client.get(reverse('users:profil', kwargs={'user_id': self.patient.id}))
        self.assertEqual(response.status_code, 200)





