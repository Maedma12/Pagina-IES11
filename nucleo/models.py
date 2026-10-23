from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. Sistema de Roles y Usuarios (Con related_name corregido)
class Usuario(AbstractUser):
    ROLES = (
        ('publico', 'Público'),
        ('alumno', 'Alumno'),
        ('admin', 'Administrativo'),
        ('cs_datos', 'Ciencia de Datos'),
    )
    rol = models.CharField(max_length=20, choices=ROLES, default='publico')
    dni = models.CharField(max_length=20, unique=True, null=True, blank=True)

    # Solución al conflicto de campos con Django Auth
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        related_name='usuario_set',
        related_query_name='usuario',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        related_name='usuario_permissions_set',
        related_query_name='usuario_permission',
    )

# 2. Núcleo Académico
class Carrera(models.Model):
    nombre = models.CharField(max_length=150)
    duracion = models.CharField(max_length=50, default='3 años')
    resolucion = models.CharField(max_length=100, default='S/N')
    # Nuevo campo para adjuntar el PDF del plan de estudios/resolución
    archivo_pdf = models.FileField(upload_to='carreras_pdf/', blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nombre

class EspacioCurricular(models.Model):
    id_espacio = models.CharField(max_length=30, primary_key=True)
    nombre_espacio = models.CharField(max_length=200)
    carrera = models.ForeignKey(Carrera, on_delete=models.CASCADE)
    anio = models.IntegerField()
    regimen = models.CharField(max_length=100)
    carga_horaria = models.IntegerField()

class Calificacion(models.Model):
    alumno = models.ForeignKey(Usuario, on_delete=models.CASCADE) 
    espacio = models.ForeignKey(EspacioCurricular, on_delete=models.CASCADE)
    nota = models.IntegerField(null=True, blank=True)
    condicion = models.CharField(max_length=20, null=True, blank=True)
    fecha_evaluacion = models.DateField(null=True, blank=True)

# 3. Módulo de Telemetría (Para Ciencia de Datos)
class RegistroVisita(models.Model):
    fecha_hora = models.DateTimeField(auto_now_add=True)
    ip_usuario = models.CharField(max_length=50, null=True, blank=True)
    carrera_vista = models.ForeignKey(Carrera, on_delete=models.SET_NULL, null=True, blank=True)
    dispositivo = models.CharField(max_length=100, null=True, blank=True)