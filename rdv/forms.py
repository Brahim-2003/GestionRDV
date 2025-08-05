from django import forms
from rdv.models import Patient, Medecin, RendezVous, Disponibilite



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

class DisponibiliteForm(forms.ModelForm):
    class Meta:
        model = Disponibilite
        # on exclut medecin, on le fixe dans la vue
        exclude = ('medecin',)
        widgets = {
            'jour': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex. Lundi'
            }),
            'heure_debut': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
            'heure_fin': forms.TimeInput(attrs={
                'class': 'form-control',
                'type': 'time'
            }),
        }