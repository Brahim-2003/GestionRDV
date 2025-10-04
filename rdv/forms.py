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

# --- BASE ---
class DisponibiliteBaseForm(forms.ModelForm):
    """
    Formulaire de base factorisant widgets, labels et validation commune.
    Acceptent kwarg `medecin=` utilisé pour les vérifications de conflit.
    """
    def __init__(self, *args, medecin=None, **kwargs):
        self.medecin = medecin

        if 'instance' not in kwargs and medecin:
            kwargs['instance'] = Disponibilite(medecin=medecin)

        super().__init__(*args, **kwargs)

        if self.instance and medecin:
            self.instance.medecin = medecin

        # --- Widgets communs ---
        if 'jour' in self.fields:
            self.fields['jour'].widget = forms.Select(
                choices=[('', '— Choisir —')] + Disponibilite.JOUR_CHOICES,
                attrs={'class': 'form-control'}
            )
            self.fields['jour'].required = False
            self.fields['jour'].label = "Jour (hebdomadaire)"

        if 'date_specific' in self.fields:
            self.fields['date_specific'].widget = forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'form-control date-input'}
            )
            self.fields['date_specific'].input_formats = ['%Y-%m-%d', '%d/%m/%Y']
            self.fields['date_specific'].required = False
            self.fields['date_specific'].label = "Date précise"

        for champ in ['heure_debut', 'heure_fin']:
            if champ in self.fields:
                self.fields[champ].widget = forms.TimeInput(
                    format='%H:%M',
                    attrs={'type': 'time', 'class': 'form-control time-input'}
                )
                self.fields[champ].input_formats = ['%H:%M', '%H:%M:%S']
                self.fields[champ].label = "Heure " + ("début" if champ=='heure_debut' else "fin")

        if 'is_active' in self.fields:
            self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
            self.fields['is_active'].label = "Actif"

    def clean(self):
        cleaned = super().clean()
        hd, hf = cleaned.get('heure_debut'), cleaned.get('heure_fin')

        # Vérif heures cohérentes
        if hd and hf and hd >= hf:
            self.add_error('heure_fin', _("L'heure de fin doit être supérieure à l'heure de début."))
            raise ValidationError(_("Heures invalides."))

        # Vérif chevauchement
        if self.medecin and hd and hf:
            qs = Disponibilite.objects.filter(medecin=self.medecin, is_active=True)
            # Cas hebdo
            if cleaned.get('jour'):
                qs = qs.filter(jour=cleaned['jour'], date_specific__isnull=True)
            # Cas spécifique
            if cleaned.get('date_specific'):
                qs = qs.filter(date_specific=cleaned['date_specific'])

            if self.instance and getattr(self.instance, 'pk', None):
                qs = qs.exclude(pk=self.instance.pk)

            conflits = qs.filter(heure_debut__lt=hf, heure_fin__gt=hd)
            if conflits.exists():
                raise ValidationError(_("Chevauchement détecté avec un autre créneau."))

        # Vérification exclusivité jour/date
        if cleaned.get('jour') and cleaned.get('date_specific'):
            raise ValidationError(_("Spécifiez soit un jour de semaine (jour), soit une date précise (date_specific), pas les deux."))

        return cleaned

# --- HEBDO EDIT FORM ---
class DisponibiliteHebdoEditForm(DisponibiliteBaseForm):
    class Meta:
        model = Disponibilite
        fields = ['jour', 'heure_debut', 'heure_fin']  # on garde juste jour et heures

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # rendre le champ jour statique
        if 'jour' in self.fields:
            self.fields['jour'].widget.attrs['readonly'] = True
            self.fields['jour'].widget.attrs['disabled'] = True  # désactive la modification
        # cacher date_specific
        if 'date_specific' in self.fields:
            self.fields['date_specific'].widget = forms.HiddenInput()


# --- SPECIFIQUE ---
class DisponibiliteSpecifiqueForm(DisponibiliteBaseForm):
    class Meta:
        model = Disponibilite
        fields = ['date_specific', 'heure_debut', 'heure_fin', 'is_active']

    def __init__(self, *args, **kwargs):
        medecin = kwargs.pop('medecin', None)
        super().__init__(*args, medecin=medecin, **kwargs)

        if 'date_specific' in self.fields:
            self.fields['date_specific'].required = True
        if 'jour' in self.fields:
            self.fields['jour'].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('jour'):
            self.add_error('jour', _("Ne pas spécifier de jour pour une disponibilité spécifique."))
        if not cleaned.get('date_specific'):
            self.add_error('date_specific', _("Date obligatoire pour une disponibilité spécifique."))
        return cleaned


