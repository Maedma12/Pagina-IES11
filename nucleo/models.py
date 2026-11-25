from django.contrib.auth.models import AbstractUser
from django.db import models


# 1. Sistema de Roles y Usuarios
class Usuario(AbstractUser):
    ROLES = (
        ('publico', 'Público'),
        ('alumno', 'Alumno'),
        ('admin', 'Administrativo'),
        ('cs_datos', 'Ciencia de Datos'),
    )
    rol = models.CharField(max_length=20, choices=ROLES, default='publico')
    dni = models.CharField(max_length=20, unique=True, null=True, blank=True)
    nombre = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Nombre"
    )
    apellido = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Apellido"
    )

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
    nombre = models.CharField(max_length=200)
    duracion = models.CharField(max_length=50, default='3 años')
    resolucion = models.CharField(max_length=100, default='S/N')
    area = models.CharField(
        max_length=100,
        default='General',
        help_text='Ej: Salud, Tecnología, Humanidades',
    )
    archivo_pdf = models.FileField(
        upload_to='carreras_pdf/', blank=True, null=True
    )
    descripcion = models.TextField(blank=True, null=True)
    vistas = models.PositiveIntegerField(
        default=0, verbose_name="Número de vistas/clics"
    )
    oferta_academica = models.BooleanField(
        default=True,
        verbose_name="¿En Oferta Académica?",
        help_text="Desmarca esta casilla si la carrera ya no abre preinscripciones para 1er año pero se sigue dictando."
    )

    class Meta:
        verbose_name = "Carrera"
        verbose_name_plural = "Carreras"
        ordering = ['area', 'nombre']

    def __str__(self):
        return self.nombre


# 3. Módulo de Publicaciones / Novedades Institucionales
class Publicacion(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título")
    imagen = models.ImageField(
        upload_to='publicaciones/', blank=True, null=True, verbose_name="Imagen"
    )
    contenido = models.TextField(verbose_name="Contenido")
    fecha_creacion = models.DateTimeField(
        auto_now_add=True, verbose_name="Fecha de Creación"
    )
    vistas = models.PositiveIntegerField(
        default=0, verbose_name="Número de vistas/clics"
    )

    class Meta:
        verbose_name = "Publicación"
        verbose_name_plural = "Publicaciones"

    def __str__(self):
        return self.titulo


# 4. Módulo de Telemetría
class RegistroVisita(models.Model):
    fecha_hora = models.DateTimeField(auto_now_add=True)
    ip_usuario = models.CharField(max_length=50, null=True, blank=True)
    carrera_vista = models.ForeignKey(
        Carrera, on_delete=models.SET_NULL, null=True, blank=True
    )
    dispositivo = models.CharField(max_length=100, null=True, blank=True)


# 5. Módulo de Gestión del Slider / Portada
class SliderItem(models.Model):
    titulo = models.CharField(max_length=150, verbose_name="Título del Slider")
    subtitulo = models.CharField(
        max_length=250,
        blank=True,
        null=True,
        verbose_name="Subtítulo / Descripción corta",
    )
    imagen = models.ImageField(
        upload_to='slider/', verbose_name="Imagen de Fondo"
    )
    texto_boton = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Texto del Botón"
    )
    enlace_boton = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="Enlace de destino"
    )
    orden = models.IntegerField(default=1, verbose_name="Orden de aparición")
    activo = models.BooleanField(
        default=True, verbose_name="¿Mostrar en portada?"
    )
    mostrar_logo = models.BooleanField(
        default=True, verbose_name="Mostrar logo institucional flotante"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Elemento del Slider"
        verbose_name_plural = "Elementos del Slider"
        ordering = ['orden', '-fecha_creacion']

    def __str__(self):
        return self.titulo


# 6. Módulo de Calendario Académico
class EventoCalendario(models.Model):
    CATEGORIAS = [
        ('Inscripciones', 'Inscripciones'),
        ('Inicio', 'Inicio de Clases'),
        ('Cierre', 'Cierre / Entrega'),
        ('Receso', 'Receso Escolar'),
        ('Finalización', 'Finalización del Ciclo'),
        ('General', 'General / Otro'),
    ]

    titulo = models.CharField(max_length=200, verbose_name="Título del Evento")
    descripcion = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Ej: Período escolar común - ICL Marzo 2026",
    )
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(
        blank=True, 
        null=True, 
        verbose_name="Fecha de Fin (Opcional)"
    )
    categoria = models.CharField(
        max_length=50,
        choices=CATEGORIAS,
        default='General',
        verbose_name="Categoría",
    )
    activo = models.BooleanField(
        default=True, verbose_name="¿Mostrar en el calendario?"
    )

    class Meta:
        ordering = ['fecha_inicio']
        verbose_name = "Evento de Calendario"
        verbose_name_plural = "Eventos de Calendario"

    def __str__(self):
        if self.fecha_fin:
            return f"{self.fecha_inicio.strftime('%d/%m/%Y')} al {self.fecha_fin.strftime('%d/%m/%Y')} - {self.titulo}"
        return f"{self.fecha_inicio.strftime('%d/%m/%Y')} - {self.titulo}"


# 7. Módulo de Horarios de Cursado
class Horario(models.Model):
    ANIO_CHOICES = [
        ('1', '1er Año'),
        ('2', '2do Año'),
        ('3', '3er Año'),
    ]

    carrera = models.ForeignKey(
        Carrera, on_delete=models.CASCADE, related_name='horarios'
    )
    anio = models.CharField(
        max_length=1, choices=ANIO_CHOICES, verbose_name="Año de cursado"
    )
    turno = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Ej: 1ª Com. (Mañana) / 2ª Com. (Noche)",
        verbose_name="Comisión / Turno"
    )
    enlace_drive = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Enlace del PDF en Google Drive",
    )
    archivo_pdf = models.FileField(
        upload_to='horarios_pdf/', blank=True, null=True
    )

    class Meta:
        ordering = ['carrera__area', 'carrera__nombre', 'anio', 'turno']
        verbose_name = "Horario"
        verbose_name_plural = "Horarios"

    def __str__(self):
        detalle = f" ({self.turno})" if self.turno else ""
        return f"{self.carrera.nombre} - {self.get_anio_display()}{detalle}"