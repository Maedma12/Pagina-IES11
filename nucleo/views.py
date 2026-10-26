import os
import json
import tempfile
from io import BytesIO
from google import genai
from google.genai import types
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.files import File
from django.core.mail import send_mail
from django.conf import settings
from .models import Carrera, Publicacion, Usuario

class CustomLoginView(LoginView):
    template_name = 'nucleo/login.html'
    
    def get_success_url(self):
        # Redirección inteligente según el rol del usuario
        if self.request.user.is_staff:
            return reverse_lazy('gestion')
        else:
            return reverse_lazy('alumno')

def inicio(request):
    publicaciones_list = Publicacion.objects.all().order_by('-fecha_creacion')
    context = {
        'publicaciones': publicaciones_list,
    }
    return render(request, 'nucleo/index.html', context)

def institucional(request):
    return render(request, 'nucleo/institucional.html')

def carreras(request):
    carreras_list = Carrera.objects.all()
    context = {
        'carreras': carreras_list,
    }
    return render(request, 'nucleo/carreras.html', context)

# VISTA: Genera la página dinámica para cada carrera individual
def detalle_carrera(request, carrera_id):
    carrera = get_object_or_404(Carrera, id=carrera_id)
    return render(request, 'nucleo/detalle_carrera.html', {'carrera': carrera})

@login_required
def alumno_dashboard(request):
    return render(request, 'nucleo/alumno.html')

@login_required
def admin_dashboard(request):
    tab = request.GET.get('tab', 'carreras')
    
    if request.method == 'POST':
        tipo_carga = request.POST.get('tipo_carga')
        
        # OPCIÓN A: CARGA MANUAL DE CARRERA
        if tipo_carga == 'manual':
            nombre = request.POST.get('nombre')
            duracion = request.POST.get('duracion', '3 años')
            resolucion = request.POST.get('resolucion', 'S/N')
            area = request.POST.get('area', 'General')
            archivo_pdf = request.FILES.get('archivo_pdf')
            
            if nombre:
                Carrera.objects.create(
                    nombre=nombre,
                    duracion=duracion,
                    resolucion=resolucion,
                    area=area,
                    archivo_pdf=archivo_pdf
                )
                return redirect('/gestion/?tab=carreras')

        # OPCIÓN B: CARGA INTELIGENTE CON IA EN LA NUBE (GEMINI SIN RECORTE)
        elif tipo_carga == 'ia_pdf':
            pdf_file = request.FILES.get('pdf_ia')
            if pdf_file:
                tmp_local_path = None
                try:
                    file_bytes = pdf_file.read()
                    
                    # 1. Guardamos el archivo original en un temporal físico local para procesar con IA y subir después
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                        tmp_file.write(file_bytes)
                        tmp_local_path = tmp_file.name
                    
                    request.session['pdf_local_path'] = tmp_local_path
                    request.session['pdf_original_name'] = pdf_file.name
                    
                    # Inicializamos el cliente de la API de Gemini
                    client = genai.Client()
                    
                    # Prompt exigiendo el área y formato de resolución normalizado
                    prompt = (
                        "Analiza este documento oficial del IES N°11 y extrae la información solicitada. "
                        "Debes responder EXCLUSIVAMENTE en formato JSON válido con estas cinco claves exactas: "
                        "\"nombre\", \"duracion\", \"resolucion\", \"resumen\", \"area\". "
                        "Reglas de extracción: "
                        "1. \"nombre\": Nombre completo de la carrera. Obligatoriamente debe comenzar de manera explícita con 'Técnico Superior en...' seguido del nombre oficial. "
                        "2. \"duracion\": Duración estimada (ej. '3 años'). "
                        "3. \"resolucion\": Número de resolución ministerial. DEBE estar estrictamente normalizado comenzando siempre con 'Resolución N° ' seguido del número exacto (ej. 'Resolución N° 3098-E-2022'). Prohibido usar abreviaturas como 'Res.' o dejar solo el número. "
                        "4. \"resumen\": Un resumen exhaustivo del plan de estudio, perfil profesional y las áreas o lugares donde se desempeña el egresado basándote en el documento. "
                        "5. \"area\": Deduce y clasifica la carrera en una sola área temática principal de una o dos palabras (ej. 'Tecnología', 'Salud', 'Humanidades', 'Administración', 'Turismo')."
                    )

                    # 2. Enviamos el archivo completo directamente a Gemini sin recortes previos
                    response = client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=[
                            types.Part.from_bytes(
                                data=file_bytes,
                                mime_type=pdf_file.content_type or 'application/pdf',
                            ),
                            prompt
                        ],
                        config={
                            'response_mime_type': 'application/json',
                        }
                    )

                    # Parseamos la respuesta JSON de la IA
                    parsed_data = json.loads(response.text)

                    datos_ia = {
                        'nombre': parsed_data.get('nombre', 'Nombre no detectado'),
                        'duracion': parsed_data.get('duracion', '3 años'),
                        'resolucion': parsed_data.get('resolucion', 'S/N'),
                        'descripcion': parsed_data.get('resumen', 'Sin resumen disponible'),
                        'area': parsed_data.get('area', 'General')
                    }

                except Exception as e:
                    datos_ia = {
                        'nombre': 'Error en procesamiento IA',
                        'duracion': '3 años',
                        'resolucion': 'S/N',
                        'descripcion': f"Ocurrió un error al conectar con la API de IA: {str(e)}",
                        'area': 'General'
                    }
                
                # Guardamos en la sesión y pasamos a la confirmación
                request.session['datos_ia'] = datos_ia
                return render(request, 'nucleo/confirmacion.html', {'datos_ia': datos_ia}) 

        # OPCIÓN C: CREAR PUBLICACIÓN
        elif tipo_carga == 'publicacion':
            titulo = request.POST.get('titulo')
            contenido = request.POST.get('contenido')
            imagen = request.FILES.get('imagen')
            if titulo and contenido:
                Publicacion.objects.create(
                    titulo=titulo,
                    contenido=contenido,
                    imagen=imagen
                )
                return redirect('/gestion/?tab=publicaciones')

        # OPCIÓN D: CREAR ALUMNO
        elif tipo_carga == 'alumno':
            username = request.POST.get('username')
            dni = request.POST.get('dni')
            nombre = request.POST.get('nombre')
            apellido = request.POST.get('apellido')
            email = request.POST.get('email')
            password = request.POST.get('password')
            
            if username and password:
                # Creamos el usuario con los nuevos campos
                usuario = Usuario.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    dni=dni,
                    nombre=nombre,
                    apellido=apellido,
                    rol='alumno',
                    is_staff=False
                )
                
                # Envío de correo electrónico automático
                if email:
                    asunto = 'Bienvenido al IES N°11 - Tus credenciales de acceso'
                    mensaje = (
                        f"Hola {nombre or ''} {apellido or ''},\n\n"
                        f"Se ha creado tu cuenta institucional para el sistema del IES N°11.\n\n"
                        f"Tus datos de acceso son:\n"
                        f"- Usuario / DNI: {username}\n"
                        f"- Contraseña temporal: {password}\n\n"
                        f"Te recomendamos iniciar sesión y cambiar tu contraseña por seguridad."
                    )
                    try:
                        send_mail(
                            asunto,
                            mensaje,
                            settings.DEFAULT_FROM_EMAIL,
                            [email],
                            fail_silently=False,
                        )
                    except Exception as e:
                        print(f"Error al enviar el correo: {e}")

                return redirect('/gestion/?tab=alumnos')
    
    carreras_list = Carrera.objects.all()
    publicaciones_list = Publicacion.objects.all().order_by('-fecha_creacion')
    alumnos_list = Usuario.objects.filter(rol='alumno') | Usuario.objects.filter(is_staff=False)
    
    context = {
        'tab': tab,
        'carreras': carreras_list,
        'total_carreras': carreras_list.count(),
        'publicaciones': publicaciones_list,
        'alumnos': alumnos_list.distinct(),
    }
    return render(request, 'nucleo/admin.html', context)

