from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from nucleo import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('', views.inicio, name='inicio'),
    path('institucional/', views.institucional, name='institucional'),
    path('carreras/', views.carreras, name='carreras'),
    path('alumno/', views.alumno_dashboard, name='alumno'),
    path('gestion/', views.admin_dashboard, name='gestion'),
    path('gestion/guardar-confirmado/', views.guardar_confirmado, name='guardar_confirmado'),
    path('accounts/profile/', lambda request: redirect('/admin/')),
    path('pedir-certificado/', views.pedir_certificado, name='pedir_certificado'),
    path('gestion-certificados/', views.gestion_certificados, name='gestion_certificados'),
]
