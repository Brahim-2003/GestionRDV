from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.timesince import timesince
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from django.utils import timezone
from django.db.models import Q, UniqueConstraint



class Patient(models.Model):
    user =  models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profil_patient')
    numero_patient = models.CharField(max_length=20, unique=True, blank=True)
    date_naissance = models.DateField()
    adresse = models.TextField(blank=True)
    sexe = models.CharField(max_length=10, choices=[('F', 'Féminin'), ('M', 'Masculin')], default='F')
    tel = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(regex=r'^\+?[0-9\s\-\(\)]+$', message="Numéro de téléphone invalide")]
    )


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
    specialite = models.CharField(max_length=100, choices=SPECIALITES)
    cabinet = models.CharField(max_length=200, blank=True)
    adresse_cabinet = models.TextField(blank=True)
    tel = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r'^\+?[0-9\s\-\(\)]+$', message="Numéro de téléphone invalide")]
    )
    sexe = models.CharField(max_length=10, choices=[('F', 'Féminin'), ('M', 'Masculin')], default='F')
    diplomes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Médecin"
        verbose_name_plural = "Médecins"

    def __str__(self):
        return f"Dr. {self.user.nom_complet()} - {self.specialite}"

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
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)




    class Meta:
        verbose_name = "Rendez-Vous"
        verbose_name_plural = "Rendez-Vous"

    def __str__(self):
        return f"RDV {self.patient.user.nom_complet()} - Dr. {self.medecin.user.nom_complet()} - {self.date_heure_rdv.strftime('%d/%m/%Y %H:%M')}"

# models.py

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
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='system')
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


class MessageBot(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    contenu = models.TextField()
    intention = models.CharField(max_length=200)
    reponse = models.TextField()
    date_echange = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message du ChatBot"
        verbose_name_plural = "Messages du ChatBot"

