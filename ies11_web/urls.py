from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from nucleo import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='inicio'), name='logout'),
    path('', views.inicio, name='inicio'),
    path('institucional/', views.institucional, name='institucional'),
    path('carreras/', views.carreras, name='carreras'),
    path('carrera/detalle/<int:carrera_id>/', views.detalle_carrera, name='detalle_carrera'),
    path('alumno/', views.alumno_dashboard, name='alumno'),
    path('gestion/', views.admin_dashboard, name='gestion'),
    path('gestion/guardar-confirmado/', views.guardar_confirmado, name='guardar_confirmado'),
    path('carrera/editar/<int:carrera_id>/', views.editar_carrera, name='editar_carrera'),
    path('carrera/eliminar/<int:carrera_id>/', views.eliminar_carrera, name='eliminar_carrera'),
    path('accounts/profile/', lambda request: redirect('/admin/')),
]

# Esto permite que Django sirva los PDFs subidos mientras está activo el modo DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)