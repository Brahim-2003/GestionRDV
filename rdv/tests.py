# rdv/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import datetime, date, time, timedelta
from decimal import Decimal

from users.models import Utilisateur
from rdv.models import (
    Patient, Medecin, Disponibilite, RendezVous, 
    Notification, RdvHistory, FavoriMedecin
)


class PatientModelTest(TestCase):
    """Tests du modèle Patient"""
    
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Dupont',
            prenom='Jean',
            date_naissance=date(1990, 5, 15),
            role='patient',
            mot_de_passe='test123'
        )
    
    def test_patient_auto_creation(self):
        """Le profil patient se crée automatiquement"""
        self.assertTrue(Patient.objects.filter(user=self.user).exists())
        patient = self.user.profil_patient
        self.assertIsNotNone(patient.numero_patient)
    
    def test_numero_patient_format(self):
        """Format du numéro patient"""
        patient = self.user.profil_patient
        self.assertTrue(patient.numero_patient.startswith('PAT'))
        self.assertEqual(len(patient.numero_patient), 10)  # PAT-XXXXXX
    
    def test_numero_patient_unique(self):
        """Unicité du numéro patient"""
        patient1 = self.user.profil_patient
        
        user2 = Utilisateur.objects.create_user(
            email='patient2@test.com',
            nom='Martin',
            prenom='Pierre',
            date_naissance=date(1985, 3, 20),
            role='patient',
            mot_de_passe='test123'
        )
        patient2 = user2.profil_patient
        
        self.assertNotEqual(patient1.numero_patient, patient2.numero_patient)


class MedecinModelTest(TestCase):
    """Tests du modèle Medecin"""
    
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email='medecin@test.com',
            nom='IBRAHIM',
            prenom='Issa',
            date_naissance=date(1975, 8, 10),
            role='medecin',
            mot_de_passe='test123'
        )
    
    def test_medecin_auto_creation(self):
        """Le profil médecin se crée automatiquement"""
        self.assertTrue(Medecin.objects.filter(user=self.user).exists())
        medecin = self.user.profil_medecin
        self.assertEqual(medecin.specialite, 'generaliste')  # Défaut
    
    def test_medecin_str(self):
        """Représentation string du médecin"""
        medecin = self.user.profil_medecin
        expected = f"Dr. {self.user.nom_complet()} - {medecin.specialite}"
        self.assertEqual(str(medecin), expected)
    
    def test_prochaine_disponibilite_empty(self):
        """Prochaine disponibilité sans créneaux définis"""
        medecin = self.user.profil_medecin
        self.assertIsNone(medecin.prochaine_disponibilite)


