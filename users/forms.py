from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from users.models import Utilisateur

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
        fields = ('nom', 'prenom', 'email', 'telephone', 'password1', 'password2')


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
        fields = ('nom', 'prenom', 'email', 'telephone', 'role', 'password1', 'password2')

# Formulaire de modification d'utilisateur
class UtilisateurUpdateForm(UserChangeForm):
    password = None  # Supprime le champ mot de passe
    
    nom = forms.CharField(
        max_length=66,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    prenom = forms.CharField(
        max_length=66,
        widget=forms.TextInput(attrs={'class': 'form-control'})
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
    est_actif = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})

    
    class Meta:
        model = Utilisateur
        fields = ('nom', 'prenom', 'email', 'telephone', 'role', 'est_actif')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Si l'utilisateur modifie son propre profil et n'est pas admin,
        # on retire certains champs
        if hasattr(self, 'request') and self.request.user == self.instance and self.request.user.role != 'admin':
            del self.fields['role']
            del self.fields['est_actif']

