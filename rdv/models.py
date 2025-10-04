from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.timesince import timesince
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from django.utils import timezone
from django.db.models import Q, UniqueConstraint
import logging

logger = logging.getLogger(__name__)


class RdvHistory(models.Model):
    ACTION_CHOICES = [
        ('create', 'Création'),
        ('confirm', 'Confirmation'),
        ('cancel', 'Annulation'),
        ('report', 'Report'),
        ('update', 'Mise à jour'),
        ('delete', 'Suppression'),
    ]

    rdv = models.ForeignKey('RendezVous', on_delete=models.CASCADE, related_name='history')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='rdv_actions')
    timestamp = models.DateTimeField(auto_now_add=True)
    # stocker les valeurs utiles pour audit (ancienne / nouvelle date, ancien statut etc.)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)  # plus long que 255
    extra = models.JSONField(blank=True, null=True, default=dict)  # info structurable (optionnel)

    class Meta:
        verbose_name = "Historique RDV"
        verbose_name_plural = "Historique RDV"
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] RDV#{self.rdv_id} {self.get_action_display()} par {self.performed_by or 'système'}"



class Patient(models.Model):
    user =  models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profil_patient')
    numero_patient = models.CharField(max_length=20, unique=True, blank=True)
    date_naissance = models.DateField(verbose_name="Date de naissance")
    adresse = models.TextField(blank=True)
    sexe = models.CharField(max_length=10, choices=[('F', 'Féminin'), ('M', 'Masculin')], default='F')
    tel = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(regex=r'^\+?[0-9\s\-\(\)]+$', message="Numéro de téléphone invalide")]
    )
    photo = models.ImageField(upload_to='patients/', blank=True, null=True)


    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = "Patients"

    def __str__(self):
        return f"{self.user.__str__()}"
    
    def save(self, *args, **kwargs):
        if not self.numero_patient:
            # Générer un numéro de patient automatique
            last_patient = Patient.objects.order_by('-id').first()
            if last_patient:
                last_num = int(last_patient.numero_patient.split('-')[-1])
                self.numero_patient = f"PAT-{last_num + 1:06d}"
            else:
                self.numero_patient = "PAT-000001"
        super().save(*args, **kwargs)

    
class Medecin(models.Model):
    SPECIALITES = [
        ('generaliste', 'Médecin Généraliste'),
        ('cardiologue', 'Cardiologue'),
        ('dermatologue', 'Dermatologue'),
        ('pediatre', 'Pédiatre'),
        ('gynecologue', 'Gynécologue'),
        ('neurologue', 'Neurologue'),
        ('psychiatre', 'Psychiatre'),
        ('orthopediste', 'Orthopédiste'),
        ('ophtalmologue', 'Ophtalmologue'),
        ('orl', 'ORL'),
    ]

    user =  models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profil_medecin')
    numero_order = models.CharField(max_length=20, blank=True)
    date_naissance = models.DateField(verbose_name="Date de naissance")
    specialite = models.CharField(max_length=100, choices=SPECIALITES)
    cabinet = models.CharField(max_length=200, blank=True)
    adresse_cabinet = models.TextField(blank=True)
    tel = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r'^\+?[0-9\s\-\(\)]+$', message="Numéro de téléphone invalide")]
    )
    sexe = models.CharField(max_length=10, choices=[('F', 'Féminin'), ('M', 'Masculin')], default='F')
    diplomes = models.TextField(blank=True)
    photo = models.ImageField(upload_to='medecins/', blank=True, null=True)
    tarif_consultation = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    langues_parlees = models.CharField(max_length=200, blank=True, help_text="Ex: Français, Anglais, Arabe")
    accepte_nouveaux_patients = models.BooleanField(default=True)
    delai_moyen_rdv = models.IntegerField(null=True, blank=True, help_text="En jours")
    
    class Meta:
        verbose_name = "Médecin"
        verbose_name_plural = "Médecins"

    def __str__(self):
        return f"Dr. {self.user.nom_complet()} - {self.specialite}"
    
    @property
    def prochaine_disponibilite(self):
        """Retourne le prochain créneau disponible"""
        now = timezone.now()
        # Créneaux hebdomadaires
        dispos = self.disponibilites.filter(
            is_active=True,
            date_specific__isnull=True
        ).order_by('jour', 'heure_debut')

        for dispo in dispos:
            # Convertir en date réelle et vérifier si pas déjà pris
            slots = dispo.get_slot_datetimes()
            for start, end in slots:
                # S'assurer que start est aware
                if timezone.is_naive(start):
                    start = timezone.make_aware(start, timezone.get_current_timezone())

                if start > now:
                    # Vérifier si créneau libre
                    if not RendezVous.objects.filter(
                        medecin=self,
                        date_heure_rdv=start,
                        statut__in=['programme', 'confirme']
                    ).exists():
                        return start
        return None