class DisponibiliteModelTest(TestCase):
    """Tests du modèle Disponibilite"""
    
    def setUp(self):
        self.medecin_user = Utilisateur.objects.create_user(
            email='medecin@test.com',
            nom='Medecin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='test123'
        )
        self.medecin = self.medecin_user.profil_medecin
    
    def test_create_disponibilite_hebdo(self):
        """Création créneau hebdomadaire"""
        dispo = Disponibilite.objects.create(
            medecin=self.medecin,
            jour='mon',
            heure_debut=time(9, 0),
            heure_fin=time(12, 0),
            is_active=True
        )
        
        self.assertEqual(dispo.jour, 'mon')
        self.assertIsNone(dispo.date_specific)
        self.assertTrue(dispo.is_active)
    
    def test_create_disponibilite_specifique(self):
        """Création créneau ponctuel"""
        future_date = date.today() + timedelta(days=10)
        
        dispo = Disponibilite.objects.create(
            medecin=self.medecin,
            date_specific=future_date,
            jour='',
            heure_debut=time(14, 0),
            heure_fin=time(18, 0),
            is_active=True
        )
        
        self.assertEqual(dispo.date_specific, future_date)
        self.assertEqual(dispo.jour, '')
    
    def test_clean_validation_xor_jour_date(self):
        """Validation XOR entre jour et date_specific"""
        # Les deux renseignés
        dispo = Disponibilite(
            medecin=self.medecin,
            jour='mon',
            date_specific=date.today(),
            heure_debut=time(9, 0),
            heure_fin=time(12, 0)
        )
        
        with self.assertRaises(ValidationError):
            dispo.full_clean()
        
        # Aucun des deux
        dispo2 = Disponibilite(
            medecin=self.medecin,
            jour='',
            date_specific=None,
            heure_debut=time(9, 0),
            heure_fin=time(12, 0)
        )
        
        with self.assertRaises(ValidationError):
            dispo2.full_clean()
    
    def test_clean_validation_heures(self):
        """Validation heure_debut < heure_fin"""
        dispo = Disponibilite(
            medecin=self.medecin,
            jour='mon',
            heure_debut=time(12, 0),
            heure_fin=time(9, 0)  # Incohérent
        )
        
        with self.assertRaises(ValidationError):
            dispo.full_clean()
    
    def test_clean_validation_chevauchement(self):
        """Détection de chevauchements"""
        # Premier créneau
        Disponibilite.objects.create(
            medecin=self.medecin,
            jour='mon',
            heure_debut=time(9, 0),
            heure_fin=time(12, 0)
        )
        
        # Créneau qui chevauche
        dispo2 = Disponibilite(
            medecin=self.medecin,
            jour='mon',
            heure_debut=time(11, 0),
            heure_fin=time(14, 0)
        )
        
        with self.assertRaises(ValidationError):
            dispo2.full_clean()
    
    def test_get_slot_datetimes_hebdo(self):
        """Génération des slots pour créneau hebdomadaire"""
        dispo = Disponibilite.objects.create(
            medecin=self.medecin,
            jour='mon',
            heure_debut=time(9, 0),
            heure_fin=time(12, 0)
        )
        
        slots = dispo.get_slot_datetimes()
        
        self.assertEqual(len(slots), 1)
        start, end = slots[0]
        self.assertEqual(start.time(), time(9, 0))
        self.assertEqual(end.time(), time(12, 0))


