from django.core.management.base import BaseCommand
from users.models import Utilisateur
from rdv.models import Patient, Medecin
from datetime import datetime

class Command(BaseCommand):
    help = 'Insère les utilisateurs tchadiens (patients et médecins)'

    def handle(self, *args, **kwargs):
        # Données des patients
        patients_data = [
            {"email": "aminata.idriss@tchad.td", "nom": "Idriss", "prenom": "Aminata", "telephone": "235650000001", "role": "patient", "date_naissance": "1988-03-10", "sexe": "F", "adresse": "N'Djamena, Quartier Diguel Est", "numero_patient": "PAT000001", "password": "Dk8!fLm2Px#"},
            {"email": "fatima.brahim@tchad.td", "nom": "Brahim", "prenom": "Fatima", "telephone": "235650000002", "role": "patient", "date_naissance": "1979-11-23", "sexe": "F", "adresse": "N'Djamena, Rue principale", "numero_patient": "PAT000002", "password": "Mx7$BvQ8jw"},
            {"email": "salma.karim@tchad.td", "nom": "Karim", "prenom": "Salma", "telephone": "235650000003", "role": "patient", "date_naissance": "1985-05-19", "sexe": "F", "adresse": "N'Djamena, Zone 4", "numero_patient": "PAT000003", "password": "H9cWyVz4Lp"},
            {"email": "zahra.hassan@tchad.td", "nom": "Hassan", "prenom": "Zahra", "telephone": "235650000004", "role": "patient", "date_naissance": "1998-09-08", "sexe": "F", "adresse": "N'Djamena, Centre-ville", "numero_patient": "PAT000004", "password": "R3$SkLz7Bq"},
            {"email": "amina.fall@tchad.td", "nom": "Fall", "prenom": "Amina", "telephone": "235650000005", "role": "patient", "date_naissance": "1987-06-25", "sexe": "F", "adresse": "N'Djamena, Quartier Ndjari", "numero_patient": "PAT000005", "password": "Gx1!NzHpK2"},
            {"email": "rania.djado@tchad.td", "nom": "Djado", "prenom": "Rania", "telephone": "235650000006", "role": "patient", "date_naissance": "2001-08-28", "sexe": "F", "adresse": "N'Djamena, Quartier Argouboua", "numero_patient": "PAT000006", "password": "Yt6&WfjLpZ"},
            {"email": "aicha.douba@tchad.td", "nom": "Douba", "prenom": "Aicha", "telephone": "235650000007", "role": "patient", "date_naissance": "1982-07-13", "sexe": "F", "adresse": "N'Djamena, Farcha", "numero_patient": "PAT000007", "password": "V$edP2CmjN"},
            {"email": "miriam.galid@tchad.td", "nom": "Galid", "prenom": "Miriam", "telephone": "235650000008", "role": "patient", "date_naissance": "1989-03-16", "sexe": "F", "adresse": "N'Djamena, Zone 3", "numero_patient": "PAT000008", "password": "Lf74!QwcXp"},
            {"email": "sana.youssouf@tchad.td", "nom": "Youssouf", "prenom": "Sana", "telephone": "235650000009", "role": "patient", "date_naissance": "1996-06-07", "sexe": "F", "adresse": "N'Djamena, Quartier Bebedjia", "numero_patient": "PAT000009", "password": "Tx#Wp3MvZk"},
            {"email": "halima.baba@tchad.td", "nom": "Baba", "prenom": "Halima", "telephone": "235650000010", "role": "patient", "date_naissance": "1991-09-03", "sexe": "F", "adresse": "N'Djamena, Quartier Kim", "numero_patient": "PAT000010", "password": "Aq8$DsJvMz"},
            {"email": "aminata.kone@tchad.td", "nom": "Koné", "prenom": "Aminata", "telephone": "235650000011", "role": "patient", "date_naissance": "1983-04-11", "sexe": "F", "adresse": "N'Djamena, Quartier Cité de l'Air", "numero_patient": "PAT000011", "password": "Bd6!XrmCtP"},
            {"email": "mariam.kalamat@tchad.td", "nom": "Kalamat", "prenom": "Mariam", "telephone": "235650000012", "role": "patient", "date_naissance": "1990-11-20", "sexe": "F", "adresse": "N'Djamena, Secteur 5", "numero_patient": "PAT000012", "password": "C9$nVzYwLp"},
            {"email": "fatouma.bakari@tchad.td", "nom": "Bakari", "prenom": "Fatouma", "telephone": "235650000013", "role": "patient", "date_naissance": "1986-08-02", "sexe": "F", "adresse": "N'Djamena, Quartier Komé", "numero_patient": "PAT000013", "password": "Hw7!TqXvpL"},
            {"email": "chadia.ali@tchad.td", "nom": "Ali", "prenom": "Chadia", "telephone": "235650000014", "role": "patient", "date_naissance": "1997-05-25", "sexe": "F", "adresse": "N'Djamena, Quartier Kabalaye", "numero_patient": "PAT000014", "password": "Mv3$NpLWtx"},
            {"email": "assia.tamim@tchad.td", "nom": "Tamim", "prenom": "Assia", "telephone": "235650000015", "role": "patient", "date_naissance": "1995-12-30", "sexe": "F", "adresse": "N'Djamena, Quartier Mkolo", "numero_patient": "PAT000015", "password": "Xj9!DsJbwL"},
            {"email": "laila.djimadoum@tchad.td", "nom": "Djimadoum", "prenom": "Laila", "telephone": "235650000016", "role": "patient", "date_naissance": "2000-07-17", "sexe": "F", "adresse": "N'Djamena, Quartier Habena", "numero_patient": "PAT000016", "password": "Pw4$MvCXkt"},
            {"email": "imane.alim@tchad.td", "nom": "Alim", "prenom": "Imane", "telephone": "235650000017", "role": "patient", "date_naissance": "1988-02-23", "sexe": "F", "adresse": "N'Djamena, Quartier Moursal", "numero_patient": "PAT000017", "password": "Vx5!BpnMcz"},
            {"email": "khadidja.karim@tchad.td", "nom": "Karim", "prenom": "Khadidja", "telephone": "235650000018", "role": "patient", "date_naissance": "1992-06-14", "sexe": "F", "adresse": "N'Djamena, Quartier Kasra", "numero_patient": "PAT000018", "password": "Lt2$WvjXpM"},
            {"email": "asma.djibrine@tchad.td", "nom": "Djibrine", "prenom": "Asma", "telephone": "235650000019", "role": "patient", "date_naissance": "1994-10-29", "sexe": "F", "adresse": "N'Djamena, Quartier Raisman", "numero_patient": "PAT000019", "password": "Rz7!FpnYxL"},
            {"email": "sabrina.hassane@tchad.td", "nom": "Hassane", "prenom": "Sabrina", "telephone": "235650000020", "role": "patient", "date_naissance": "1987-09-07", "sexe": "F", "adresse": "N'Djamena, Quartier Ngueli", "numero_patient": "PAT000020", "password": "Nk3$VtzLpW"},
        ]

        # Données des médecins
        medecins_data = [
            {"email": "dr.karim.abakar@tchad.td", "nom": "Abakar", "prenom": "Karim", "telephone": "235660000001", "role": "medecin", "date_naissance": "1980-01-15", "specialite": "generaliste", "cabinet": "Clinique N'Djamena", "adresse_cabinet": "N'Djamena, Quartier Farcha", "sexe": "M", "diplomes": "Diplôme médecine générale", "password": "Ev9!KzWpMx"},
            {"email": "dr.mariam.saleh@tchad.td", "nom": "Saleh", "prenom": "Mariam", "telephone": "235660000002", "role": "medecin", "date_naissance": "1985-03-20", "specialite": "pediatre", "cabinet": "Centre Médical N'Djamena", "adresse_cabinet": "N'Djamena, Quartier Diguel", "sexe": "F", "diplomes": "Diplôme pédiatrie", "password": "Fj8#YtvWqNz"},
            {"email": "dr.zahra.hassan@tchad.td", "nom": "Hassan", "prenom": "Zahra", "telephone": "235660000003", "role": "medecin", "date_naissance": "1982-06-10", "specialite": "gynecologue", "cabinet": "Centre de Santé N'Djamena", "adresse_cabinet": "N'Djamena, Quartier Farcha", "sexe": "F", "diplomes": "Diplôme gynécologie", "password": "Pw3$QmzHxLn"},
            {"email": "dr.amina.salah@tchad.td", "nom": "Salah", "prenom": "Amina", "telephone": "235660000004", "role": "medecin", "date_naissance": "1983-08-25", "specialite": "dermatologue", "cabinet": "Hôpital N'Djamena", "adresse_cabinet": "N'Djamena, Quartier Bebedjia", "sexe": "F", "diplomes": "Diplôme dermatologie", "password": "Rv4!JpkCwtM"},
            {"email": "dr.yahya.talal@tchad.td", "nom": "Talal", "prenom": "Yahya", "telephone": "235660000005", "role": "medecin", "date_naissance": "1978-11-30", "specialite": "ophtalmologue", "cabinet": "Centre Ophtalmologique", "adresse_cabinet": "N'Djamena, Rue Kalthoum", "sexe": "M", "diplomes": "Diplôme ophtalmologie", "password": "Tx7#VkmLnWp"},
            {"email": "dr.fadel.djigo@tchad.td", "nom": "Djigo", "prenom": "Fadel", "telephone": "235660000006", "role": "medecin", "date_naissance": "1981-04-18", "specialite": "cardiologue", "cabinet": "Clinique Fadel", "adresse_cabinet": "N'Djamena, Quartier Farcha", "sexe": "M", "diplomes": "Diplôme cardiologie", "password": "Lb1!SqvMXtn"},
            {"email": "dr.salma.karim@tchad.td", "nom": "Karim", "prenom": "Salma", "telephone": "235660000007", "role": "medecin", "date_naissance": "1984-09-05", "specialite": "orl", "cabinet": "Hôpital Moursal", "adresse_cabinet": "N'Djamena, Quartier Moursal", "sexe": "F", "diplomes": "Diplôme ORL", "password": "Gv6#WlPqZxm"},
            {"email": "dr.rania.fall@tchad.td", "nom": "Fall", "prenom": "Rania", "telephone": "235660000008", "role": "medecin", "date_naissance": "1986-02-14", "specialite": "orthopediste", "cabinet": "Clinique Sarh", "adresse_cabinet": "N'Djamena, Boulevard Principal", "sexe": "F", "diplomes": "Diplôme orthopédie", "password": "Dn2!VjKTpx"},
            {"email": "dr.mustapha.djibril@tchad.td", "nom": "Djibril", "prenom": "Mustapha", "telephone": "235660000009", "role": "medecin", "date_naissance": "1979-07-22", "specialite": "neurologue", "cabinet": "Clinique Moundou", "adresse_cabinet": "N'Djamena, Zone 2", "sexe": "M", "diplomes": "Diplôme neurologie", "password": "Xk9#NrvLqZp"},
            {"email": "dr.bakari.odah@tchad.td", "nom": "Odah", "prenom": "Bakari", "telephone": "235660000010", "role": "medecin", "date_naissance": "1980-12-08", "specialite": "psychiatre", "cabinet": "Centre Psychiatrique", "adresse_cabinet": "N'Djamena, Quartier Kilo", "sexe": "M", "diplomes": "Diplôme psychiatrie", "password": "Zj4!PxsMlVt"},
        ]

        self.stdout.write(self.style.WARNING("\n Début de l'insertion des utilisateurs...\n"))

        # Insertion des patients
        self.stdout.write(self.style.NOTICE("Insertion des patients..."))
        patients_created = 0
        patients_skipped = 0

        for patient_data in patients_data:
            try:
                if Utilisateur.objects.filter(email=patient_data['email']).exists():
                    self.stdout.write(self.style.WARNING(f"  Patient existe déjà: {patient_data['email']}"))
                    patients_skipped += 1
                    continue

                # Créer l'utilisateur - le signal créera automatiquement le profil Patient
                user = Utilisateur.objects.create_user(
                    email=patient_data['email'],
                    nom=patient_data['nom'],
                    prenom=patient_data['prenom'],
                    date_naissance=datetime.strptime(patient_data['date_naissance'], '%Y-%m-%d').date(),
                    mot_de_passe=patient_data['password'],
                    telephone=patient_data['telephone'],
                    role='patient',
                    is_actif=True
                )

                # Mettre à jour le profil Patient créé par le signal
                patient_profile = Patient.objects.get(user=user)
                patient_profile.numero_patient = patient_data['numero_patient']
                patient_profile.adresse = patient_data['adresse']
                patient_profile.sexe = patient_data['sexe']
                patient_profile.save()

                patients_created += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Patient créé: {patient_data['prenom']} {patient_data['nom']} ({patient_data['numero_patient']})"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Erreur pour {patient_data['email']}: {str(e)}"))

        # Insertion des médecins
        self.stdout.write(self.style.NOTICE("\n Insertion des médecins..."))
        medecins_created = 0
        medecins_skipped = 0

        for medecin_data in medecins_data:
            try:
                if Utilisateur.objects.filter(email=medecin_data['email']).exists():
                    self.stdout.write(self.style.WARNING(f"  Médecin existe déjà: {medecin_data['email']}"))
                    medecins_skipped += 1
                    continue

                # Créer l'utilisateur - le signal créera automatiquement le profil Medecin
                user = Utilisateur.objects.create_user(
                    email=medecin_data['email'],
                    nom=medecin_data['nom'],
                    prenom=medecin_data['prenom'],
                    date_naissance=datetime.strptime(medecin_data['date_naissance'], '%Y-%m-%d').date(),
                    mot_de_passe=medecin_data['password'],
                    telephone=medecin_data['telephone'],
                    role='medecin',
                    is_actif=True
                )

                # Mettre à jour le profil Medecin créé par le signal
                medecin_profile = Medecin.objects.get(user=user)
                medecin_profile.specialite = medecin_data['specialite']
                medecin_profile.cabinet = medecin_data['cabinet']
                medecin_profile.adresse_cabinet = medecin_data['adresse_cabinet']
                medecin_profile.sexe = medecin_data['sexe']
                medecin_profile.diplomes = medecin_data['diplomes']
                medecin_profile.save()

                medecins_created += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ Médecin créé: Dr. {medecin_data['prenom']} {medecin_data['nom']} ({medecin_data['specialite']})"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Erreur pour {medecin_data['email']}: {str(e)}"))

        # Résumé
        self.stdout.write(self.style.SUCCESS(f"\n{'='*60}"))
        self.stdout.write(self.style.SUCCESS(f" INSERTION TERMINÉE !"))
        self.stdout.write(self.style.SUCCESS(f"{'='*60}"))
        self.stdout.write(self.style.SUCCESS(f"Patients créés: {patients_created}"))
        self.stdout.write(self.style.WARNING(f"Patients ignorés: {patients_skipped}"))
        self.stdout.write(self.style.SUCCESS(f"Médecins créés: {medecins_created}"))
        self.stdout.write(self.style.WARNING(f"Médecins ignorés: {medecins_skipped}"))
        self.stdout.write(self.style.SUCCESS(f"{'='*60}\n"))