from django.contrib import admin
from .models import Usuario, Carrera, EspacioCurricular, Calificacion, RegistroVisita

# Registramos los modelos para gestionarlos desde la administración
admin.site.register(Usuario)
admin.site.register(Carrera)
admin.site.register(EspacioCurricular)
admin.site.register(Calificacion)
admin.site.register(RegistroVisita)