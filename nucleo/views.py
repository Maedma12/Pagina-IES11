import datetime
import json
import os
import tempfile

import gspread
import pandas as pd
import pymupdf as fitz
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from google import genai
from google.genai import types

from .models import Carrera, EventoCalendario, Publicacion, SliderItem, Usuario


# -------------------------------------------------------------------
# FUNCIONES AUXILIARES DE PERMISOS POR ROL
# -------------------------------------------------------------------
def es_analista(user):
    """Permite el acceso a la analítica si el usuario tiene rol cs_datos o admin."""
    return user.is_authenticated and (
        getattr(user, 'rol', '') == 'cs_datos' or user.is_staff
    )


def es_admin(user):
    """Permite el acceso al panel de gestión únicamente a administradores."""
    return user.is_authenticated and (
        getattr(user, 'rol', '') == 'admin' or user.is_staff
    )


# -------------------------------------------------------------------
# FUNCIÓN AUXILIAR DE CATEGORIZACIÓN SEMÁNTICA PARA EL CHATBOT
# -------------------------------------------------------------------
def categorizar_consulta(pregunta_texto, nodo_detectado='', mapa_menu=None):
    """Agrupa intenciones semánticas y traduce IDs del árbol a sus títulos reales."""
    if mapa_menu is None:
        mapa_menu = {}

    texto = str(pregunta_texto).strip()
    nodo = str(nodo_detectado).strip()

    if nodo in mapa_menu:
        return mapa_menu[nodo]
    if texto in mapa_menu:
        return mapa_menu[texto]

    texto_lower = texto.lower()

    if any(
        k in texto_lower
        for k in ['salud', 'enfermer', 'agente sanitari', 'terapeuti']
    ):
        return '¿Qué carreras de la salud se ofrecen?'
    elif any(
        k in texto_lower
        for k in [
            'tecnologia',
            'ciencia de datos',
            'ia',
            'software',
            'programac',
        ]
    ):
        return '¿Qué carreras de tecnología se ofrecen?'
    elif any(
        k in texto_lower
        for k in [
            'preinscrip',
            'inscrib',
            'nexo',
            'ingreso',
            'requisito',
            'inscri',
        ]
    ):
        return '¿Cómo me inscribo y cuáles son los requisitos?'
    elif any(
        k in texto_lower for k in ['nota', 'certificado', 'tramite', 'modelo', 'pedir']
    ):
        return '¿Cómo solicito un certificado o modelo de nota?'
    elif any(
        k in texto_lower
        for k in ['pasantia', 'practica', 'profesionaliz', 'diferencia']
    ):
        return '¿Información sobre prácticas profesionalizantes y pasantías?'
    elif any(k in texto_lower for k in ['beca', 'progresar', 'ayuda']):
        return '¿Qué becas están disponibles?'
    else:
        return pregunta_texto


# -------------------------------------------------------------------
# LOGIN CUSTOM CON REDIRECCIÓN SEGÚN ROL
# -------------------------------------------------------------------
class CustomLoginView(LoginView):
    template_name = 'nucleo/login.html'

    def get_success_url(self):
        user = self.request.user
        rol = getattr(user, 'rol', '')

        if rol == 'cs_datos':
            return reverse_lazy('estadisticas')
        elif user.is_staff or rol == 'admin':
            return reverse_lazy('gestion')
        else:
            return reverse_lazy('alumno')


# -------------------------------------------------------------------
# VISTAS PÚBLICAS
# -------------------------------------------------------------------
def inicio(request):
    publicaciones_list = Publicacion.objects.all().order_by('-fecha_creacion')[:6]
    sliders_list = SliderItem.objects.filter(activo=True).order_by('orden')

    # Filtrado dinámico: únicamente eventos activos entre hoy y los próximos 30 días
    hoy = timezone.now().date()
    limite_30_dias = hoy + datetime.timedelta(days=30)
    eventos_calendario = EventoCalendario.objects.filter(
        activo=True,
        fecha_inicio__gte=hoy,
        fecha_inicio__lte=limite_30_dias
    ).order_by('fecha_inicio')

    context = {
        'publicaciones': publicaciones_list,
        'sliders': sliders_list,
        'eventos_calendario': eventos_calendario,
    }
    return render(request, 'nucleo/index.html', context)