class RendezVousModelTest(TestCase):
    """Tests du modèle RendezVous"""
    
    def setUp(self):
        # Patient
        self.patient_user = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='test123'
        )
        self.patient = self.patient_user.profil_patient
        
        # Médecin
        self.medecin_user = Utilisateur.objects.create_user(
            email='medecin@test.com',
            nom='Medecin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='test123'
        )
        self.medecin = self.medecin_user.profil_medecin
        
        # Disponibilité
        Disponibilite.objects.create(
            medecin=self.medecin,
            jour='mon',
            heure_debut=time(9, 0),
            heure_fin=time(18, 0)
        )
    
    def test_create_rendez_vous(self):
        """Création d'un rendez-vous"""
        rdv_date = timezone.now() + timedelta(days=7)
        
        rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=rdv_date,
            duree_minutes=30,
            motif='Consultation générale',
            statut='programme'
        )
        
        self.assertEqual(rdv.statut, 'programme')
        self.assertEqual(rdv.duree_minutes, 30)
        self.assertIsNotNone(rdv.date_creation)
    
    def test_rdv_str(self):
        """Représentation string du RDV"""
        rdv_date = timezone.now() + timedelta(days=7)
        rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=rdv_date,
            motif='Test'
        )
        
        expected = f"RDV {self.patient.user.nom_complet()} - Dr. {self.medecin.user.nom_complet()}"
        self.assertIn("RDV", str(rdv))
    
    def test_can_transition_to(self):
        """Vérification des transitions autorisées"""
        rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=timezone.now() + timedelta(days=1),
            statut='programme'
        )
        
        # Transitions valides depuis 'programme'
        self.assertTrue(rdv.can_transition_to('confirme'))
        self.assertTrue(rdv.can_transition_to('annule'))
        self.assertTrue(rdv.can_transition_to('reporte'))
        
        # Transition invalide
        self.assertFalse(rdv.can_transition_to('termine'))
    
    def test_confirm_rdv(self):
        """Confirmation d'un rendez-vous"""
        rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=timezone.now() + timedelta(days=1),
            statut='programme'
        )
        
        rdv.confirm(by_user=self.medecin_user)
        
        self.assertEqual(rdv.statut, 'confirme')
        
        # Vérifie l'historique
        self.assertTrue(RdvHistory.objects.filter(
            rdv=rdv,
            action='confirm'
        ).exists())
    
    def test_cancel_rdv(self):
        """Annulation d'un rendez-vous"""
        rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=timezone.now() + timedelta(days=1),
            statut='confirme'
        )
        
        rdv.cancel(description='Patient indisponible', by_user=self.patient_user)
        
        self.assertEqual(rdv.statut, 'annule')
        self.assertEqual(rdv.raison_annulation, 'Patient indisponible')
        
        # Vérifie l'historique
        history = RdvHistory.objects.filter(rdv=rdv, action='cancel').first()
        self.assertIsNotNone(history)
        self.assertEqual(history.description, 'Patient indisponible')
    
    def test_report_rdv_by_medecin(self):
        """Report d'un rendez-vous par le médecin"""
        rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=timezone.now() + timedelta(days=1),
            statut='confirme'
        )
        
        old_date = rdv.date_heure_rdv
        new_date = timezone.now() + timedelta(days=5)
        
        rdv.report(
            new_datetime=new_date,
            raison='Urgence médicale',
            initiator='medecin',
            by_user=self.medecin_user
        )
        
        self.assertEqual(rdv.statut, 'confirme')  # Médecin confirme directement
        self.assertEqual(rdv.date_heure_rdv, new_date)
        self.assertEqual(rdv.ancienne_date_heure, old_date)
        self.assertEqual(rdv.report_initiator, 'medecin')
    
    def test_report_rdv_by_patient(self):
        """Report d'un rendez-vous par le patient"""
        rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=timezone.now() + timedelta(days=1),
            statut='confirme'
        )
        
        new_date = timezone.now() + timedelta(days=3)
        
        rdv.report(
            new_datetime=new_date,
            raison='Empêchement',
            initiator='patient',
            by_user=self.patient_user
        )
        
        self.assertEqual(rdv.statut, 'reporte')  # Attente confirmation médecin
        self.assertEqual(rdv.report_initiator, 'patient')
    
    def test_invalid_transition_raises_error(self):
        """Transition invalide lève une erreur"""
        rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=timezone.now() + timedelta(days=1),
            statut='termine'
        )
        
        with self.assertRaises(ValueError):
            rdv.confirm()


class NotificationModelTest(TestCase):
    """Tests du modèle Notification"""
    
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email='user@test.com',
            nom='User',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            mot_de_passe='test123'
        )
    
    def test_create_notification(self):
        """Création d'une notification"""
        notif = Notification.objects.create(
            user=self.user,
            message='Test notification',
            type='info',
            category='system'
        )
        
        self.assertEqual(notif.message, 'Test notification')
        self.assertFalse(notif.is_read)
        self.assertIsNotNone(notif.date_envoi)
        self.assertIsNone(notif.date_read)
    
    def test_mark_as_read(self):
        """Marquer une notification comme lue"""
        notif = Notification.objects.create(
            user=self.user,
            message='Test',
            type='info'
        )
        
        notif.mark_as_read()
        
        self.assertTrue(notif.is_read)
        self.assertIsNotNone(notif.date_read)
    
    def test_time_since_property(self):
        """Propriété time_since"""
        notif = Notification.objects.create(
            user=self.user,
            message='Test',
            type='info'
        )
        
        time_since = notif.time_since
        self.assertIsNotNone(time_since)
        self.assertIn('second', time_since.lower() or 'minute' in time_since.lower())


