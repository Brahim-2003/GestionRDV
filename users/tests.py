# users/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date, timedelta
from rdv.models import Patient, Medecin

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
        print(response.context['form'].errors)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Utilisateur.objects.filter(email='created@test.com').exists())


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
        
        self.assertEqual(response.status_code, 200)
        
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
        response = self.client.post(reverse('users:edit_user'), {
            'nom': 'Updated',
            'prenom': 'Name',
            'telephone': '+33612345678'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.nom, 'Updated')
        self.assertEqual(self.patient.prenom, 'Name')