def calendario(request):
    """Vista pública completa del Calendario Académico."""
    eventos = EventoCalendario.objects.filter(activo=True).order_by('fecha_inicio')

    categoria_selected = request.GET.get('categoria', '')
    if categoria_selected:
        eventos = eventos.filter(categoria=categoria_selected)

    context = {
        'eventos': eventos,
        'categoria_selected': categoria_selected,
    }
    return render(request, 'nucleo/calendario.html', context)


def institucional(request):
    return render(request, 'nucleo/institucional.html')


def carreras(request):
    """Muestra ÚNICAMENTE las carreras vigentes en la Oferta Académica (preinscripciones abiertas)."""
    carreras_list = Carrera.objects.filter(oferta_academica=True).order_by('area', 'nombre')
    context = {
        'carreras': carreras_list,
    }
    return render(request, 'nucleo/carreras.html', context)


def detalle_carrera(request, carrera_id):
    carrera = get_object_or_404(Carrera, id=carrera_id)

    carrera.vistas += 1
    carrera.save(update_fields=['vistas'])

    return render(request, 'nucleo/detalle_carrera.html', {'carrera': carrera})


def horarios(request):
    """Muestra TODAS las carreras que se dictan actualmente (incluyendo ciclos cerrados)."""
    carreras_list = Carrera.objects.prefetch_related('horarios').order_by('area', 'nombre')
    context = {
        'carreras': carreras_list,
    }
    return render(request, 'nucleo/horarios.html', context)


def detalle_publicacion(request, pub_id):
    publicacion = get_object_or_404(Publicacion, id=pub_id)

    publicacion.vistas += 1
    publicacion.save(update_fields=['vistas'])

    return render(request, 'nucleo/detalle_publicacion.html', {'publicacion': publicacion})


def lista_publicaciones(request):
    publicaciones_list = Publicacion.objects.all().order_by('-fecha_creacion')
    return render(request, 'nucleo/lista_publicaciones.html', {'publicaciones': publicaciones_list})


# -------------------------------------------------------------------
# DASHBOARDS Y PANEL DE ADMINISTRACIÓN
# -------------------------------------------------------------------
@login_required
def alumno_dashboard(request):
    return render(request, 'nucleo/alumno.html')


