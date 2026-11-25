from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.shortcuts import redirect
from django.urls import path

from nucleo import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='inicio'), name='logout'),
    path('', views.inicio, name='inicio'),
    path('institucional/', views.institucional, name='institucional'),
    path('carreras/', views.carreras, name='carreras'),
    path('carrera/detalle/<int:carrera_id>/', views.detalle_carrera, name='detalle_carrera'),
    
    # === RUTA DE HORARIOS DE CURSADO ===
    path('horarios/', views.horarios, name='horarios'),
    
    path('alumno/', views.alumno_dashboard, name='alumno'),
    path('gestion/', views.admin_dashboard, name='gestion'),
    path('gestion/guardar-confirmado/', views.guardar_confirmado, name='guardar_confirmado'),
    path('carrera/editar/<int:carrera_id>/', views.editar_carrera, name='editar_carrera'),
    path('carrera/eliminar/<int:carrera_id>/', views.eliminar_carrera, name='eliminar_carrera'),
    
    # === RUTAS DE CALENDARIO, PUBLICACIONES Y SLIDER ===
    path('calendario/', views.calendario, name='calendario'),
    path('gestion/calendario/eliminar/<int:evento_id>/', views.eliminar_evento_calendario, name='eliminar_evento_calendario'),
    path('publicacion/<int:pub_id>/', views.detalle_publicacion, name='detalle_publicacion'),
    path('publicaciones/', views.lista_publicaciones, name='lista_publicaciones'),
    path('gestion/slider/eliminar/<int:slide_id>/', views.eliminar_slider, name='eliminar_slider'),
    
    # Ruta para el tablero de métricas y analítica
    path('estadisticas/', views.estadisticas_view, name='estadisticas'),
    
    # Rutas para las solapas de publicaciones y alumnos
    path('gestion/publicacion/eliminar/<int:pub_id>/', views.eliminar_publicacion, name='eliminar_publicacion'),
    path('gestion/alumno/baja/<int:user_id>/', views.baja_alumno, name='baja_alumno'),
    
    path('accounts/profile/', lambda request: redirect('/admin/')),
]