class FavoriMedecin(models.Model):
    """Médecins favoris du patient"""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medecins_favoris')
    medecin = models.ForeignKey(Medecin, on_delete=models.CASCADE, related_name='patients_favoris')
    date_ajout = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['patient', 'medecin']

class RechercheSymptome(models.Model):
    """Mapping symptômes -> spécialités suggérées"""
    symptome = models.CharField(max_length=100)
    specialites_suggerees = models.JSONField(default=list)  # ['cardiologue', 'generaliste']
    
    class Meta:
        indexes = [
            models.Index(fields=['symptome']),
        ]



class Disponibilite(models.Model):
    JOUR_CHOICES = [
        ('mon', 'Lundi'),
        ('tue', 'Mardi'),
        ('wed', 'Mercredi'),
        ('thu', 'Jeudi'),
        ('fri', 'Vendredi'),
        ('sat', 'Samedi'),
        ('sun', 'Dimanche'),
    ]

    medecin        = models.ForeignKey(
        'Medecin', on_delete=models.CASCADE, related_name="disponibilites"
    )
    # Créneau hebdo
    jour           = models.CharField(
        max_length=3, choices=JOUR_CHOICES, blank=True,
        help_text="Jour de la semaine (pour disponibilités récurrentes)"
    )
    # Créneau ponctuel (exception)
    date_specific  = models.DateField(
        blank=True, null=True,
        help_text="Date précise (pour congés ou cas particulier)"
    )
    heure_debut    = models.TimeField()
    heure_fin      = models.TimeField()
    is_active      = models.BooleanField(
        default=True,
        help_text="Désactive pour masquer temporairement sans supprimer"
    )

    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Disponibilité"
        verbose_name_plural = "Disponibilités"
        ordering = ['medecin', 'date_specific', 'jour', 'heure_debut']

        constraints = [
            # Unicité pour les créneaux hebdomadaires (date_specific NULL)
            UniqueConstraint(
                fields=['medecin', 'jour', 'heure_debut', 'heure_fin'],
                condition=Q(date_specific__isnull=True) & ~Q(jour=''),
                name='unique_dispo_hebdo'
            ),
            # Unicité pour les créneaux spécifiques (jour vide)
            UniqueConstraint(
                fields=['medecin', 'date_specific', 'heure_debut', 'heure_fin'],
                condition=Q(jour='') | Q(jour__exact=''),
                name='unique_dispo_specifique'
            ),
        ]

    def clean(self):
        errors = {}

        # 0) Medecin : si absent, on lève une erreur explicite (utile si instance créée sans medecin)
        if not getattr(self, 'medecin', None):
            raise ValidationError(_("Le médecin est requis pour valider cette disponibilité."))

        # 1) Présence des heures
        if self.heure_debut is None:
            errors['heure_debut'] = _("L'heure de début est requise.")
        if self.heure_fin is None:
            errors['heure_fin'] = _("L'heure de fin est requise.")
        if errors:
            raise ValidationError(errors)

        # 2) début < fin
        if self.heure_debut >= self.heure_fin:
            raise ValidationError({
                'heure_debut': _("L'heure de début doit être antérieure à l'heure de fin."),
                'heure_fin': _("L'heure de fin doit être postérieure à l'heure de début."),
            })

        # 3) XOR jour / date_specific (exactement l'un ou l'autre)
        if bool(self.jour) == bool(self.date_specific):
            raise ValidationError(_("Spécifiez soit un jour de semaine (jour), soit une date précise (date_specific), pas les deux."))

        # 4) Conflits : seulement si medecin renseigné (on l'a déjà vérifié)
        qs = Disponibilite.objects.filter(medecin=self.medecin, is_active=True)
        if self.date_specific:
            qs = qs.filter(date_specific=self.date_specific)
        else:
            qs = qs.filter(jour=self.jour, date_specific__isnull=True)

        if self.pk:
            qs = qs.exclude(pk=self.pk)

        chevauchements = qs.filter(heure_debut__lt=self.heure_fin, heure_fin__gt=self.heure_debut)
        if chevauchements.exists():
            raise ValidationError(_("Chevauchement détecté avec un autre créneau."))

    def __str__(self):
        if self.date_specific:
            label = self.date_specific.strftime("%d/%m/%Y")
        else:
            label = dict(self.JOUR_CHOICES).get(self.jour, self.jour)
        return f"{self.medecin} — {label} de {self.heure_debut:%H:%M} à {self.heure_fin:%H:%M}"

    def get_slot_datetimes(self, reference_week_start=None):
        slots = []
        if self.date_specific:
            date = self.date_specific
            start = timezone.datetime.combine(date, self.heure_debut)
            end   = timezone.datetime.combine(date, self.heure_fin)
            slots.append((start, end))
        else:
            if not reference_week_start:
                reference_week_start = timezone.now().date()
            dow_map = {'mon':0,'tue':1,'wed':2,'thu':3,'fri':4,'sat':5,'sun':6}
            target = dow_map[self.jour]
            delta_days = (target - reference_week_start.weekday()) % 7
            date = reference_week_start + timezone.timedelta(days=delta_days)
            start = timezone.datetime.combine(date, self.heure_debut)
            end   = timezone.datetime.combine(date, self.heure_fin)
            slots.append((start, end))
        return slots