@login_required
@user_passes_test(es_admin)
def admin_dashboard(request):
    tab = request.GET.get('tab', 'carreras')

    if request.method == 'POST':
        tipo_carga = request.POST.get('tipo_carga')

        if tipo_carga == 'manual':
            nombre = request.POST.get('nombre')
            duracion = request.POST.get('duracion', '3 años')
            resolucion = request.POST.get('resolucion', 'S/N')
            area = request.POST.get('area', 'General')
            archivo_pdf = request.FILES.get('archivo_pdf')
            oferta_academica = request.POST.get('oferta_academica') == 'on'

            if nombre:
                Carrera.objects.create(
                    nombre=nombre,
                    duracion=duracion,
                    resolucion=resolucion,
                    area=area,
                    archivo_pdf=archivo_pdf,
                    oferta_academica=oferta_academica,
                )
                return redirect('/gestion/?tab=carreras')

        elif tipo_carga == 'calendario':
            titulo = request.POST.get('titulo')
            descripcion = request.POST.get('descripcion', '')
            fecha_inicio = request.POST.get('fecha_inicio')
            fecha_fin = request.POST.get('fecha_fin') or None
            categoria = request.POST.get('categoria', 'General')

            if titulo and fecha_inicio:
                EventoCalendario.objects.create(
                    titulo=titulo,
                    descripcion=descripcion,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    categoria=categoria
                )
                return redirect('/gestion/?tab=calendario')

        elif tipo_carga == 'ia_pdf':
            pdf_file = request.FILES.get('pdf_ia')
            if pdf_file:
                try:
                    file_bytes = pdf_file.read()

                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix='.pdf'
                    ) as tmp_file:
                        tmp_file.write(file_bytes)
                        tmp_local_path = tmp_file.name

                    request.session['pdf_local_path'] = tmp_local_path
                    request.session['pdf_original_name'] = pdf_file.name

                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    texto_pdf = ""
                    for page in doc:
                        texto_pdf += page.get_text() + "\n"

                    client = genai.Client()

                    prompt = (
                        'Analiza este documento oficial del IES N°11 de principio a fin y extrae la'
                        ' información solicitada. Debes responder EXCLUSIVAMENTE en'
                        ' formato JSON válido con estas cinco claves exactas: '
                        ' "nombre", "duracion", "resolucion", "resumen", "area". '
                        'Reglas de extracción: 1. "nombre": Nombre completo de la'
                        ' carrera. Obligatoriamente debe comenzar explícitamente con'
                        " 'Técnico Superior en...' seguido del nombre oficial. 2."
                        ' "duracion": Duración estimada (ej. \'3 años\'). 3. "resolucion":'
                        ' Número de resolución ministerial. DEBE estar estrictamente'
                        " normalizado comenzando siempre con 'Resolución N° ' seguido del"
                        " número exacto (ej. 'Resolución N° 3098-E-2022'). Prohibido usar"
                        " abreviaturas como 'Res.' o dejar solo el número. 4. \"resumen\":"
                        ' Un resumen exhaustivo de todo el plan de estudio, perfil profesional y'
                        ' las áreas o lugares donde se desempeña el egresado basándote en'
                        ' todo el documento. 5. "area": Deduce y clasifica la carrera en una'
                        ' sola área temática principal (ej. \'Tecnología\', \'Salud\','
                        " 'Humanidades', 'Administración', 'Turismo')."
                    )

                    if texto_pdf.strip():
                        contents = [
                            prompt,
                            f"TEXTO COMPLETO DEL DOCUMENTO PDF:\n\n{texto_pdf}"
                        ]
                    else:
                        contents = [
                            types.Part.from_bytes(
                                data=file_bytes,
                                mime_type=pdf_file.content_type or 'application/pdf',
                            ),
                            prompt,
                        ]

                    response = client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=contents,
                        config={
                            'response_mime_type': 'application/json',
                        },
                    )

                    parsed_data = json.loads(response.text)

                    datos_ia = {
                        'nombre': parsed_data.get('nombre', 'Nombre no detectado'),
                        'duracion': parsed_data.get('duracion', '3 años'),
                        'resolucion': parsed_data.get('resolucion', 'S/N'),
                        'descripcion': parsed_data.get(
                            'resumen', 'Sin resumen disponible'
                        ),
                        'area': parsed_data.get('area', 'General'),
                        'oferta_academica': True,
                    }

                except Exception as e:
                    datos_ia = {
                        'nombre': 'Error en procesamiento IA',
                        'duracion': '3 años',
                        'resolucion': 'S/N',
                        'descripcion': (
                            f'Ocurrió un error al conectar con la API de IA: {str(e)}'
                        ),
                        'area': 'General',
                        'oferta_academica': True,
                    }

                request.session['datos_ia'] = datos_ia
                return render(
                    request, 'nucleo/confirmacion.html', {'datos_ia': datos_ia}
                )

        elif tipo_carga == 'publicacion':
            titulo = request.POST.get('titulo')
            contenido = request.POST.get('contenido')
            imagen = request.FILES.get('imagen')
            if titulo and contenido:
                Publicacion.objects.create(
                    titulo=titulo, contenido=contenido, imagen=imagen
                )
                return redirect('/gestion/?tab=publicaciones')

        elif tipo_carga == 'slider':
            titulo = request.POST.get('titulo')
            subtitulo = request.POST.get('subtitulo', '')
            texto_boton = request.POST.get('texto_boton', '')
            enlace_boton = request.POST.get('enlace_boton', '')

            try:
                nuevo_orden = int(request.POST.get('orden', 1))
            except ValueError:
                nuevo_orden = 1

            imagen = request.FILES.get('imagen')
            mostrar_logo = request.POST.get('mostrar_logo') == 'on'

            if titulo and imagen:
                sliders_existentes = SliderItem.objects.filter(orden__gte=nuevo_orden).order_by('-orden')
                for s in sliders_existentes:
                    s.orden += 1
                    s.save()

                SliderItem.objects.create(
                    titulo=titulo,
                    subtitulo=subtitulo,
                    texto_boton=texto_boton,
                    enlace_boton=enlace_boton,
                    orden=nuevo_orden,
                    imagen=imagen,
                    mostrar_logo=mostrar_logo
                )
                return redirect('/gestion/?tab=slider')

        elif tipo_carga == 'alumno':
            username = request.POST.get('username')
            dni = request.POST.get('dni')
            nombre = request.POST.get('nombre')
            apellido = request.POST.get('apellido')
            email = request.POST.get('email')
            password = request.POST.get('password')
            rol = request.POST.get('rol', 'alumno')

            if username and password:
                Usuario.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    dni=dni,
                    nombre=nombre,
                    apellido=apellido,
                    rol=rol,
                    is_staff=(rol == 'admin'),
                )

                if email:
                    asunto = 'Bienvenido al IES N°11 - Tus credenciales de acceso'
                    mensaje = (
                        f"Hola {nombre or ''} {apellido or ''},\n\nSe ha creado tu cuenta"
                        f" institucional ({rol.upper()}) en el IES N°11.\n\nTus datos de"
                        f" acceso son:\nUsuario / DNI: {username}\nContraseña temporal: {password}\n"
                    )
                    try:
                        send_mail(
                            asunto,
                            mensaje,
                            settings.DEFAULT_FROM_EMAIL,
                            [email],
                            fail_silently=True,
                        )
                    except Exception as e:
                        print(f'Error al enviar correo: {e}')

                return redirect('/gestion/?tab=alumnos')

    carreras_list = Carrera.objects.all().order_by('area', 'nombre')
    publicaciones_list = Publicacion.objects.all().order_by('-fecha_creacion')
    sliders_list = SliderItem.objects.all().order_by('orden')
    alumnos_list = Usuario.objects.filter(models.Q(rol='alumno') | models.Q(is_staff=False)).distinct()
    calendario_list = EventoCalendario.objects.all().order_by('fecha_inicio')

    context = {
        'tab': tab,
        'carreras': carreras_list,
        'total_carreras': carreras_list.count(),
        'publicaciones': publicaciones_list,
        'sliders': sliders_list,
        'alumnos': alumnos_list,
        'calendario': calendario_list,
    }
    return render(request, 'nucleo/admin.html', context)