# --- FORMULAIRE DE CREATION HEBDO ---
class DisponibiliteHebdoCreateForm(DisponibiliteBaseForm):
    class Meta:
        model = Disponibilite
        fields = ['jour', 'heure_debut', 'heure_fin', 'is_active']  # AJOUTER 'jour'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Le champ jour est requis mais peut être masqué côté template
        if 'jour' in self.fields:
            self.fields['jour'].required = True

        # Masquer le champ date_specific
        if 'date_specific' in self.fields:
            self.fields['date_specific'].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()

        # Vérification du jour (maintenant le champ existe)
        if not cleaned.get('jour'):
            if 'jour' in self.fields:  # Vérifier que le champ existe avant d'ajouter l'erreur
                self.add_error('jour', "Jour obligatoire pour une disponibilité hebdomadaire.")
            else:
                # Si le champ n'existe pas, ajouter l'erreur globalement
                raise ValidationError("Jour obligatoire pour une disponibilité hebdomadaire.")

        # La date spécifique ne doit jamais être remplie
        if cleaned.get('date_specific'):
            self.add_error('date_specific', "Ne pas spécifier de date pour une disponibilité hebdomadaire.")

        return cleaned

# --- Formulaire de base pour l'édition hebdo ---
class DisponibiliteHebdoEditForm(forms.ModelForm):
    class Meta:
        model = Disponibilite
        fields = ['heure_debut', 'heure_fin']
        widgets = {
            'heure_debut': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
            'heure_fin': forms.TimeInput(format='%H:%M', attrs={'type': 'time'}),
        }
        labels = {
            'heure_debut': _('Heure de début'),
            'heure_fin': _('Heure de fin'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # rendre les champs obligatoires
        self.fields['heure_debut'].required = True
        self.fields['heure_fin'].required = True

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get('heure_debut')
        fin = cleaned.get('heure_fin')

        if debut and fin and debut >= fin:
            self.add_error('heure_fin', _("L'heure de fin doit être après l'heure de début."))

        return cleaned



class DisponibiliteSpecifiqueCreateForm(DisponibiliteBaseForm):
    class Meta:
        model = Disponibilite
        fields = ['date_specific', 'heure_debut', 'heure_fin', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'jour' in self.fields:
            self.fields['jour'].widget = forms.HiddenInput()
        if 'date_specific' in self.fields:
            self.fields['date_specific'].required = True

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('date_specific'):
            self.add_error('date_specific', _("Date obligatoire pour une disponibilité spécifique."))
        if cleaned.get('jour'):
            self.add_error('jour', _("Ne pas spécifier de jour pour une disponibilité spécifique."))
        return cleaned


class DisponibiliteSpecifiqueEditForm(DisponibiliteSpecifiqueForm):
    """Édition spécifique"""

    
class AnnulerRdvForm(forms.Form):
    raison = forms.CharField(
        label="Raison d'annulation",
        required=False,
        widget=forms.Textarea(attrs={'rows':4}),
        max_length=1000,
    )

class ReporterRdvForm(forms.Form):
    nouvelle_date = forms.DateField(
        label="Nouvelle date",
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=True
    )
    nouvelle_heure = forms.TimeField(
        label="Nouvelle heure",
        widget=forms.TimeInput(attrs={'type': 'time'}),
        required=True
    )
    raison = forms.CharField(
        label="Raison du report (optionnel)",
        widget=forms.Textarea(attrs={'rows':3}),
        required=False,
        max_length=1000
    )


class NotifierRdvForm(forms.Form):
    subject = forms.CharField(
        label="Sujet",
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    
    message = forms.CharField(
        label="Message",
        required=True,
        widget=forms.Textarea(attrs={"rows": 5, "class": "form-control"})
    )



class RendezVousForm(forms.Form):
    specialite = forms.ChoiceField(
        choices=Medecin.SPECIALITES, required=True, label="Spécialité"
    )
    medecin = forms.ModelChoiceField(
        queryset=Medecin.objects.all(), required=True, label="Médecin"
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}), required=True, label="Date"
    )
    heure = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time'}), required=True, label="Heure"
    )
    motif = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}), required=False, label="Motif"
    )



