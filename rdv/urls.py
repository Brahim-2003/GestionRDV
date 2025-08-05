from django.urls import path
from . import views
from django.shortcuts import redirect

app_name = "rdv"

urlpatterns=[
    path('', views.acceuil_view, name='acceuil'),  # Redirige vers le tableau de bord
    path('dashboard/', views.dashboard_admin_view, name='dashboard_redirect'),
    path('api/dashboard/stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
    path('rdvs/', views.liste_rendez_vous, name='list_rdv'),
    path('modifier_rdv/<int:rdv_id>/', views.edit_rdv, name='modifier_rendez_vous'),
    path('supprimer_rdv/<int:rdv_id>/', views.delete_rdv, name='supprimer_rendez_vous'),
    path('dashboard_medecin/', views.dashboard_medecin_view, name='dashboard_medecin'),
    path('liste_rdv_medecin/', views.liste_rdv_medecin, name='liste_rdv_medecin'),
    path('disponibilites/', views.disponibilites_list, name='disponibilites_list'),
    path('disponibilites/add/', views.disponibilite_add, name='disponibilite_add'),
    path('disponibilites/<int:pk>/edit/', views.disponibilite_edit, name='disponibilite_edit'),
    path('disponibilites/<int:pk>/delete/', views.disponibilite_delete, name='disponibilite_delete'),
    path('notifs/', views.list_notif, name='notifs'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_as_read, name='mark_read'),
    path('notifications/mark-all-read/', views.mark_all_as_read, name='mark_all_read'),
    path('notifications/delete/<int:notification_id>/', views.delete_notification, name='delete'),
    path('notifications/delete-all/', views.delete_all_notifications, name='delete_all'),
    path('notifications/count/', views.get_notification_count, name='count'),

]