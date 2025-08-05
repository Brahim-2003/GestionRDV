
from django.contrib import admin
from django.urls import path, include

handler403 = 'users.views.permission_denied_view'

urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include('users.urls')),
    path("rdv/", include('rdv.urls'))
]
