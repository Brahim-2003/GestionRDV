from django.urls import path
from . import views

app_name = "users"

urlpatterns=[
    path('login/', views.connecter, name='login'),
    path('logout/', views.deconnecter, name='logout'),
    path('register/', views.inscription, name='register'),
    path('users/', views.liste_utilisateurs, name='list_users'),
    path('users/ajax/', views.liste_utilisateurs_ajax, name='list_users_ajax'),
    path('users/add/', views.creer_utilisateur, name='creer_utilisateur'),
    path('modifier_user/, <int:user_id>', views.modifier_utilisateur, name='modifier_utilisateur'),
    path('supprimer_user/, <int:user_id>', views.supprimer_utilisateur, name='supprimer_utilisateur'),
    path('profil_user/, <int:user_id>', views.profil, name="profil"),
    path('mon_profil/', views.profil_view, name="mon_profil"),
    
]