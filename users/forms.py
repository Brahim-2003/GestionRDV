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
    # (ton formulaire existant — pas répété ici)
    class Meta:
        model = Utilisateur
        fields = ('nom', 'prenom', 'date_naissance', 'email', 'telephone', 'role', 'is_actif', 'password1', 'password2')

        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom'
            }),
            'prenom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prénom'
            }),
            'date_naissance': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemple.com'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+235 XX XX XX XX'
            }),
            'role': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_actif': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and Utilisateur.objects.filter(email__iexact=email).exists():
            raise ValidationError("Un compte existe déjà avec cette adresse email.")
        return email


class UtilisateurEditForm(forms.ModelForm):
    """
    Formulaire pour éditer un utilisateur existant.
    Ne gère PAS le mot de passe (utiliser un formulaire séparé pour ça).
    """
    class Meta:
        model = Utilisateur
        fields = ('nom', 'prenom', 'email', 'telephone', 'role', 'is_actif')
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom'
            }),
            'prenom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prénom'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemple.com'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+235 XX XX XX XX'
            }),
            'role': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_actif': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            })
        }
        labels = {
            'nom': 'Nom',
            'prenom': 'Prénom',
            'email': 'Email',
            'telephone': 'Téléphone',
            'role': 'Rôle',
            'is_actif': 'Compte actif'
        }
    
    def clean_email(self):
        """
        Vérifie que l'email n'est pas déjà utilisé par un autre utilisateur.
        """
        email = self.cleaned_data.get('email')
        if email:
            # Exclure l'utilisateur actuel de la vérification
            existing = Utilisateur.objects.filter(email__iexact=email).exclude(id=self.instance.id)
            if existing.exists():
                raise ValidationError("Un autre compte existe déjà avec cette adresse email.")
        return email
    
    def clean_telephone(self):
        """
        Validation optionnelle du téléphone (adapte selon tes besoins).
        """
        telephone = self.cleaned_data.get('telephone')
        # Ajoute ta logique de validation si nécessaire
        return telephone

User = get_user_model()
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


