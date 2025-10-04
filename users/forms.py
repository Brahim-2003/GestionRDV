from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from users.models import Utilisateur
from rdv.models import Patient, Medecin
from django.contrib.auth import get_user_model
from django.contrib.auth import password_validation

# Formulaire de connexion
class ConnexionForm(forms.Form):

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Votre Email'
            })
        )
    
    password = forms.CharField(
        widget= forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Votre mot de passe'
        })
    )

# Formulaire d'inscription 
class RegisterForm(forms.ModelForm):
    nom = forms.CharField(
        max_length=66,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre nom'
        })
    )

    prenom = forms.CharField(
        max_length=66,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre Prénom'
        })
    )

    date_naissance = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre adresse Email'
        })
    )

    telephone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre numéro de téléphone'
        })
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mot de passe'
        })
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmer le mot de passe'
        })
    )

    class Meta:
        model = Utilisateur
        fields = ('nom', 'prenom', 'date_naissance', 'email', 'telephone', 'password1', 'password2')


    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")

        return cleaned_data
    
    
    def save(self, commit=True):
        cleaned_data = self.cleaned_data
        user = Utilisateur.objects.create_user(
            email=cleaned_data['email'],
            nom=cleaned_data['nom'],
            prenom=cleaned_data['prenom'],
            date_naissance=cleaned_data['date_naissance'],
            mot_de_passe=cleaned_data['password1'],
            telephone=cleaned_data['telephone'],
            role='patient'  # Toujours patient pour les inscriptions classiques
        )
        return user


# Formulaire de création d'utilisateur par l'admin
class UtilisateurCreationForm(UserCreationForm):
    nom = forms.CharField(
        max_length=66,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    prenom = forms.CharField(
        max_length=66,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    date_naissance = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control','type': 'date'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    telephone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    role = forms.ChoiceField(
        choices=Utilisateur.ROLE,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mot de passe'
        })
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmez le mot de passe'
        })
    )
    
    class Meta:
        model = Utilisateur
        fields = ('nom', 'prenom', 'date_naissance', 'email', 'telephone', 'role', 'password1', 'password2')

User = get_user_model()

# Formulaire de modification d'utilisateur
class UtilisateurUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["nom", "prenom", "email", "telephone", "role", "is_actif"]





class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["nom", "prenom", "email", "telephone"]


class PatientEditForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ["date_naissance", "sexe", "tel", "adresse", "photo"]


class MedecinEditForm(forms.ModelForm):
    class Meta:
        model = Medecin
        fields = ["numero_order", "specialite", "cabinet", "adresse_cabinet", "tel", "sexe", "diplomes", "photo", "tarif_consultation", "langues_parlees", "accepte_nouveaux_patients"]



class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(
        label="Ancien mot de passe",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Ancien mot de passe"})
    )
    new_password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Nouveau mot de passe"}),
        help_text=password_validation.password_validators_help_text_html()
    )
    new_password2 = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirmez le mot de passe"})
    )


