from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Carrera, EspacioCurricular, Calificacion, RegistroVisita, Publicacion

# Personalizamos el administrador para el modelo Usuario
class CustomUserAdmin(UserAdmin):
    model = Usuario
    # Agregamos los campos personalizados a las vistas de edición en el admin
    fieldsets = UserAdmin.fieldsets + (
        ('Información Institucional', {'fields': ('rol', 'dni', 'nombre', 'apellido')}),
    )
    # Agregamos los campos al formulario de creación de usuario
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Institucional', {'fields': ('rol', 'dni', 'nombre', 'apellido', 'email')}),
    )

# Registramos los modelos con sus debidas configuraciones
admin.site.register(Usuario, CustomUserAdmin)
admin.site.register(Carrera)
admin.site.register(EspacioCurricular)
admin.site.register(Calificacion)
admin.site.register(RegistroVisita)
admin.site.register(Publicacion) # Opcional: si también quieres gestionarlas desde /admin/