class RdvHistoryTest(TestCase):
    """Tests de l'historique des RDV"""
    
    def setUp(self):
        self.patient_user = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='test123'
        )
        self.patient = self.patient_user.profil_patient
        
        self.medecin_user = Utilisateur.objects.create_user(
            email='medecin@test.com',
            nom='Medecin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='test123'
        )
        self.medecin = self.medecin_user.profil_medecin
        
        self.rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=timezone.now() + timedelta(days=1),
            statut='programme'
        )
    
    def test_history_created_on_confirm(self):
        """Historique créé lors de la confirmation"""
        self.rdv.confirm(by_user=self.medecin_user)
        
        history = RdvHistory.objects.filter(
            rdv=self.rdv,
            action='confirm'
        ).first()
        
        self.assertIsNotNone(history)
        self.assertEqual(history.performed_by, self.medecin_user)
    
    def test_history_created_on_cancel(self):
        """Historique créé lors de l'annulation"""
        self.rdv.cancel(description='Test annulation', by_user=self.patient_user)
        
        history = RdvHistory.objects.filter(
            rdv=self.rdv,
            action='cancel'
        ).first()
        
        self.assertIsNotNone(history)
        self.assertEqual(history.description, 'Test annulation')
    
    def test_history_ordering(self):
        """L'historique est trié par timestamp décroissant"""
        self.rdv.confirm(by_user=self.medecin_user)
        self.rdv.cancel(description='Test', by_user=self.patient_user)
        
        histories = RdvHistory.objects.filter(rdv=self.rdv)
        
        # Le plus récent (cancel) doit être en premier
        self.assertEqual(histories.first().action, 'cancel')
        self.assertEqual(histories.last().action, 'confirm')


class FavoriMedecinTest(TestCase):
    """Tests des favoris médecin"""
    
    def setUp(self):
        self.patient_user = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='test123'
        )
        self.patient = self.patient_user.profil_patient
        
        self.medecin_user = Utilisateur.objects.create_user(
            email='medecin@test.com',
            nom='Medecin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='test123'
        )
        self.medecin = self.medecin_user.profil_medecin
    
    def test_add_favori(self):
        """Ajout d'un médecin aux favoris"""
        favori = FavoriMedecin.objects.create(
            patient=self.patient,
            medecin=self.medecin
        )
        
        self.assertIsNotNone(favori.date_ajout)
        self.assertEqual(favori.patient, self.patient)
        self.assertEqual(favori.medecin, self.medecin)
    
    def test_unique_together_constraint(self):
        """Un même médecin ne peut être ajouté deux fois"""
        FavoriMedecin.objects.create(
            patient=self.patient,
            medecin=self.medecin
        )
        
        with self.assertRaises(Exception):  # IntegrityError
            FavoriMedecin.objects.create(
                patient=self.patient,
                medecin=self.medecin
            )


class DashboardViewTest(TestCase):
    """Tests des vues dashboard"""
    
    def setUp(self):
        self.client = Client()
        
        # Admin
        self.admin = Utilisateur.objects.create_superuser(
            email='admin@test.com',
            nom='Admin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            mot_de_passe='admin123'
        )
        
        # Médecin
        self.medecin_user = Utilisateur.objects.create_user(
            email='medecin@test.com',
            nom='Medecin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='medecin123'
        )
        
        # Patient
        self.patient_user = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='patient123'
        )
    
    def test_admin_dashboard_access(self):
        """Accès au dashboard admin"""
        self.client.login(email='admin@test.com', password='admin123')
        response = self.client.get(reverse('rdv:dashboard_redirect'))
        
        self.assertEqual(response.status_code, 200)
    
    def test_medecin_dashboard_access(self):
        """Accès au dashboard médecin"""
        self.client.login(email='medecin@test.com', password='medecin123')
        response = self.client.get(reverse('rdv:dashboard_medecin'))
        
        self.assertEqual(response.status_code, 200)
    
    def test_patient_dashboard_access(self):
        """Accès au dashboard patient"""
        self.client.login(email='patient@test.com', password='patient123')
        response = self.client.get(reverse('rdv:dashboard_patient'))
        
        self.assertEqual(response.status_code, 200)
    
    def test_unauthorized_access_forbidden(self):
        """Accès non autorisé refusé"""
        # Patient tente d'accéder au dashboard admin
        self.client.login(email='patient@test.com', password='patient123')
        response = self.client.get(reverse('rdv:dashboard_redirect'))
        
        self.assertEqual(response.status_code, 403)


