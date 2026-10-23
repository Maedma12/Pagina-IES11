import pypdf
import os
from google import genai
from google.genai import types
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from .models import Carrera


class CustomLoginView(LoginView):
    template_name = 'nucleo/login.html'

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
            archivo_pdf = request.FILES.get('archivo_pdf')
            
            if nombre:
                Carrera.objects.create(
                    nombre=nombre,
                    duracion=duracion,
                    resolucion=resolucion,
                    archivo_pdf=archivo_pdf
                )
                return redirect('gestion')

        # OPCIÓN B: CARGA INTELIGENTE CON IA EN LA NUBE (GEMINI)
        elif tipo_carga == 'ia_pdf':
            pdf_file = request.FILES.get('pdf_ia')
            if pdf_file:
                try:
                    # Leemos los bytes del archivo PDF o imagen subida
                    file_bytes = pdf_file.read()
                    
                    # Inicializamos el cliente de la API de Gemini
                    client = genai.Client() # Toma la clave automáticamente de os.environ["GEMINI_API_KEY"]
                    
                    # Prompt estructurado para que la IA devuelva exactamente lo que necesitamos
                    prompt = (
                        "Analiza este documento oficial del IES N°11 y extrae la siguiente información "
                        "en formato de texto plano estructurado: "
                        "1. Nombre completo de la carrera. "
                        "2. Duración estimada. "
                        "3. Número de resolución ministerial. "
                        "4. Un resumen claro de la descripción o plan de estudio."
                    )

                    # Enviamos el archivo y el prompt a Gemini
                    response = client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=[
                            types.Part.from_bytes(
                                data=file_bytes,
                                mime_type=pdf_file.content_type or 'application/pdf',
                            ),
                            prompt
                        ]
                    )

                    # Estructuramos los datos devueltos por la IA
                    datos_ia = {
                        'nombre': pdf_file.name.replace('.pdf', '').replace('_', ' ').title(),
                        'duracion': '3 años',
                        'resolucion': 'Res. Ministerial (IA)',
                        'descripcion': response.text if response else "No se pudo extraer contenido."
                    }

                except Exception as e:
                    datos_ia = {
                        'nombre': 'Error en procesamiento IA',
                        'duracion': '3 años',
                        'resolucion': 'S/N',
                        'descripcion': f"Ocurrió un error al conectar con la API de IA: {str(e)}"
                    }
                
                # Guardamos en la sesión para la previsualización y confirmación
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
        descripcion = request.POST.get('descripcion')
        
        if nombre:
            Carrera.objects.create(
                nombre=nombre,
                duracion=duracion,
                resolucion=resolucion,
                descripcion=descripcion
            )
            # Limpiamos la sesión
            if 'datos_ia' in request.session:
                del request.session['datos_ia']
                
        return redirect('gestion')
    return redirect('gestion')