# -------------------------------------------------------------------
# ACCIÓN: ELIMINAR EVENTO DEL CALENDARIO
# -------------------------------------------------------------------
@login_required
@user_passes_test(es_admin)
def eliminar_evento_calendario(request, evento_id):
    evento = get_object_or_404(EventoCalendario, id=evento_id)
    evento.delete()
    return redirect('/gestion/?tab=calendario')


# -------------------------------------------------------------------
# TABLERO DE ESTADÍSTICAS Y ANALÍTICA (GSPREAD CON CREDENCIALES PRIVADAS)
# -------------------------------------------------------------------
@login_required
@user_passes_test(es_analista)
def estadisticas_view(request):
    """Vista del Analista de Datos conectada a la hoja de cálculo privada vía gspread."""

    carreras_qs = Carrera.objects.all().order_by('-vistas')
    carreras_labels = (
        [f"{c.nombre} ({c.vistas})" for c in carreras_qs[:5]]
        if carreras_qs.exists()
        else ['Data Science (0)', 'Enfermería (0)', 'Software (0)', 'Turismo (0)']
    )
    carreras_data = (
        [c.vistas for c in carreras_qs[:5]]
        if carreras_qs.exists()
        else [0, 0, 0, 0]
    )

    pubs_qs = Publicacion.objects.all().order_by('-fecha_creacion')
    pubs_labels = (
        [f"{p.titulo[:20]}... ({p.vistas})" for p in pubs_qs[:5]]
        if pubs_qs.exists()
        else ['Inscripciones 2026 (0)', 'Taller IA (0)', 'Mesa Finales (0)']
    )
    pubs_data = (
        [p.vistas for p in pubs_qs[:5]]
        if pubs_qs.exists()
        else [0, 0, 0]
    )

    creds_path = '/etc/secrets/credentials.json' if os.path.exists('/etc/secrets/credentials.json') else os.path.join(settings.BASE_DIR, 'credentials.json')

    try:
        gc = gspread.service_account(filename=creds_path)
        sh = gc.open("Bot IES")

        mapa_menu = {}
        try:
            ws_menu = sh.worksheet("Menu")
            records_menu = ws_menu.get_all_records()
            for r in records_menu:
                n_id = str(r.get('id', '')).strip()
                n_titulo = str(r.get('titulo', '')).strip() or str(r.get('opcion', '')).strip()
                if n_id and n_titulo:
                    mapa_menu[n_id] = n_titulo
        except Exception as e_menu:
            print(f"Aviso: No se pudo cargar pestaña Menu: {e_menu}")

        worksheet = sh.worksheet("Logs_Bot")
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)

        total_consultas_chat = len(df)
        consultas_ia = int((df['uso_ia'] == 'SI').sum()) if 'uso_ia' in df.columns else 0
        consultas_boton = int((df['origen'] == 'BOTON').sum()) if 'origen' in df.columns else 0
        consultas_texto = int((df['origen'] == 'TEXTO').sum()) if 'origen' in df.columns else 0
        consultas_voz = int((df['origen'] == 'VOZ').sum()) if 'origen' in df.columns else 0

        porcentaje_ia = (
            round((consultas_ia / total_consultas_chat) * 100, 1)
            if total_consultas_chat > 0
            else 0
        )

        origen_labels = ['BOTON', 'TEXTO', 'VOZ']
        origen_data = [consultas_boton, consultas_texto, consultas_voz]

        if 'texto_alumno' in df.columns:
            if 'nodo_detectado' not in df.columns:
                df['nodo_detectado'] = ''
            df['pregunta_normalizada'] = df.apply(
                lambda row: categorizar_consulta(
                    row.get('texto_alumno', ''),
                    row.get('nodo_detectado', ''),
                    mapa_menu
                ),
                axis=1
            )
            top_df = (
                df['pregunta_normalizada']
                .dropna()
                .value_counts()
                .head(5)
                .reset_index()
            )
            top_df.columns = ['pregunta', 'cantidad']
            preguntas_frecuentes = top_df.to_dict(orient='records')
        else:
            preguntas_frecuentes = []

        df_fallos = df[df['hubo_fallo'].astype(str).str.upper() == 'SI'] if 'hubo_fallo' in df.columns else pd.DataFrame()
        total_fallos = len(df_fallos)
        consultas_fallos = []
        if not df_fallos.empty:
            for _, r in df_fallos.iloc[::-1].iterrows():
                consultas_fallos.append({
                    'fecha_hora': str(r.get('fecha_hora', '-')),
                    'texto_alumno': str(r.get('texto_alumno', '-')),
                    'origen': str(r.get('origen', '-'))
                })

        df_dislikes = df[df['feedback'].astype(str).str.upper() == 'DISLIKE'] if 'feedback' in df.columns else pd.DataFrame()
        total_dislikes = len(df_dislikes)
        prompts_dislike = []
        if not df_dislikes.empty:
            for _, r in df_dislikes.iterrows():
                prompts_dislike.append({
                    'texto_alumno': str(r.get('texto_alumno', '-')),
                    'respuesta_bot': str(r.get('respuesta_bot', '-')),
                    'feedback': str(r.get('feedback', 'DISLIKE')),
                    'origen': str(r.get('origen', '-'))
                })

    except Exception as e:
        print(f"Error al conectar con Google Sheets vía gspread: {e}")
        total_consultas_chat = 0
        consultas_ia = 0
        consultas_boton = 0
        porcentaje_ia = 0
        origen_labels = ['BOTON', 'TEXTO', 'VOZ']
        origen_data = [0, 0, 0]
        preguntas_frecuentes = []
        total_fallos = 0
        consultas_fallos = []
        total_dislikes = 0
        prompts_dislike = []

    context = {
        'chart_carreras_labels': json.dumps(carreras_labels),
        'chart_carreras_data': json.dumps(carreras_data),
        'chart_pubs_labels': json.dumps(pubs_labels),
        'chart_pubs_data': json.dumps(pubs_data),
        'total_consultas_chat': total_consultas_chat,
        'consultas_ia': consultas_ia,
        'consultas_boton': consultas_boton,
        'porcentaje_ia': porcentaje_ia,
        'chart_origen_labels': json.dumps(origen_labels),
        'chart_origen_data': json.dumps(origen_data),
        'preguntas_frecuentes': preguntas_frecuentes,
        'total_fallos': total_fallos,
        'consultas_fallos': consultas_fallos,
        'total_dislikes': total_dislikes,
        'prompts_dislike': prompts_dislike,
    }
    return render(request, 'nucleo/estadisticas.html', context)