class PriseRdvViewTest(TestCase):
    """Tests de la prise de rendez-vous"""
    
    def setUp(self):
        self.client = Client()
        
        # Patient
        self.patient_user = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='patient123'
        )
        self.patient = self.patient_user.profil_patient
        
        # Médecin
        self.medecin_user = Utilisateur.objects.create_user(
            email='medecin@test.com',
            nom='IBRAHIM',
            prenom='Issa',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='medecin123'
        )
        self.medecin = self.medecin_user.profil_medecin
        self.medecin.specialite = 'cardiologue'
        self.medecin.save()
        
        # Disponibilité
        Disponibilite.objects.create(
            medecin=self.medecin,
            jour='mon',
            heure_debut=time(9, 0),
            heure_fin=time(18, 0)
        )
        
        self.client.login(email='patient@test.com', password='patient123')
    
    def test_prendre_rdv_page(self):
        """Affichage de la page de prise de RDV"""
        response = self.client.get(reverse('rdv:prendre_rdv'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'médecin')
    
    def test_api_search_medecins(self):
        """Recherche de médecins via API"""
        response = self.client.get(reverse('rdv:api_search_medecins'), {
            'specialite': 'cardiologue'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('medecins', data)
        self.assertEqual(len(data['medecins']), 1)
    
    def test_api_creneaux_medecin(self):
        """Récupération des créneaux d'un médecin"""
        # Calcule une date lundi prochain
        today = date.today()
        days_ahead = 0 - today.weekday()  # Lundi = 0
        if days_ahead <= 0:
            days_ahead += 7
        next_monday = today + timedelta(days=days_ahead)
        
        response = self.client.get(
            reverse('rdv:api_creneaux_medecin', kwargs={'medecin_id': self.medecin.id}),
            {
                'date_debut': next_monday.isoformat(),
                'date_fin': (next_monday + timedelta(days=7)).isoformat()
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('creneaux', data)
        self.assertGreater(len(data['creneaux']), 0)
    
    def test_api_reserver_rdv(self):
        """Réservation d'un RDV via API"""
        # Date lundi prochain 10h
        today = date.today()
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_monday = today + timedelta(days=days_ahead)
        rdv_datetime = timezone.make_aware(
            datetime.combine(next_monday, time(10, 0))
        )
        
        response = self.client.post(
            reverse('rdv:api_reserver_rdv'),
            data={
                'medecin_id': self.medecin.id,
                'datetime': rdv_datetime.isoformat(),
                'motif': 'Consultation cardiologie'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Vérifie que le RDV existe
        rdv = RendezVous.objects.get(id=data['rdv_id'])
        self.assertEqual(rdv.patient, self.patient)
        self.assertEqual(rdv.medecin, self.medecin)
        self.assertEqual(rdv.statut, 'programme')


class GestionDisponibilitesViewTest(TestCase):
    """Tests de la gestion des disponibilités"""
    
    def setUp(self):
        self.client = Client()
        
        self.medecin_user = Utilisateur.objects.create_user(
            email='medecin@test.com',
            nom='Medecin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='medecin123'
        )
        self.medecin = self.medecin_user.profil_medecin
        
        self.client.login(email='medecin@test.com', password='medecin123')
    
    def test_disponibilites_list_page(self):
        """Affichage de la page de gestion des disponibilités"""
        response = self.client.get(reverse('rdv:disponibilites_list'))
        
        self.assertEqual(response.status_code, 200)
    
    def test_add_disponibilite_hebdo(self):
        """Ajout d'un créneau hebdomadaire"""
        response = self.client.post(
            reverse('rdv:disponibilite_hebdo_add', kwargs={'day_key': 'monday'}),
            {
                'jour': 'mon',
                'heure_debut': '09:00',
                'heure_fin': '12:00'
            }
        )
        
        # Vérifie la création
        self.assertTrue(
            Disponibilite.objects.filter(
                medecin=self.medecin,
                jour='mon'
            ).exists()
        )
    
    def test_add_disponibilite_specifique(self):
        """Ajout d'un créneau ponctuel"""
        future_date = (date.today() + timedelta(days=10)).isoformat()
        
        response = self.client.post(
            reverse('rdv:disponibilite_specifique_add'),
            {
                'date_specific': future_date,
                'heure_debut': '14:00',
                'heure_fin': '18:00'
            }
        )
        
        # Vérifie la création
        self.assertTrue(
            Disponibilite.objects.filter(
                medecin=self.medecin,
                date_specific=future_date
            ).exists()
        )
    
    def test_toggle_disponibilite_status(self):
        """Activation/désactivation d'une disponibilité"""
        dispo = Disponibilite.objects.create(
            medecin=self.medecin,
            jour='mon',
            heure_debut=time(9, 0),
            heure_fin=time(12, 0),
            is_active=True
        )
        
        response = self.client.post(
            reverse('rdv:toggle_dispo_status', kwargs={'dispo_id': dispo.id}),
            data={'is_active': False},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        dispo.refresh_from_db()
        self.assertFalse(dispo.is_active)


class GestionRdvMedecinViewTest(TestCase):
    """Tests de la gestion des RDV par le médecin"""
    
    def setUp(self):
        self.client = Client()
        
        # Patient
        self.patient_user = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='patient123'
        )
        self.patient = self.patient_user.profil_patient
        
        # Médecin
        self.medecin_user = Utilisateur.objects.create_user(
            email='medecin@test.com',
            nom='Medecin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='medecin123'
        )
        self.medecin = self.medecin_user.profil_medecin
        
        # RDV
        self.rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=timezone.now() + timedelta(days=3),
            statut='programme',
            motif='Test'
        )
        
        self.client.login(email='medecin@test.com', password='medecin123')
    
    def test_liste_rdv_medecin(self):
        """Liste des RDV du médecin"""
        response = self.client.get(reverse('rdv:liste_rdv_medecin'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test')
    
    def test_confirmer_rdv(self):
        """Confirmation d'un RDV"""
        response = self.client.post(
            reverse('rdv:confirmer_rdv', kwargs={'rdv_id': self.rdv.id})
        )
        
        self.assertEqual(response.status_code, 200)
        
        self.rdv.refresh_from_db()
        self.assertEqual(self.rdv.statut, 'confirme')
    
    def test_annuler_rdv_get(self):
        """Affichage du formulaire d'annulation"""
        response = self.client.get(
            reverse('rdv:annuler_rdv', kwargs={'rdv_id': self.rdv.id})
        )
        
        self.assertEqual(response.status_code, 200)
    
    def test_annuler_rdv_post(self):
        """Annulation d'un RDV"""
        self.rdv.statut = 'confirme'
        self.rdv.save()
        
        response = self.client.post(
            reverse('rdv:annuler_rdv', kwargs={'rdv_id': self.rdv.id}),
            data={'description': 'Urgence médicale'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        self.rdv.refresh_from_db()
        self.assertEqual(self.rdv.statut, 'annule')
        self.assertEqual(self.rdv.raison_annulation, 'Urgence médicale')
    
    def test_reporter_rdv(self):
        """Report d'un RDV"""
        new_date = (timezone.now() + timedelta(days=7)).replace(hour=14, minute=0)
        
        response = self.client.post(
            reverse('rdv:reporter_rdv', kwargs={'rdv_id': self.rdv.id}),
            data={
                'nouvelle_date': new_date.date().isoformat(),
                'nouvelle_heure': new_date.time().strftime('%H:%M'),
                'raison': 'Conflit agenda'
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        self.rdv.refresh_from_db()
        self.assertEqual(self.rdv.statut, 'confirme')  # Médecin confirme directement


class NotificationViewTest(TestCase):
    """Tests des vues de notifications"""
    
    def setUp(self):
        self.client = Client()
        
        self.user = Utilisateur.objects.create_user(
            email='user@test.com',
            nom='User',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            mot_de_passe='test123'
        )
        
        # Créer quelques notifications
        for i in range(5):
            Notification.objects.create(
                user=self.user,
                message=f'Notification {i}',
                type='info',
                is_read=(i % 2 == 0)
            )
        
        self.client.login(email='user@test.com', password='test123')
    
    def test_list_notif(self):
        """Affichage de la liste des notifications"""
        response = self.client.get(reverse('rdv:list_notif'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notification')
    
    def test_mark_as_read(self):
        """Marquer une notification comme lue"""
        notif = Notification.objects.filter(user=self.user, is_read=False).first()
        
        response = self.client.post(
            reverse('rdv:mark_as_read', kwargs={'notification_id': notif.id})
        )
        
        notif.refresh_from_db()
        self.assertTrue(notif.is_read)
    
    def test_mark_all_as_read(self):
        """Marquer toutes les notifications comme lues"""
        response = self.client.post(reverse('rdv:mark_all_as_read'))
        
        unread_count = Notification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(unread_count, 0)
    
    def test_delete_notification(self):
        """Supprimer une notification"""
        notif = Notification.objects.filter(user=self.user).first()
        notif_id = notif.id
        
        response = self.client.post(
            reverse('rdv:delete_notification', kwargs={'notification_id': notif_id})
        )
        
        self.assertFalse(Notification.objects.filter(id=notif_id).exists())
    
    def test_get_notification_count(self):
        """Récupération du compteur de notifications"""
        response = self.client.get(reverse('rdv:get_notification_count'))
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('unread_count', data)


class UtilsFunctionTest(TestCase):
    """Tests des fonctions utilitaires"""
    
    def setUp(self):
        self.user = Utilisateur.objects.create_user(
            email='user@test.com',
            nom='User',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            mot_de_passe='test123'
        )
    
    def test_create_and_send_notification(self):
        """Test de la fonction create_and_send_notification"""
        from rdv.utils import create_and_send_notification
        
        sent, notif = create_and_send_notification(
            self.user,
            'Test Subject',
            'Test Message',
            notif_type='info',
            category='system'
        )
        
        self.assertIsNotNone(notif)
        self.assertEqual(notif.message, 'Test Message')
        self.assertEqual(notif.type, 'info')
        
        # Vérifie en base
        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                message='Test Message'
            ).exists()
        )


# Tests de performance et d'intégration

class PerformanceTest(TestCase):
    """Tests de performance basiques"""
    
    def test_bulk_rdv_creation_performance(self):
        """Création en masse de RDV"""
        import time
        
        # Créer patient et médecin
        patient_user = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='test123'
        )
        patient = patient_user.profil_patient
        
        medecin_user = Utilisateur.objects.create_user(
            email='medecin@test.com',
            nom='Medecin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='test123'
        )
        medecin = medecin_user.profil_medecin
        
        # Mesurer le temps de création de 100 RDV
        start_time = time.time()
        
        rdvs = []
        for i in range(100):
            rdvs.append(RendezVous(
                patient=patient,
                medecin=medecin,
                date_heure_rdv=timezone.now() + timedelta(days=i),
                statut='programme',
                motif=f'Test {i}'
            ))
        
        RendezVous.objects.bulk_create(rdvs)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Doit prendre moins de 2 secondes
        self.assertLess(duration, 2.0)
        self.assertEqual(RendezVous.objects.count(), 100)