@login_required
def guardar_confirmado(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        duracion = request.POST.get('duracion')
        resolucion = request.POST.get('resolucion')
        area = request.POST.get('area', 'General')
        descripcion = request.POST.get('descripcion')
        
        # Recuperamos la ruta del archivo temporal local
        pdf_local_path = request.session.get('pdf_local_path')
        pdf_file_obj = None
        
        if pdf_local_path and os.path.exists(pdf_local_path):
            try:
                with open(pdf_local_path, 'rb') as f:
                    file_content = BytesIO(f.read())
                original_name = request.session.get('pdf_original_name', 'documento.pdf')
                pdf_file_obj = File(file_content, name=original_name)
            except Exception:
                pdf_file_obj = None
        
        if nombre:
            Carrera.objects.create(
                nombre=nombre,
                duracion=duracion,
                resolucion=resolucion,
                area=area,
                descripcion=descripcion,
                archivo_pdf=pdf_file_obj
            )
            
            # Limpiamos los archivos temporales locales y de sesión de forma segura
            if pdf_local_path and os.path.exists(pdf_local_path):
                try:
                    os.remove(pdf_local_path)
                except Exception:
                    pass
            
            if 'datos_ia' in request.session:
                del request.session['datos_ia']
            if 'pdf_local_path' in request.session:
                del request.session['pdf_local_path']
            if 'pdf_original_name' in request.session:
                del request.session['pdf_original_name']
                
        return redirect('/gestion/?tab=carreras')
    return redirect('/gestion/?tab=carreras')

@login_required
def eliminar_carrera(request, carrera_id):
    carrera = get_object_or_404(Carrera, id=carrera_id)
    if carrera.archivo_pdf and default_storage.exists(carrera.archivo_pdf.name):
        default_storage.delete(carrera.archivo_pdf.name)
    carrera.delete()
    return redirect('/gestion/?tab=carreras')

@login_required
def editar_carrera(request, carrera_id):
    carrera = get_object_or_404(Carrera, id=carrera_id)
    if request.method == 'POST':
        carrera.nombre = request.POST.get('nombre')
        carrera.duracion = request.POST.get('duracion')
        carrera.resolucion = request.POST.get('resolucion')
        carrera.area = request.POST.get('area', 'General')
        carrera.descripcion = request.POST.get('descripcion', '')
        
        nuevo_pdf = request.FILES.get('archivo_pdf')
        if nuevo_pdf:
            if carrera.archivo_pdf and default_storage.exists(carrera.archivo_pdf.name):
                default_storage.delete(carrera.archivo_pdf.name)
            carrera.archivo_pdf = nuevo_pdf
            
        carrera.save()
        return redirect('/gestion/?tab=carreras')
    
    return render(request, 'nucleo/editar_carrera.html', {'carrera': carrera})

@login_required
def eliminar_publicacion(request, pub_id):
    publicacion = get_object_or_404(Publicacion, id=pub_id)
    if publicacion.imagen and default_storage.exists(publicacion.imagen.name):
        default_storage.delete(publicacion.imagen.name)
    publicacion.delete()
    return redirect('/gestion/?tab=publicaciones')

@login_required
def baja_alumno(request, user_id):
    alumno = get_object_or_404(Usuario, id=user_id)
    alumno.delete()
    return redirect('/gestion/?tab=alumnos')