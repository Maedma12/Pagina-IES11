import pypdf
import os
import json
from google import genai
from google.genai import types
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.files import File
from .models import Carrera

class CustomLoginView(LoginView):
    template_name = 'nucleo/login.html'
    
    def get_success_url(self):
        # Redirección inteligente según el rol del usuario
        if self.request.user.is_staff:
            return reverse_lazy('gestion')
        else:
            return reverse_lazy('alumno')

def inicio(request):
    return render(request, 'nucleo/index.html')

def institucional(request):
    return render(request, 'nucleo/institucional.html')

def carreras(request):
    carreras_list = Carrera.objects.all()
    context = {
        'carreras': carreras_list,
    }
    return render(request, 'nucleo/carreras.html', context)

# NUEVA VISTA: Genera la página dinámica para cada carrera individual
def detalle_carrera(request, carrera_id):
    carrera = get_object_or_404(Carrera, id=carrera_id)
    return render(request, 'nucleo/detalle_carrera.html', {'carrera': carrera})

@login_required
def alumno_dashboard(request):
    return render(request, 'nucleo/alumno.html')

@login_required
def admin_dashboard(request):
    if request.method == 'POST':
        tipo_carga = request.POST.get('tipo_carga')
        
        # OPCIÓN A: CARGA MANUAL
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
                return redirect('gestion')

        # OPCIÓN B: CARGA INTELIGENTE CON IA EN LA NUBE (GEMINI)
        elif tipo_carga == 'ia_pdf':
            pdf_file = request.FILES.get('pdf_ia')
            if pdf_file:
                try:
                    # Guardamos el archivo temporalmente en disco
                    file_bytes = pdf_file.read()
                    temp_path = default_storage.save(f'temp_uploads/{pdf_file.name}', ContentFile(file_bytes))
                    request.session['pdf_temp_path'] = temp_path
                    
                    # Inicializamos el cliente de la API de Gemini
                    client = genai.Client()
                    
                    # Prompt actualizado exigiendo el área y formato de resolución normalizado
                    prompt = (
                        "Analiza este documento oficial del IES N°11 y extrae la información solicitada. "
                        "Debes responder EXCLUSIVAMENTE en formato JSON válido con estas cinco claves exactas: "
                        "\"nombre\", \"duracion\", \"resolucion\", \"resumen\", \"area\". "
                        "Reglas de extracción: "
                        "1. \"nombre\": Nombre completo de la carrera. Obligatoriamente debe comenzar de manera explícita con 'Técnico Superior en...' seguido del nombre oficial. "
                        "2. \"duracion\": Duración estimada (ej. '3 años'). "
                        "3. \"resolucion\": Número de resolución ministerial. DEBE estar estrictamente normalizado comenzando siempre con 'Resolución N° ' seguido del número exacto (ej. 'Resolución N° 3098-E-2022'). Prohibido usar abreviaturas como 'Res.' o dejar solo el número. "
                        "4. \"resumen\": Un resumen breve del plan de estudio y salidas laborales. "
                        "5. \"area\": Deduce y clasifica la carrera en una sola área temática principal de una o dos palabras (ej. 'Tecnología', 'Salud', 'Humanidades', 'Administración', 'Turismo')."
                    )

                    # Enviamos a Gemini pidiendo JSON
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
                
                # Guardamos en la sesión
                request.session['datos_ia'] = datos_ia
                return render(request, 'nucleo/confirmacion.html', {'datos_ia': datos_ia})

    carreras_list = Carrera.objects.all()
    context = {
        'carreras': carreras_list,
        'total_carreras': carreras_list.count(),
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
        
        # Recuperamos el archivo PDF temporal si existe
        pdf_temp_path = request.session.get('pdf_temp_path')
        pdf_file_obj = None
        
        if pdf_temp_path and default_storage.exists(pdf_temp_path):
            file_content = default_storage.open(pdf_temp_path)
            pdf_file_obj = File(file_content, name=os.path.basename(pdf_temp_path))
        
        if nombre:
            Carrera.objects.create(
                nombre=nombre,
                duracion=duracion,
                resolucion=resolucion,
                area=area,
                descripcion=descripcion,
                archivo_pdf=pdf_file_obj
            )
            
            # Limpiamos temporales
            if pdf_temp_path and default_storage.exists(pdf_temp_path):
                default_storage.delete(pdf_temp_path)
            if 'datos_ia' in request.session:
                del request.session['datos_ia']
            if 'pdf_temp_path' in request.session:
                del request.session['pdf_temp_path']
                
        return redirect('gestion')
    return redirect('gestion')

@login_required
def eliminar_carrera(request, carrera_id):
    carrera = get_object_or_404(Carrera, id=carrera_id)
    if carrera.archivo_pdf and default_storage.exists(carrera.archivo_pdf.name):
        default_storage.delete(carrera.archivo_pdf.name)
    carrera.delete()
    return redirect('gestion')

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
        return redirect('gestion')
    
    return render(request, 'nucleo/editar_carrera.html', {'carrera': carrera})