# -------------------------------------------------------------------
# OTRAS ACCIONES DE ADMINISTRACIÓN
# -------------------------------------------------------------------
@login_required
@user_passes_test(es_admin)
def guardar_confirmado(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        duracion = request.POST.get('duracion')
        resolucion = request.POST.get('resolucion')
        area = request.POST.get('area', 'General')
        descripcion = request.POST.get('descripcion')
        oferta_academica = request.POST.get('oferta_academica') == 'on'

        pdf_local_path = request.session.get('pdf_local_path')

        if nombre:
            if pdf_local_path and os.path.exists(pdf_local_path):
                try:
                    original_name = request.session.get(
                        'pdf_original_name', 'documento.pdf'
                    )
                    with open(pdf_local_path, 'rb') as f:
                        Carrera.objects.create(
                            nombre=nombre,
                            duracion=duracion,
                            resolucion=resolucion,
                            area=area,
                            descripcion=descripcion,
                            archivo_pdf=File(f, name=original_name),
                            oferta_academica=oferta_academica,
                        )
                except Exception:
                    Carrera.objects.create(
                        nombre=nombre,
                        duracion=duracion,
                        resolucion=resolucion,
                        area=area,
                        descripcion=descripcion,
                        oferta_academica=oferta_academica,
                    )
                finally:
                    try:
                        os.remove(pdf_local_path)
                    except Exception:
                        pass
            else:
                Carrera.objects.create(
                    nombre=nombre,
                    duracion=duracion,
                    resolucion=resolucion,
                    area=area,
                    descripcion=descripcion,
                    oferta_academica=oferta_academica,
                )

            request.session.pop('datos_ia', None)
            request.session.pop('pdf_local_path', None)
            request.session.pop('pdf_original_name', None)

    return redirect('/gestion/?tab=carreras')


@login_required
@user_passes_test(es_admin)
def eliminar_carrera(request, carrera_id):
    carrera = get_object_or_404(Carrera, id=carrera_id)
    if carrera.archivo_pdf and default_storage.exists(carrera.archivo_pdf.name):
        default_storage.delete(carrera.archivo_pdf.name)
    carrera.delete()
    return redirect('/gestion/?tab=carreras')


@login_required
@user_passes_test(es_admin)
def editar_carrera(request, carrera_id):
    carrera = get_object_or_404(Carrera, id=carrera_id)
    if request.method == 'POST':
        carrera.nombre = request.POST.get('nombre')
        carrera.duracion = request.POST.get('duracion')
        carrera.resolucion = request.POST.get('resolucion')
        carrera.area = request.POST.get('area', 'General')
        carrera.descripcion = request.POST.get('descripcion', '')
        carrera.oferta_academica = request.POST.get('oferta_academica') == 'on'

        nuevo_pdf = request.FILES.get('archivo_pdf')
        if nuevo_pdf:
            if carrera.archivo_pdf and default_storage.exists(
                carrera.archivo_pdf.name
            ):
                default_storage.delete(carrera.archivo_pdf.name)
            carrera.archivo_pdf = nuevo_pdf

        carrera.save()
        return redirect('/gestion/?tab=carreras')

    return render(request, 'nucleo/editar_carrera.html', {'carrera': carrera})


@login_required
@user_passes_test(es_admin)
def eliminar_publicacion(request, pub_id):
    publicacion = get_object_or_404(Publicacion, id=pub_id)
    if publicacion.imagen and default_storage.exists(publicacion.imagen.name):
        default_storage.delete(publicacion.imagen.name)
    publicacion.delete()
    return redirect('/gestion/?tab=publicaciones')


@login_required
@user_passes_test(es_admin)
def eliminar_slider(request, slide_id):
    slide = get_object_or_404(SliderItem, id=slide_id)
    if slide.imagen and default_storage.exists(slide.imagen.name):
        default_storage.delete(slide.imagen.name)
    slide.delete()
    return redirect('/gestion/?tab=slider')


@login_required
@user_passes_test(es_admin)
def baja_alumno(request, user_id):
    alumno = get_object_or_404(Usuario, id=user_id)
    alumno.delete()
    return redirect('/gestion/?tab=alumnos')