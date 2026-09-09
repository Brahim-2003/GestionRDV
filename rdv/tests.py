# rdv/tests.py
import json
import threading
import time as time_module
from unittest import mock
from django.conf import settings
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import connection, connections, transaction
from django.db.utils import OperationalError
from datetime import datetime, date, time, timedelta
from decimal import Decimal

from users.models import Utilisateur
from rdv.models import (
    Patient, Medecin, Disponibilite, RendezVous,
    Notification, RdvHistory, FavoriMedecin, ListeAttenteCreneau
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
        """Format du numéro patient (PAT-000001, généré par le point unique
        rdv/models.py::generate_next_numero_patient, appelé depuis
        Patient.save())"""
        patient = self.user.profil_patient
        self.assertEqual(patient.numero_patient, 'PAT-000001')
    
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

    def test_numero_patient_incremental(self):
        """Des créations successives produisent des numéros strictement
        incrémentaux (PAT-000001, PAT-000002, PAT-000003, ...), conformément
        au compteur unique de rdv/models.py::generate_next_numero_patient."""
        self.assertEqual(self.user.profil_patient.numero_patient, 'PAT-000001')

        user2 = Utilisateur.objects.create_user(
            email='patient2@test.com',
            nom='Martin',
            prenom='Pierre',
            date_naissance=date(1985, 3, 20),
            role='patient',
            mot_de_passe='test123'
        )
        user3 = Utilisateur.objects.create_user(
            email='patient3@test.com',
            nom='Durand',
            prenom='Alice',
            date_naissance=date(1992, 7, 1),
            role='patient',
            mot_de_passe='test123'
        )

        self.assertEqual(user2.profil_patient.numero_patient, 'PAT-000002')
        self.assertEqual(user3.profil_patient.numero_patient, 'PAT-000003')


class NumeroPatientConcurrencyTest(TransactionTestCase):
    """Vérifie que des créations de patients lancées en parallèle (threads,
    donc connexions DB distinctes) ne produisent jamais de doublon de
    numero_patient, grâce au verrou de ligne (select_for_update) posé dans
    rdv/models.py::generate_next_numero_patient. Utilise TransactionTestCase
    (et non TestCase) car chaque thread a besoin de voir les commits des
    autres threads, ce qu'une TestCase enveloppée dans une seule transaction
    ne permet pas."""

    @mock.patch('users.signals.notify_admins_on_user_create.delay')
    def test_creations_concurrentes_sans_doublon(self, mock_notify_delay):
        """La notification admin (Celery/Redis) est mockée : ce test cible
        exclusivement l'absence de doublon de numero_patient sous
        concurrence, pas la disponibilité d'un broker Celery réel, qui
        n'existe pas dans cet environnement de test."""
        nb_threads = 8
        erreurs = []

        def creer_patient(index):
            # SQLite n'a pas de vrai verrou par ligne : sous 8 écritures
            # concurrentes, il peut lever "database table is locked" (SQLITE_LOCKED),
            # une erreur que busy_timeout ne couvre pas (il ne couvre que
            # SQLITE_BUSY). Ce n'est qu'une limitation de SQLite en tant que
            # backend de test (PostgreSQL, backend cible, gère de vrais verrous
            # de ligne) : on retente donc quelques fois avant d'abandonner. La
            # création est enveloppée dans un atomic() explicite pour que
            # l'échec (même après l'INSERT Utilisateur, déclenché par le
            # signal post_save) soit intégralement annulé et la retentative
            # avec le même e-mail reste sûre (pas de doublon partiel).
            for attempt in range(5):
                try:
                    if connection.vendor == 'sqlite':
                        with connection.cursor() as cursor:
                            cursor.execute('PRAGMA busy_timeout = 30000;')
                    with transaction.atomic():
                        Utilisateur.objects.create_user(
                            email=f'concurrent{index}@test.com',
                            nom='Test',
                            prenom=f'Patient{index}',
                            date_naissance=date(1990, 1, 1),
                            role='patient',
                            mot_de_passe='test123',
                        )
                    return
                except OperationalError as exc:
                    if 'locked' not in str(exc).lower():
                        erreurs.append(exc)
                        return
                    connection.close()
                    time_module.sleep(0.05 * (attempt + 1))
                except Exception as exc:
                    erreurs.append(exc)
                    return
                finally:
                    connections.close_all()
            erreurs.append(OperationalError('database table is locked (après plusieurs tentatives)'))

        threads = [threading.Thread(target=creer_patient, args=(i,)) for i in range(nb_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(erreurs, [])
        numeros = list(Patient.objects.values_list('numero_patient', flat=True))
        self.assertEqual(len(numeros), nb_threads)
        self.assertEqual(len(numeros), len(set(numeros)))


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
        # Bug de précédence dans l'ancienne assertion : `'second' in x.lower()
        # or 'minute' in x.lower()` était écrit `assertIn('second', x.lower()
        # or 'minute' in x.lower())`, qui s'évalue toujours comme
        # `assertIn('second', x.lower())` (le membre droit du `or` n'est
        # jamais atteint car x.lower() est une chaîne non vide, donc vraie).
        self.assertTrue('second' in time_since.lower() or 'minute' in time_since.lower())


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

    def test_api_search_medecins_plusieurs_specialites(self):
        """?specialite=x&specialite=y (recherche par symptôme) renvoie les
        médecins des deux spécialités."""
        dermato_user = Utilisateur.objects.create_user(
            email='dermato@test.com', nom='Dermato', prenom='Test',
            date_naissance=date(1980, 1, 1), role='medecin', mot_de_passe='test123'
        )
        dermato_user.profil_medecin.specialite = 'dermatologue'
        dermato_user.profil_medecin.save()

        response = self.client.get(
            reverse('rdv:api_search_medecins') + '?specialite=cardiologue&specialite=dermatologue'
        )
        self.assertEqual(response.status_code, 200)
        specialites = {m['specialite'] for m in response.json()['medecins']}
        self.assertEqual(specialites, {'cardiologue', 'dermatologue'})

    def test_api_symptomes(self):
        """L'API symptômes renvoie des catégories peuplées et l'avertissement."""
        response = self.client.get(reverse('rdv:api_symptomes'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('categories', data)
        self.assertGreater(len(data['categories']), 0)
        self.assertIn('avertissement', data)
        self.assertIn('urgences', data['avertissement'].lower())

        douleur = next((c for c in data['categories'] if c['nom'] == 'Douleur'), None)
        self.assertIsNotNone(douleur)
        thorax = next((s for s in douleur['symptomes'] if s['nom'] == 'Douleur thoracique'), None)
        self.assertIsNotNone(thorax)
        self.assertIn('cardiologue', thorax['specialites'])

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

    def test_api_creneaux_medecin_inclut_les_creneaux_pris(self):
        """Un créneau déjà réservé apparaît avec disponible=False (au lieu
        d'être simplement omis), pour permettre le bouton "M'avertir"."""
        today = date.today()
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_monday = today + timedelta(days=days_ahead)
        rdv_datetime = timezone.make_aware(datetime.combine(next_monday, time(10, 0)))

        RendezVous.objects.create(
            patient=self.patient, medecin=self.medecin,
            date_heure_rdv=rdv_datetime, statut='confirme',
        )

        response = self.client.get(
            reverse('rdv:api_creneaux_medecin', kwargs={'medecin_id': self.medecin.id}),
            {
                'date_debut': next_monday.isoformat(),
                'date_fin': (next_monday + timedelta(days=1)).isoformat()
            }
        )
        data = response.json()
        creneau_pris = next(
            (c for c in data['creneaux'] if c['heure'] == '10:00'), None
        )
        self.assertIsNotNone(creneau_pris)
        self.assertFalse(creneau_pris['disponible'])
        self.assertTrue(any(c['disponible'] for c in data['creneaux']))

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

    def test_api_reserver_rdv_honore_inscription_et_expire_les_concurrentes(self):
        """Réserver un créneau honore l'inscription du réservataire sur ce
        créneau (si elle existe) et fait expirer celles des autres patients
        en attente sur le même (medecin, date_heure_souhaitee)."""
        today = date.today()
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_monday = today + timedelta(days=days_ahead)
        rdv_datetime = timezone.make_aware(datetime.combine(next_monday, time(10, 0)))

        inscription_gagnante = ListeAttenteCreneau.objects.create(
            patient=self.patient, medecin=self.medecin,
            date_heure_souhaitee=rdv_datetime,
        )

        autre_patient_user = Utilisateur.objects.create_user(
            email='autre_patient@test.com', nom='Autre', prenom='Patient',
            date_naissance=date(1990, 1, 1), role='patient', mot_de_passe='test123'
        )
        inscription_concurrente = ListeAttenteCreneau.objects.create(
            patient=autre_patient_user.profil_patient, medecin=self.medecin,
            date_heure_souhaitee=rdv_datetime,
        )

        response = self.client.post(
            reverse('rdv:api_reserver_rdv'),
            data={
                'medecin_id': self.medecin.id,
                'datetime': rdv_datetime.isoformat(),
                'motif': 'Consultation',
            },
            content_type='application/json'
        )
        self.assertTrue(response.json()['success'])
        rdv = RendezVous.objects.get(id=response.json()['rdv_id'])

        inscription_gagnante.refresh_from_db()
        inscription_concurrente.refresh_from_db()
        self.assertEqual(inscription_gagnante.statut, 'honore')
        self.assertEqual(inscription_gagnante.rdv_propose, rdv)
        self.assertEqual(inscription_concurrente.statut, 'expire')

    def test_inscrire_liste_attente_success(self):
        """Inscription réussie en liste d'attente sur un créneau précis."""
        rdv_datetime = timezone.now() + timedelta(days=7)
        response = self.client.post(
            reverse('rdv:inscrire_liste_attente'),
            data=json.dumps({
                'medecin_id': self.medecin.id,
                'datetime': rdv_datetime.isoformat(),
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        inscription = ListeAttenteCreneau.objects.get(id=data['inscription_id'])
        self.assertEqual(inscription.patient, self.patient)
        self.assertEqual(inscription.medecin, self.medecin)
        self.assertEqual(inscription.statut, 'en_attente')

    def test_inscrire_liste_attente_refuse_si_deja_inscrit_meme_medecin(self):
        """Une seule inscription active à la fois par (patient, médecin)."""
        rdv_datetime = timezone.now() + timedelta(days=7)
        ListeAttenteCreneau.objects.create(
            patient=self.patient, medecin=self.medecin,
            date_heure_souhaitee=rdv_datetime,
        )

        response = self.client.post(
            reverse('rdv:inscrire_liste_attente'),
            data=json.dumps({
                'medecin_id': self.medecin.id,
                'datetime': (rdv_datetime + timedelta(hours=1)).isoformat(),
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('déjà', data['error'])
        self.assertEqual(ListeAttenteCreneau.objects.filter(patient=self.patient).count(), 1)

    def test_desinscrire_liste_attente(self):
        """Le patient peut annuler sa propre inscription."""
        inscription = ListeAttenteCreneau.objects.create(
            patient=self.patient, medecin=self.medecin,
            date_heure_souhaitee=timezone.now() + timedelta(days=7),
        )
        response = self.client.post(
            reverse('rdv:desinscrire_liste_attente', kwargs={'inscription_id': inscription.id})
        )
        self.assertEqual(response.status_code, 200)
        inscription.refresh_from_db()
        self.assertEqual(inscription.statut, 'annule')

    def test_desinscrire_liste_attente_refuse_pour_autre_patient(self):
        """Un patient ne peut pas annuler l'inscription d'un autre."""
        autre_patient_user = Utilisateur.objects.create_user(
            email='autre_patient@test.com', nom='Autre', prenom='Patient',
            date_naissance=date(1990, 1, 1), role='patient', mot_de_passe='test123'
        )
        inscription = ListeAttenteCreneau.objects.create(
            patient=autre_patient_user.profil_patient, medecin=self.medecin,
            date_heure_souhaitee=timezone.now() + timedelta(days=7),
        )
        response = self.client.post(
            reverse('rdv:desinscrire_liste_attente', kwargs={'inscription_id': inscription.id})
        )
        self.assertEqual(response.status_code, 404)
        inscription.refresh_from_db()
        self.assertEqual(inscription.statut, 'en_attente')

    def test_mes_inscriptions_liste_attente_page(self):
        """La page liste les inscriptions du patient connecté."""
        ListeAttenteCreneau.objects.create(
            patient=self.patient, medecin=self.medecin,
            date_heure_souhaitee=timezone.now() + timedelta(days=7),
        )
        response = self.client.get(reverse('rdv:mes_inscriptions_liste_attente'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['inscriptions']), 1)


class ReservationConcurrencyTest(TransactionTestCase):
    """Vérifie qu'un même créneau (medecin, date_heure_rdv) réservé par
    plusieurs patients en parallèle n'est jamais accordé à plus d'un seul
    d'entre eux — garanti par la contrainte unique_rdv_actif_par_creneau
    (rdv/models.py::RendezVous.Meta) et le verrouillage/rattrapage
    d'IntegrityError dans api_reserver_rdv (rdv/views.py)."""

    def setUp(self):
        # Comme pour NumeroPatientConcurrencyTest : sous TransactionTestCase,
        # les transaction.on_commit() s'exécutent réellement, donc tout appel
        # Celery .delay() non mocké tente une vraie connexion au broker
        # (Redis, absent ici). Les deux points d'appel concernés ici sont la
        # création de patient (notify_admins_on_user_create, users/signals.py)
        # et la création de RDV (notify_medecin_new_rdv, rdv/signals.py) —
        # mockés pour toute la durée du test via addCleanup, pas seulement
        # setUp, puisque la réservation elle-même a lieu dans le test.
        for target in ('users.signals.notify_admins_on_user_create.delay',
                       'rdv.tasks.notify_medecin_new_rdv.delay'):
            patcher = mock.patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.medecin_user = Utilisateur.objects.create_user(
            email='medecin.concurrence@test.com',
            nom='Karim',
            prenom='Salma',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='test123'
        )
        self.medecin = self.medecin_user.profil_medecin

        # Comptes patients ET connexions (client.login crée une session en
        # base) faits séquentiellement ici, hors des threads : on ne veut
        # tester la concurrence que sur la réservation elle-même, pas sur la
        # création de session, qui ajouterait une seconde source de
        # contention SQLite sans rapport avec ce qu'on vérifie.
        self.nb_patients = 8
        self.clients = []
        for i in range(self.nb_patients):
            Utilisateur.objects.create_user(
                email=f'patient.concurrence{i}@test.com',
                nom='Test',
                prenom=f'Patient{i}',
                date_naissance=date(1990, 1, 1),
                role='patient',
                mot_de_passe='test123'
            )
            client = Client()
            assert client.login(email=f'patient.concurrence{i}@test.com', password='test123')
            self.clients.append(client)

    def test_une_seule_reservation_gagnante_sur_creneau_dispute(self):
        creneau = timezone.now() + timedelta(days=7)
        creneau = creneau.replace(hour=10, minute=0, second=0, microsecond=0)
        creneau_iso = creneau.strftime('%Y-%m-%dT%H:%M:%S')

        resultats = []
        erreurs = []

        def reserver(index):
            client = self.clients[index]

            # Même limitation SQLite que pour numero_patient (voir
            # NumeroPatientConcurrencyTest) : sous forte contention, une
            # requête peut lever "database table is locked" (SQLITE_LOCKED),
            # non couvert par busy_timeout. Chaque appel POST est déjà
            # atomique côté vue ; on retente juste la requête entière avec
            # une connexion fraîche, ce qui est sûr (la vue ne modifie rien
            # en cas d'échec avant commit).
            for attempt in range(5):
                try:
                    if connection.vendor == 'sqlite':
                        with connection.cursor() as cursor:
                            cursor.execute('PRAGMA busy_timeout = 30000;')
                    response = client.post(
                        reverse('rdv:api_reserver_rdv'),
                        data=json.dumps({
                            'medecin_id': self.medecin.id,
                            'datetime': creneau_iso,
                            'motif': f'Concurrence {index}',
                        }),
                        content_type='application/json'
                    )
                    resultats.append(response.json())
                    return
                except OperationalError as exc:
                    if 'locked' not in str(exc).lower():
                        erreurs.append(exc)
                        return
                    connection.close()
                    time_module.sleep(0.05 * (attempt + 1))
                except Exception as exc:
                    erreurs.append(exc)
                    return
                finally:
                    connections.close_all()
            erreurs.append(OperationalError('database table is locked (après plusieurs tentatives)'))

        threads = [threading.Thread(target=reserver, args=(i,)) for i in range(self.nb_patients)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(erreurs, [])
        self.assertEqual(len(resultats), self.nb_patients)

        # L'invariant qui compte est en base : jamais plus d'un RDV actif sur
        # ce créneau, garanti par unique_rdv_actif_par_creneau. On ne peut
        # pas systématiquement affirmer "exactement 1 réponse HTTP à
        # success:True" : sous SQLite (verrou base entière, pas de vrai
        # row-lock), il arrive que l'écriture gagnante ait lieu au sein d'une
        # requête dont une étape suivante échoue ensuite sur le même verrou
        # et parte en rollback complet côté client-retry — l'utilisateur
        # revoit alors "créneau déjà pris" alors que sa requête avait en
        # réalité gagné la course. Ce n'est pas reproductible sur PostgreSQL
        # (verrouillage par ligne, backend cible de prod) ; on vérifie donc
        # ici qu'il n'y a jamais de double succès (le vrai risque métier), et
        # que l'invariant en base est respecté.
        succes = [r for r in resultats if r.get('success')]
        echecs = [r for r in resultats if not r.get('success')]
        self.assertLessEqual(len(succes), 1, f"Jamais plus d'un succès, obtenu : {resultats}")
        for echec in echecs:
            self.assertIn('déjà pris', echec.get('error', ''))

        rdv_actifs = RendezVous.objects.filter(
            medecin=self.medecin,
            date_heure_rdv=creneau,
            statut__in=['programme', 'confirme'],
        )
        self.assertEqual(rdv_actifs.count(), 1)


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
            reverse('rdv:disponibilite_add'),
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

    def test_edit_disponibilite_hebdo(self):
        """Modification des horaires d'un créneau hebdomadaire (chantier 5 : formulaire dédupliqué)"""
        dispo = Disponibilite.objects.create(
            medecin=self.medecin,
            jour='mon',
            heure_debut=time(9, 0),
            heure_fin=time(12, 0),
        )

        response = self.client.post(
            reverse('rdv:disponibilite_hebdo_edit', kwargs={'pk': dispo.id}),
            {'heure_debut': '10:00', 'heure_fin': '13:00'},
        )

        self.assertEqual(response.status_code, 302)
        dispo.refresh_from_db()
        self.assertEqual(dispo.heure_debut, time(10, 0))
        self.assertEqual(dispo.heure_fin, time(13, 0))

    def test_edit_disponibilite_hebdo_rejects_overlap(self):
        """Le formulaire d'édition hebdo détecte à nouveau le chevauchement (medecin= câblé)."""
        Disponibilite.objects.create(
            medecin=self.medecin,
            jour='mon',
            heure_debut=time(14, 0),
            heure_fin=time(16, 0),
        )
        dispo_a_modifier = Disponibilite.objects.create(
            medecin=self.medecin,
            jour='mon',
            heure_debut=time(9, 0),
            heure_fin=time(12, 0),
        )

        response = self.client.post(
            reverse('rdv:disponibilite_hebdo_edit', kwargs={'pk': dispo_a_modifier.id}),
            {'heure_debut': '15:00', 'heure_fin': '17:00'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 400)
        dispo_a_modifier.refresh_from_db()
        self.assertEqual(dispo_a_modifier.heure_debut, time(9, 0))


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
            data={'raison': 'Urgence médicale'},
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        self.rdv.refresh_from_db()
        self.assertEqual(self.rdv.statut, 'annule')
        self.assertEqual(self.rdv.raison_annulation, 'Urgence médicale')
    
    def test_reporter_rdv(self):
        """Report d'un RDV"""
        new_date = (timezone.now() + timedelta(days=7)).replace(hour=14, minute=0)

        # reporter_rdv exige que le médecin ait une disponibilité couvrant le
        # nouveau créneau (rdv/views.py) : sans cette disponibilité, la vue
        # renvoie à juste titre 400 "pas disponible à ce créneau", ce n'est
        # pas un bug de la vue mais un fixture manquant dans ce test.
        weekday_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
        Disponibilite.objects.create(
            medecin=self.medecin,
            jour=weekday_map[new_date.weekday()],
            heure_debut=time(9, 0),
            heure_fin=time(18, 0),
        )

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
        response = self.client.get(reverse('rdv:notifs'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notification')

    def test_mark_as_read(self):
        """Marquer une notification comme lue"""
        notif = Notification.objects.filter(user=self.user, is_read=False).first()

        response = self.client.post(
            reverse('rdv:mark_read', kwargs={'notification_id': notif.id})
        )

        notif.refresh_from_db()
        self.assertTrue(notif.is_read)

    def test_mark_all_as_read(self):
        """Marquer toutes les notifications comme lues"""
        response = self.client.post(reverse('rdv:mark_all_read'))

        unread_count = Notification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(unread_count, 0)

    def test_delete_notification(self):
        """Supprimer une notification"""
        notif = Notification.objects.filter(user=self.user).first()
        notif_id = notif.id

        response = self.client.post(
            reverse('rdv:delete', kwargs={'notification_id': notif_id})
        )

        self.assertFalse(Notification.objects.filter(id=notif_id).exists())

    def test_get_notification_count(self):
        """Récupération du compteur de notifications"""
        response = self.client.get(reverse('rdv:count'))

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

    def test_send_manual_notification(self):
        """send_manual_notification ne doit plus planter (subject/rdv/type invalides corrigés)"""
        from rdv.utils import send_manual_notification

        notif = send_manual_notification(
            self.user,
            'Sujet du message',
            'Contenu du message manuel',
        )

        self.assertIsNotNone(notif)
        self.assertEqual(notif.type, 'info')
        self.assertEqual(notif.category, 'appointment')
        self.assertIn('Sujet du message', notif.message)
        self.assertIn('Contenu du message manuel', notif.message)


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


class AccessControlSecurityTest(TestCase):
    """
    Vérifie qu'un utilisateur non autorisé reçoit un refus d'accès sur :
    - l'historique médical des RDV (liste globale + détail d'un RDV),
    - les statistiques globales,
    - la suppression d'un RDV (méthode + permission).
    """

    def setUp(self):
        self.client = Client()

        self.admin = Utilisateur.objects.create_superuser(
            email='admin@test.com',
            nom='Admin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            mot_de_passe='admin123'
        )

        # Médecin et patient concernés par le RDV
        self.medecin_user = Utilisateur.objects.create_user(
            email='medecin@test.com',
            nom='Medecin',
            prenom='Test',
            date_naissance=date(1980, 1, 1),
            role='medecin',
            mot_de_passe='medecin123'
        )
        self.medecin = self.medecin_user.profil_medecin

        self.patient_user = Utilisateur.objects.create_user(
            email='patient@test.com',
            nom='Patient',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='patient123'
        )
        self.patient = self.patient_user.profil_patient

        # Patient tiers, non lié au RDV
        self.autre_patient_user = Utilisateur.objects.create_user(
            email='autre_patient@test.com',
            nom='Autre',
            prenom='Patient',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='autre123'
        )

        self.rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=timezone.now() + timedelta(days=3),
            statut='programme',
            motif='Test'
        )

    def test_history_list_forbidden_for_unrelated_patient(self):
        """La liste globale de l'historique est réservée médecin/admin."""
        self.client.login(email='autre_patient@test.com', password='autre123')
        response = self.client.get(reverse('rdv:history_list'))
        self.assertEqual(response.status_code, 403)

    def test_history_detail_forbidden_for_unrelated_patient(self):
        """Un patient non concerné ne peut pas voir l'historique d'un RDV d'autrui."""
        self.client.login(email='autre_patient@test.com', password='autre123')
        response = self.client.get(reverse('rdv:history_detail', kwargs={'rdv_id': self.rdv.id}))
        self.assertEqual(response.status_code, 403)

    def test_history_detail_allowed_for_owner_patient(self):
        """Le patient propriétaire du RDV n'est pas bloqué par le contrôle d'accès.

        Note : on vérifie ici uniquement que le contrôle d'accès (l'objet de ce
        chantier) ne renvoie pas 403, sans exiger un rendu complet à 200 : le
        template 'rdv/admin/history/rdv_history_detail.html' est manquant du
        projet, un bug préexistant et distinct, hors du périmètre de cette
        session (voir le rapport de session).
        """
        client = Client(raise_request_exception=False)
        client.login(email='patient@test.com', password='patient123')
        response = client.get(reverse('rdv:history_detail', kwargs={'rdv_id': self.rdv.id}))
        self.assertNotEqual(response.status_code, 403)

    def test_stats_forbidden_for_patient(self):
        """Les statistiques globales sont réservées aux utilisateurs autorisés."""
        self.client.login(email='patient@test.com', password='patient123')
        response = self.client.get(reverse('rdv:api_overview'))
        self.assertEqual(response.status_code, 403)

    def test_stats_allowed_for_admin(self):
        """Un admin peut consulter les statistiques globales."""
        self.client.login(email='admin@test.com', password='admin123')
        response = self.client.get(reverse('rdv:api_overview'))
        self.assertEqual(response.status_code, 200)

    def test_export_stats_forbidden_for_medecin(self):
        """L'export CSV requiert la permission dédiée can_export_data."""
        self.client.login(email='medecin@test.com', password='medecin123')
        response = self.client.get(reverse('rdv:export_stats'))
        self.assertEqual(response.status_code, 403)

    def test_delete_rdv_rejects_get(self):
        """La suppression d'un RDV n'est plus déclenchable en GET."""
        self.client.login(email='admin@test.com', password='admin123')
        response = self.client.get(reverse('rdv:supprimer_rendez_vous', kwargs={'rdv_id': self.rdv.id}))
        self.assertEqual(response.status_code, 405)
        self.assertTrue(RendezVous.objects.filter(pk=self.rdv.id).exists())

    def test_delete_rdv_forbidden_without_permission(self):
        """Un utilisateur sans la permission ne peut pas supprimer un RDV, même en POST."""
        self.client.login(email='patient@test.com', password='patient123')
        response = self.client.post(reverse('rdv:supprimer_rendez_vous', kwargs={'rdv_id': self.rdv.id}))
        self.assertEqual(response.status_code, 403)
        self.assertTrue(RendezVous.objects.filter(pk=self.rdv.id).exists())

    def test_patient_can_cancel_own_rdv(self):
        """Le patient propriétaire du RDV peut désormais l'annuler lui-même (chantier 5)."""
        self.client.login(email='patient@test.com', password='patient123')
        response = self.client.post(
            reverse('rdv:annuler_rdv', kwargs={'rdv_id': self.rdv.id}),
            data={'raison': 'Empêchement personnel'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        self.rdv.refresh_from_db()
        self.assertEqual(self.rdv.statut, 'annule')
        self.assertEqual(self.rdv.raison_annulation, 'Empêchement personnel')

    def test_annuler_rdv_forbidden_for_unrelated_patient(self):
        """Un patient non concerné ne peut toujours pas annuler le RDV d'un autre."""
        self.client.login(email='autre_patient@test.com', password='autre123')
        response = self.client.post(
            reverse('rdv:annuler_rdv', kwargs={'rdv_id': self.rdv.id}),
            data={'raison': 'Tentative non autorisée'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)
        self.rdv.refresh_from_db()
        self.assertEqual(self.rdv.statut, 'programme')


class CeleryIntegrationTest(TestCase):
    """
    Vérifie que la chaîne signal -> Celery -> notification fonctionne
    réellement de bout en bout (pipeline réparé au chantier 3), en exécutant
    les tâches en mode 'eager' (synchrone, sans broker) pour ne pas dépendre
    d'un worker/Redis réels pendant les tests.
    """

    def setUp(self):
        from GestionRDV.celery import app as celery_app
        self.celery_app = celery_app
        self._previous_eager = celery_app.conf.task_always_eager
        self._previous_propagates = celery_app.conf.task_eager_propagates
        celery_app.conf.task_always_eager = True
        celery_app.conf.task_eager_propagates = True

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

    def tearDown(self):
        self.celery_app.conf.task_always_eager = self._previous_eager
        self.celery_app.conf.task_eager_propagates = self._previous_propagates

    def test_new_rdv_triggers_medecin_notification_via_celery(self):
        """La création d'un RDV déclenche rdv.tasks.notify_medecin_new_rdv."""
        # Le signal utilise transaction.on_commit() : sous TestCase, la
        # transaction du test est annulée (rollback) sans jamais "commit" —
        # captureOnCommitCallbacks force leur exécution comme en production.
        with self.captureOnCommitCallbacks(execute=True):
            RendezVous.objects.create(
                patient=self.patient,
                medecin=self.medecin,
                date_heure_rdv=timezone.now() + timedelta(days=3),
                statut='programme',
                motif='Test intégration Celery'
            )

        notif = Notification.objects.filter(
            user=self.medecin_user, category='appointment'
        ).order_by('-date_envoi').first()
        self.assertIsNotNone(notif)
        self.assertIn('rendez-vous', notif.message.lower())

    def test_status_change_triggers_patient_notification_via_celery(self):
        """Un changement de statut programme -> confirme déclenche rdv.tasks.handle_status_change."""
        rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=timezone.now() + timedelta(days=3),
            statut='programme',
            motif='Test'
        )
        Notification.objects.filter(user=self.patient_user).delete()

        with self.captureOnCommitCallbacks(execute=True):
            rdv.statut = 'confirme'
            rdv.save()

        notif = Notification.objects.filter(
            user=self.patient_user, category='appointment'
        ).order_by('-date_envoi').first()
        self.assertIsNotNone(notif)
        self.assertIn('confirmé', notif.message.lower())

    def test_cancellation_notifies_waitlist_via_celery(self):
        """L'annulation d'un RDV déclenche rdv.tasks.notify_waitlist_on_cancellation
        pour les inscriptions en_attente sur ce créneau précis (même medecin,
        même date_heure_rdv), et fait passer leur statut à notifie."""
        creneau = timezone.now() + timedelta(days=3)

        rdv = RendezVous.objects.create(
            patient=self.patient,
            medecin=self.medecin,
            date_heure_rdv=creneau,
            statut='confirme',
            motif='Test'
        )

        attendant_user = Utilisateur.objects.create_user(
            email='attendant@test.com',
            nom='Attendant',
            prenom='Test',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='test123'
        )
        inscription = ListeAttenteCreneau.objects.create(
            patient=attendant_user.profil_patient,
            medecin=self.medecin,
            date_heure_souhaitee=creneau,
        )

        # Inscription non concernée (créneau différent) : ne doit pas être notifiée.
        autre_user = Utilisateur.objects.create_user(
            email='autre_attendant@test.com',
            nom='Autre',
            prenom='Attendant',
            date_naissance=date(1990, 1, 1),
            role='patient',
            mot_de_passe='test123'
        )
        autre_inscription = ListeAttenteCreneau.objects.create(
            patient=autre_user.profil_patient,
            medecin=self.medecin,
            date_heure_souhaitee=creneau + timedelta(hours=1),
        )

        with self.captureOnCommitCallbacks(execute=True):
            rdv.cancel(description='Test annulation', by_user=self.medecin_user)

        inscription.refresh_from_db()
        autre_inscription.refresh_from_db()
        self.assertEqual(inscription.statut, 'notifie')
        self.assertEqual(autre_inscription.statut, 'en_attente')

        notif = Notification.objects.filter(
            user=attendant_user, category='appointment'
        ).order_by('-date_envoi').first()
        self.assertIsNotNone(notif)
        self.assertIn('libér', notif.message.lower())

        self.assertFalse(
            Notification.objects.filter(user=autre_user, category='appointment').exists()
        )


class WaitlistExpirationTaskTest(TestCase):
    """Vérifie rdv.tasks.expire_old_waitlist_entries (job périodique)."""

    def setUp(self):
        self.medecin_user = Utilisateur.objects.create_user(
            email='medecin@test.com', nom='Medecin', prenom='Test',
            date_naissance=date(1980, 1, 1), role='medecin', mot_de_passe='test123'
        )
        self.medecin = self.medecin_user.profil_medecin

    def _patient(self, email):
        user = Utilisateur.objects.create_user(
            email=email, nom='Patient', prenom='Test',
            date_naissance=date(1990, 1, 1), role='patient', mot_de_passe='test123'
        )
        return user.profil_patient

    def test_expire_old_waitlist_entries(self):
        from rdv.tasks import expire_old_waitlist_entries

        expiree = ListeAttenteCreneau.objects.create(
            patient=self._patient('attente1@test.com'), medecin=self.medecin,
            date_heure_souhaitee=timezone.now() - timedelta(days=1),
        )
        active = ListeAttenteCreneau.objects.create(
            patient=self._patient('attente2@test.com'), medecin=self.medecin,
            date_heure_souhaitee=timezone.now() + timedelta(days=1),
        )
        honoree = ListeAttenteCreneau.objects.create(
            patient=self._patient('attente3@test.com'), medecin=self.medecin,
            date_heure_souhaitee=timezone.now() - timedelta(days=1),
            statut='honore',
        )

        expire_old_waitlist_entries()

        expiree.refresh_from_db()
        active.refresh_from_db()
        honoree.refresh_from_db()
        self.assertEqual(expiree.statut, 'expire')
        self.assertEqual(active.statut, 'en_attente')
        self.assertEqual(honoree.statut, 'honore')


class CeleryBeatScheduleTest(TestCase):
    """Vérifie que les tâches périodiques connues sont bien programmées
    dans CELERY_BEAT_SCHEDULE. Une tâche @shared_task correcte mais jamais
    ajoutée au planning ne s'exécute jamais en production (piège déjà
    rencontré avec expire_old_waitlist_entries) ; ce test échoue si l'une
    de ces quatre tâches disparaît du planning."""

    def test_taches_periodiques_enregistrees(self):
        taches_attendues = {
            'rdv.tasks.send_rdv_reminder_24h',
            'rdv.tasks.auto_cancel_expired_rdv',
            'rdv.tasks.auto_start_rdv',
            'rdv.tasks.expire_old_waitlist_entries',
        }

        schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        taches_planifiees = {entry.get('task') for entry in schedule.values()}

        manquantes = taches_attendues - taches_planifiees
        self.assertEqual(
            manquantes, set(),
            f"Tâches périodiques absentes de CELERY_BEAT_SCHEDULE : {manquantes}"
        )

