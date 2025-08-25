from django import forms
from rdv.models import Patient, Medecin, RendezVous, Disponibilite
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _



class PatientProfilForm(forms.Form):
    """Formulaire pour compléter le profil patient"""
    date_naissance = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    adresse = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3
        })
    )


  

class MedecinProfilForm(forms.Form):
    """Formulaire pour compléter le profil médecin"""
    numero_ordre = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    specialite = forms.ChoiceField(
        choices=[],  # Sera rempli dans __init__
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    cabinet = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    adresse_cabinet = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3
        })
    )

    diplomes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3
        })
    )


class UpdateRDVForm(forms.ModelForm):
    """Formulaire pour modifier un rendez-vous"""
    class Meta:
        model = RendezVous
        fields = ['date_heure_rdv', 'patient', 'medecin']
        widgets = {
            'date_heure_rdv': forms.DateTimeInput(
                attrs={
                    'class': 'form-control',
                    'type': 'datetime-local',
                },
                format='%Y-%m-%dT%H:%M'
            ),
            'patient': forms.Select(attrs={'class': 'form-control'}),
            'medecin': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(UpdateRDVForm, self).__init__(*args, **kwargs)
        # Si une instance existe, formater la date_heure_rdv pour HTML5 datetime-local
        if self.instance and self.instance.pk:
            self.initial['date_heure_rdv'] = self.instance.date_heure_rdv.strftime('%Y-%m-%dT%H:%M')


class DisponibiliteBaseForm(forms.ModelForm):
    """
    Formulaire de base factorisant widgets, labels et validation commune.
    Acceptent kwarg `medecin=` utilisé pour les vérifications de conflit.
    """
    def __init__(self, *args, medecin=None, **kwargs):
        self.medecin = medecin
        super().__init__(*args, **kwargs)

        # Select pour 'jour' (évite saisie libre)
        self.fields['jour'].widget = forms.Select(
            choices=[('', '— Choisir —')] + Disponibilite.JOUR_CHOICES,
            attrs={'class': 'form-control'}
        )
        self.fields['jour'].required = False

        # Date input : widget en ISO pour que <input type="date"> soit pré-rempli correctement
        self.fields['date_specific'].widget = forms.DateInput(
            format='%Y-%m-%d',
            attrs={'type': 'date', 'class': 'form-control date-input'}
        )
        # accepter plusieurs formats en entrée (ISO + français) pour robustesse
        self.fields['date_specific'].input_formats = ['%Y-%m-%d', '%d/%m/%Y']
        self.fields['date_specific'].required = False

        # Time inputs
        self.fields['heure_debut'].widget = forms.TimeInput(
            format='%H:%M',
            attrs={'type': 'time', 'class': 'form-control time-input'}
        )
        self.fields['heure_fin'].widget = forms.TimeInput(
            format='%H:%M',
            attrs={'type': 'time', 'class': 'form-control time-input'}
        )
        # accepter formats heure (au besoin)
        self.fields['heure_debut'].input_formats = ['%H:%M', '%H:%M:%S']
        self.fields['heure_fin'].input_formats  = ['%H:%M', '%H:%M:%S']

        # Checkbox
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})

        # Labels lisibles
        self.fields['jour'].label = "Jour (hebdomadaire)"
        self.fields['date_specific'].label = "Date précise (optionnel)"
        self.fields['heure_debut'].label = "Heure début"
        self.fields['heure_fin'].label = "Heure fin"
        self.fields['is_active'].label = "Actif"

        # --- Initials : si instance fournie, forcer les initial au format attendu par les inputs HTML ---
        inst = getattr(self, 'instance', None)
        if inst:
            # date_specific en ISO (YYYY-MM-DD) => input[type=date] affichera la date
            ds = getattr(inst, 'date_specific', None)
            if ds:
                try:
                    self.initial['date_specific'] = ds.strftime('%Y-%m-%d')
                except Exception:
                    # fallback safe
                    self.initial['date_specific'] = str(ds)

            # heures (format HH:MM)
            hd = getattr(inst, 'heure_debut', None)
            if hd:
                try:
                    self.initial['heure_debut'] = hd.strftime('%H:%M')
                except Exception:
                    self.initial['heure_debut'] = str(hd)
            hf = getattr(inst, 'heure_fin', None)
            if hf:
                try:
                    self.initial['heure_fin'] = hf.strftime('%H:%M')
                except Exception:
                    self.initial['heure_fin'] = str(hf)

    def clean(self):
        """
        Validation commune :
         - XOR jour/date_specific
         - heure_debut < heure_fin
         - détection de chevauchement pour self.medecin (si fourni)
        """
        cleaned = super().clean()
        jour = cleaned.get('jour')
        date_specific = cleaned.get('date_specific')
        hd = cleaned.get('heure_debut')
        hf = cleaned.get('heure_fin')

        # 1) jour XOR date_specific
        if bool(jour) == bool(date_specific):
            raise ValidationError(
                _("Spécifiez soit un jour de la semaine (jour), soit une date précise (date_specific), pas les deux.")
            )

        # 2) heures cohérentes
        if hd and hf and hd >= hf:
            self.add_error('heure_fin', _("L'heure de fin doit être supérieure à l'heure de début."))
            raise ValidationError(_("Heures invalides."))

        # 3) conflit de créneaux (si medecin fourni)
        if self.medecin:
            qs = Disponibilite.objects.filter(medecin=self.medecin, is_active=True)
            if date_specific:
                qs = qs.filter(date_specific=date_specific)
            else:
                qs = qs.filter(jour=jour, date_specific__isnull=True)

            # Exclure l'instance courante (si édition)
            if self.instance and getattr(self.instance, 'pk', None):
                qs = qs.exclude(pk=self.instance.pk)

            if hd and hf:
                conflits = qs.filter(heure_debut__lt=hf, heure_fin__gt=hd)
                if conflits.exists():
                    raise ValidationError(_("Chevauchement détecté avec un autre créneau."))

        return cleaned


class DisponibiliteCreateForm(DisponibiliteBaseForm):
    """
    Formulaire utilisé pour la création d'une Disponibilite.
    Dans la vue, n'oublie pas de fixer dispo.medecin avant save() si tu utilises commit=False.
    """
    class Meta:
        model = Disponibilite
        fields = ['jour', 'date_specific', 'heure_debut', 'heure_fin', 'is_active']


class DisponibiliteEditForm(DisponibiliteBaseForm):
    """
    Formulaire utilisé pour l'édition d'une Disponibilite.
    Instantiate avec instance=dispo, medecin=medecin.
    """
    class Meta:
        model = Disponibilite
        fields = ['jour', 'date_specific', 'heure_debut', 'heure_fin', 'is_active']

    def clean(self):
        # tu peux ajouter des validations spécifiques à l'édition ici
        return super().clean()