ALLOWED_TRANSITIONS = {
    'programme': {'confirme', 'annule', 'reporte'},
    'confirme': {'annule', 'reporte', 'en_cours', 'termine'},
    'reporte': {'confirme', 'annule', 'reporte'},
    'en_cours': {'termine'},
    'termine': set(),
    'annule': set(),
}


class RendezVous(models.Model):
    STATUT_CHOICES = [
        ('programme', 'Programmé'),
        ('confirme', 'Confirmé'),
        ('en_cours', 'En cours'),
        ('termine', 'Terminé'),
        ('annule', 'Annulé'),
        ('reporte', 'Reporté'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='rendez_vous')
    medecin = models.ForeignKey(Medecin, on_delete=models.CASCADE, related_name='rendez_vous')
    date_heure_rdv = models.DateTimeField()
    duree_minutes = models.IntegerField(default=30)
    motif = models.CharField(max_length=200, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='programme')
    raison_report = models.CharField(max_length=255, blank=True, null=True)
    raison_annulation = models.CharField(max_length=255, blank=True, null=True)
    ancienne_date_heure = models.DateTimeField(null=True, blank=True)  # pour historiser l'ancienne date
    REPORT_INITIATOR_CHOICES = [
        ('medecin', 'Médecin'),
        ('patient', 'Patient'),
    ]
    report_initiator = models.CharField(max_length=10, choices=REPORT_INITIATOR_CHOICES,
                                        null=True, blank=True, help_text="Qui a initié le report")

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)




    class Meta:
        verbose_name = "Rendez-Vous"
        verbose_name_plural = "Rendez-Vous"

    def __str__(self):
        return f"RDV {self.patient.user.nom_complet()} - Dr. {self.medecin.user.nom_complet()} - {self.date_heure_rdv.strftime('%d/%m/%Y %H:%M')}"


    @property
    def is_programme(self):
        return self.statut == 'programme'

    @property
    def is_confirme(self):
        return self.statut == 'confirme'

    @property
    def is_annule(self):
        return self.statut == 'annule'

    @property
    def is_reporte(self):
        return self.statut == 'reporte'

    @property
    def is_termine(self):
        return self.statut == 'termine'

    # --------------------
    # Autorisations simplifiées pour le 'médecin' (vues/templates docteur)
    # --------------------
    @property
    def can_be_confirmed_by_medecin(self):
        """Le médecin peut confirmer si RDV est programmé ou reporté par patient."""
        return self.statut in ('programme', 'reporte')

    @property
    def can_be_reported_by_medecin(self):
        """Le médecin peut demander à reporter si RDV est programmé ou confirmé."""
        return self.statut in ('programme', 'confirme', 'reporte')

    @property
    def can_be_cancelled_by_medecin(self):
        """Le médecin peut annuler sauf si déjà annulé / terminé."""
        return self.statut in ('programme', 'confirme', 'reporte')

    # --------------------
    # Autorisations simplifiées pour le 'patient'
    # (optionnel — adapte selon ton besoin)
    # --------------------
    @property
    def can_request_report_by_patient(self):
        """Le patient peut demander un report si RDV programmé ou confirmé (mais pas annulé/termine)."""
        return self.statut in ('programme', 'confirme')


    def can_transition_to(self, new_state: str) -> bool:
        """Retourne True si la transition current->new_state est autorisée."""
        return new_state in ALLOWED_TRANSITIONS.get(self.statut, set())

    def _create_notification_safe(self, user, subject, message, **kwargs):
        """Notification non bloquante"""
        try:
            from .utils import create_and_send_notification
            # create_and_send_notification(user, subject, message, notif_type='info', category='appointment', rdv=self)
            create_and_send_notification(user, subject, message, rdv=self, **kwargs)
        except Exception as e:
            logger.exception("Erreur notification non-bloquante pour RDV %s : %s", getattr(self, 'id', '?'), e)

    def _log_history(self, action, performed_by=None, old_value=None, new_value=None, description=None, extra=None):
        """
        Helper pour créer une entrée RdvHistory non bloquante.
        """
        try:
            RdvHistory.objects.create(
                rdv=self,
                action=action,
                performed_by=performed_by,
                old_value=(old_value if old_value is not None else ''),
                new_value=(new_value if new_value is not None else ''),
                description=(description if description is not None else ''),
                extra=(extra or {})
            )
        except Exception as e:
            logger.exception("Impossible de créer RdvHistory pour RDV %s : %s", getattr(self, 'id', '?'), e)

    def confirm(self, by_user=None):
        """Confirme le RDV et enregistre l'historique."""
        if not self.can_transition_to('confirme'):
            raise ValueError("Transition vers 'confirme' non autorisée depuis '%s'." % self.statut)

        with transaction.atomic():
            old = {'statut': self.statut, 'date_heure_rdv': self.date_heure_rdv.isoformat()}
            self.statut = 'confirme'
            self.date_modification = timezone.now()
            self.save(update_fields=['statut', 'date_modification'])
            new = {'statut': self.statut, 'date_heure_rdv': self.date_heure_rdv.isoformat()}

            # log history
            self._log_history(
                action='confirm',
                performed_by=by_user,
                old_value=str(old),
                new_value=str(new),
                description='',
                extra={}
            )

        try:
            subject = "Rendez-vous confirmé"
            message = f"Bonjour M. {self.patient.user.nom_complet()}, votre rendez-vous du {self.date_heure_rdv.strftime('%d/%m/%Y %H:%M')} avec Dr. {self.medecin.user.nom_complet()} a été confirmé."
            self._create_notification_safe(self.patient.user, subject, message, notif_type='success', category='appointment')
        except Exception:
            pass

        return self


    def cancel(self, description: str = '', by_user=None):
        """Annule le RDV et enregistre l'historique."""
        if not self.can_transition_to('annule'):
            raise ValueError("Transition vers 'annule' non autorisée depuis '%s'." % self.statut)

        with transaction.atomic():
            old = {'statut': self.statut, 'date_heure_rdv': self.date_heure_rdv.isoformat()}
            self.statut = 'annule'
            if hasattr(self, 'raison_annulation'):
                self.raison_annulation = (description or '')[:2000]
            self.date_modification = timezone.now()
            update_fields = ['statut', 'date_modification']
            if hasattr(self, 'raison_annulation'):
                update_fields.append('raison_annulation')
            self.save(update_fields=update_fields)
            new = {'statut': self.statut, 'date_heure_rdv': self.date_heure_rdv.isoformat()}

            # log history
            self._log_history(
                action='cancel',
                performed_by=by_user,
                old_value=str(old),
                new_value=str(new),
                description=description,
                extra={}
            )

        # notification non-bloquante
        try:
            subject = "Rendez-vous annulé"
            message = f"Bonjour M. {self.patient.user.nom_complet()},\n\nVotre rendez-vous prévu le {self.date_heure_rdv.strftime('%d/%m/%Y %H:%M')} avec Dr. {self.medecin.user.nom_complet()} a été annulé."
            if description:
                message += f"\nRaison : {description}"
            self._create_notification_safe(self.patient.user, subject, message, notif_type='warning', category='appointment')
        except Exception:
            pass

        return self


    def report(self, new_datetime, raison: str = '', initiator: str = 'medecin', by_user=None):
        """
        Report in-place et log historique.
        initiator: 'medecin' | 'patient'
        """
        if self.statut == 'annule':
            raise ValueError("Impossible de reporter un rendez-vous annulé.")

        if not self.can_transition_to('reporte'):
            raise ValueError("Transition vers 'reporte' non autorisée depuis '%s'." % self.statut)

        with transaction.atomic():
            old = {'statut': self.statut, 'date_heure_rdv': self.date_heure_rdv.isoformat()}
            self.ancienne_date_heure = self.date_heure_rdv
            self.date_heure_rdv = new_datetime
            self.raison_report = (raison or '')[:2000] if hasattr(self, 'raison_report') else ''
            self.report_initiator = initiator
            if initiator == 'medecin':
                self.statut = 'confirme'
            else:
                self.statut = 'reporte'
            self.date_modification = timezone.now()
            update_fields = ['date_heure_rdv', 'report_initiator', 'date_modification', 'statut']
            if hasattr(self, 'raison_report'):
                update_fields.append('raison_report')
            if hasattr(self, 'ancienne_date_heure'):
                update_fields.append('ancienne_date_heure')
            self.save(update_fields=update_fields)

            new = {'statut': self.statut, 'date_heure_rdv': self.date_heure_rdv.isoformat(), 'initiator': initiator}

            # log history
            self._log_history(
                action='report',
                performed_by=by_user,
                old_value=str(old),
                new_value=str(new),
                description=raison,
                extra={'report_initiator': initiator}
            )

        # notifications
        try:
            if initiator == 'medecin':
                subject = "Rendez-vous déplacé et confirmé"
                message = f"Votre rendez-vous avec Dr. {self.medecin.user.nom_complet()} a été déplacé et confirmé au {self.date_heure_rdv.strftime('%d/%m/%Y %H:%M')}."
                self._create_notification_safe(self.patient.user, subject, message, notif_type='info', category='appointment')
            else:
                subject_patient = "Rendez-vous déplacé — en attente de confirmation"
                message_patient = f"Votre rendez-vous avec Dr. {self.medecin.user.nom_complet()} a été déplacé au {self.date_heure_rdv.strftime('%d/%m/%Y %H:%M')} et attend la confirmation du médecin."
                subject_medecin = "Rendez-vous déplacé — en attente de confirmation"
                message_medecin = f"Le rendez-vous avec {self.patient.user.nom_complet()} a été déplacé au {self.date_heure_rdv.strftime('%d/%m/%Y %H:%M')} et attend votre confirmation."

            if raison:
                message_patient += f"\nRaison : {raison}"
                self._create_notification_safe(self.patient.user, subject_patient, message_patient, notif_type='info', category='appointment')
                self._create_notification_safe(self.medecin.user, subject_medecin, message_medecin, notif_type='info', category='appointment')
        except Exception:
            pass

        return self


class Notification(models.Model):
    TYPE_CHOICES = [
        ('info', 'Information'),
        ('success', 'Succès'),
        ('warning', 'Alerte'),
        ('error', 'Erreur'),
    ]
    
    CATEGORY_CHOICES = [
        ('appointment', 'Rendez-vous'),
        ('system', 'Système'),
        ('profile', 'Profil'),
        ('reminder', 'Rappel'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, 
                             related_name='notifications')
    message = models.TextField()
    type = models.CharField(max_length=50, choices=TYPE_CHOICES, default='info')
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='system')
    is_read = models.BooleanField(default=False)
    date_envoi = models.DateTimeField(auto_now_add=True)
    date_read = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-date_envoi']
        
    def __str__(self):
        return f"{self.user.username} - {self.message[:50]}..."
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.date_read = timezone.now()
            self.save()
            
    @property
    def time_since(self):
        """Retourne le temps écoulé depuis l'envoi"""
        return timesince(self.date_envoi)


