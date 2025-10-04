# rdv/management/commands/generate_report.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from rdv.models import RendezVous, Notification, Patient, Medecin
from users.models import Utilisateur
import json


class Command(BaseCommand):
    help = 'Génère un rapport détaillé de l\'activité du système'

    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            type=str,
            default='week',
            choices=['day', 'week', 'month', 'year'],
            help='Période du rapport'
        )
        parser.add_argument(
            '--format',
            type=str,
            default='text',
            choices=['text', 'json'],
            help='Format de sortie'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Fichier de sortie (optionnel)'
        )

    def get_date_range(self, period):
        """Calcule la plage de dates selon la période"""
        now = timezone.now()
        
        if period == 'day':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            label = "aujourd'hui"
        elif period == 'week':
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            label = "cette semaine"
        elif period == 'month':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            label = "ce mois"
        else:  # year
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            label = "cette année"
        
        return start, now, label

    def collect_data(self, start_date, end_date):
        """Collecte toutes les données nécessaires"""
        
        # RDV
        rdv_data = {
            'total': RendezVous.objects.filter(date_creation__range=(start_date, end_date)).count(),
            'par_statut': dict(
                RendezVous.objects.filter(
                    date_creation__range=(start_date, end_date)
                ).values('statut').annotate(count=Count('id')).values_list('statut', 'count')
            ),
            'annules': RendezVous.objects.filter(
                statut='annule',
                date_modification__range=(start_date, end_date)
            ).count(),
        }
        
        # Calcul taux d'annulation
        if rdv_data['total'] > 0:
            rdv_data['taux_annulation'] = round((rdv_data['annules'] / rdv_data['total']) * 100, 2)
        else:
            rdv_data['taux_annulation'] = 0
        
        # Top médecins
        rdv_data['top_medecins'] = list(
            RendezVous.objects.filter(
                date_creation__range=(start_date, end_date)
            ).values(
                'medecin__user__nom',
                'medecin__user__prenom'
            ).annotate(
                total=Count('id')
            ).order_by('-total')[:5]
        )
        
        # Patients
        patient_data = {
            'nouveaux': Utilisateur.objects.filter(
                role='patient',
                date_inscription__range=(start_date, end_date)
            ).count(),
            'total': Patient.objects.count(),
            'actifs': Utilisateur.objects.filter(
                role='patient',
                is_actif=True,
                profil_patient__rendez_vous__date_creation__range=(start_date, end_date)
            ).distinct().count(),
        }
        
        # Notifications
        notif_data = {
            'envoyees': Notification.objects.filter(
                date_envoi__range=(start_date, end_date)
            ).count(),
            'lues': Notification.objects.filter(
                date_envoi__range=(start_date, end_date),
                is_read=True
            ).count(),
            'par_type': dict(
                Notification.objects.filter(
                    date_envoi__range=(start_date, end_date)
                ).values('type').annotate(count=Count('id')).values_list('type', 'count')
            ),
        }
        
        # Taux de lecture
        if notif_data['envoyees'] > 0:
            notif_data['taux_lecture'] = round((notif_data['lues'] / notif_data['envoyees']) * 100, 2)
        else:
            notif_data['taux_lecture'] = 0
        
        # Médecins
        medecin_data = {
            'total': Medecin.objects.count(),
            'actifs': Medecin.objects.filter(
                accepte_nouveaux_patients=True
            ).count(),
            'par_specialite': dict(
                Medecin.objects.values('specialite').annotate(
                    count=Count('id')
                ).values_list('specialite', 'count')
            ),
        }
        
        return {
            'rdv': rdv_data,
            'patients': patient_data,
            'notifications': notif_data,
            'medecins': medecin_data,
            'periode': {
                'debut': start_date.isoformat(),
                'fin': end_date.isoformat(),
            }
        }

    def format_text_report(self, data, period_label):
        """Formate le rapport en texte"""
        lines = []
        lines.append("\n" + "="*80)
        lines.append("  RAPPORT D'ACTIVITÉ - SYSTÈME DE GESTION RDV")
        lines.append("="*80)
        lines.append(f"Période : {period_label}")
        lines.append(f"Généré le : {timezone.now().strftime('%d/%m/%Y à %H:%M')}")
        lines.append("="*80 + "\n")
        
        # RDV
        lines.append("📅 RENDEZ-VOUS")
        lines.append("-" * 80)
        lines.append(f"Total RDV créés : {data['rdv']['total']}")
        lines.append(f"Taux d'annulation : {data['rdv']['taux_annulation']}%")
        lines.append("\nRépartition par statut :")
        for statut, count in data['rdv']['par_statut'].items():
            lines.append(f"  • {statut} : {count}")
        
        if data['rdv']['top_medecins']:
            lines.append("\nTop 5 médecins (par nombre de RDV) :")
            for i, med in enumerate(data['rdv']['top_medecins'], 1):
                nom = f"{med['medecin__user__prenom']} {med['medecin__user__nom']}"
                lines.append(f"  {i}. Dr. {nom} : {med['total']} RDV")
        
        lines.append("\n")
        
        # Patients
        lines.append("👥 PATIENTS")
        lines.append("-" * 80)
        lines.append(f"Total patients : {data['patients']['total']}")
        lines.append(f"Nouveaux patients : {data['patients']['nouveaux']}")
        lines.append(f"Patients actifs : {data['patients']['actifs']}")
        lines.append("\n")
        
        # Notifications
        lines.append("🔔 NOTIFICATIONS")
        lines.append("-" * 80)
        lines.append(f"Notifications envoyées : {data['notifications']['envoyees']}")
        lines.append(f"Taux de lecture : {data['notifications']['taux_lecture']}%")
        lines.append("\nRépartition par type :")
        for type_notif, count in data['notifications']['par_type'].items():
            lines.append(f"  • {type_notif} : {count}")
        lines.append("\n")
        
        # Médecins
        lines.append("⚕️ MÉDECINS")
        lines.append("-" * 80)
        lines.append(f"Total médecins : {data['medecins']['total']}")
        lines.append(f"Médecins actifs : {data['medecins']['actifs']}")
        lines.append("\nRépartition par spécialité :")
        for spec, count in data['medecins']['par_specialite'].items():
            lines.append(f"  • {spec} : {count}")
        
        lines.append("\n" + "="*80 + "\n")
        
        return "\n".join(lines)

    def format_json_report(self, data):
        """Formate le rapport en JSON"""
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    def handle(self, *args, **options):
        period = options['period']
        format_type = options['format']
        output_file = options['output']
        
        # Calculer les dates
        start_date, end_date, period_label = self.get_date_range(period)
        
        self.stdout.write(
            self.style.SUCCESS(f'\nGénération du rapport pour {period_label}...\n')
        )
        
        # Collecter les données
        data = self.collect_data(start_date, end_date)
        
        # Formater le rapport
        if format_type == 'json':
            report = self.format_json_report(data)
        else:
            report = self.format_text_report(data, period_label)
        
        # Sauvegarder ou afficher
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            self.stdout.write(
                self.style.SUCCESS(f'Rapport sauvegardé dans : {output_file}\n')
            )
        else:
            self.stdout.write(report)
        
        # Résumé
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Rapport généré avec succès\n'
                f'  - {data["rdv"]["total"]} RDV créés\n'
                f'  - {data["patients"]["nouveaux"]} nouveaux patients\n'
                f'  - {data["notifications"]["envoyees"]} notifications envoyées\n'
            )
        )