from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Usuario,
    Carrera,
    Publicacion,
    SliderItem,
    EventoCalendario,
    Horario,
)


class CustomUserAdmin(UserAdmin):
    model = Usuario
    fieldsets = UserAdmin.fieldsets + (
        ('Información Institucional', {'fields': ('rol', 'dni', 'nombre', 'apellido')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información Institucional', {'fields': ('rol', 'dni', 'nombre', 'apellido', 'email')}),
    )


@admin.register(Horario)
class HorarioAdmin(admin.ModelAdmin):
    list_display = ('carrera', 'anio', 'turno', 'enlace_drive')
    list_filter = ('carrera__area', 'anio')
    search_fields = ('carrera__nombre',)


admin.site.register(Usuario, CustomUserAdmin)
admin.site.register(Carrera)
admin.site.register(Publicacion)
admin.site.register(SliderItem)
admin.site.register(EventoCalendario)