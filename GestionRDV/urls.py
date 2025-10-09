
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

handler403 = 'users.views.permission_denied_view'

urlpatterns = [
    path("admin/", admin.site.urls),
    path("users/", include('users.urls')),
    path("rdv/", include('rdv.urls'))
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)
       
