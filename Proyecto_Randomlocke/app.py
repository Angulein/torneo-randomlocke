import streamlit as st
import pandas as pd
import os
import io
import os.path
from datetime import datetime
import json
import gspread

# --- LIBRERÍAS DE GOOGLE ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- 1. CONFIGURACIÓN ---
ID_CARPETA_DRIVE = "1saGgOvIbMaldfVhziwLDkeG6Kz7qpBpz" 
CARPETA_SEEDS = "Proyecto_Randomlocke/seeds/" 
NOMBRE_HOJA_CALCULO = "Reportes_Randomlocke"
PASSWORD_OWNER = "1234"

# --- 2. CONEXIONES (DRIVE Y SHEETS) ---
def obtener_credenciales():
    token_info = json.loads(st.secrets["google_token"])
    creds = Credentials.from_authorized_user_info(token_info, [
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/spreadsheets"
    ])
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds

def conectar_sheets():
    creds = obtener_credenciales()
    cliente = gspread.authorize(creds)
    try:
        # Intenta abrir la hoja existente
        return cliente.open(NOMBRE_HOJA_CALCULO).sheet1
    except gspread.SpreadsheetNotFound:
        # Si no existe, la crea y le pone encabezados
        sh = cliente.create(NOMBRE_HOJA_CALCULO)
        hoja = sh.sheet1
        hoja.append_row(["Fecha", "Jugador", "Tipo", "Detalle", "Validación_Secreta", "Link_Evidencia"])
        return hoja

def subir_a_drive(file_buffer, file_name):
    creds = obtener_credenciales()
    service = build('drive', 'v3', credentials=creds)
    file_metadata = {'name': file_name, 'parents': [ID_CARPETA_DRIVE]}
    media = MediaIoBaseUpload(file_buffer, mimetype='image/png')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

# --- 3. LÓGICA DE LOGS ---
def analizar_log(nombre_perfil):
    ruta_seeds = os.path.join(CARPETA_SEEDS, f"{nombre_perfil}.log")
    ruta_raiz = f"{nombre_perfil}.log"
    ruta_final = ruta_seeds if os.path.exists(ruta_seeds) else ruta_raiz
    datos = {}
    if os.path.exists(ruta_final):
        with open(ruta_final, 'r', encoding='utf-8') as f:
            for linea in f:
                if '|' in linea:
                    p = [i.strip() for i in linea.split('|')]
                    if len(p) >= 11:
                        try:
                            datos[p[1]] = f"{p[9]} / {p[10]}"
                        except: continue
    return datos

# --- 4. INTERFAZ ---
st.set_page_config(page_title="Randomlocke Manager", layout="wide")
st.title("🛡️ Registro Oficial de Torneo")

# Radar de archivos .log
archivos_log = []
if os.path.exists(CARPETA_SEEDS):
    archivos_log.extend([f.replace(".log", "") for f in os.listdir(CARPETA_SEEDS) if f.endswith(".log")])
archivos_log.extend([f.replace(".log", "") for f in os.listdir(".") if f.endswith(".log")])
archivos_log = list(set(archivos_log))

modo = st.sidebar.selectbox("¿Quién eres?", ["Jugador", "Owner"])

if modo == "Jugador":
    st.subheader("📝 Reportar Actividad")
    perfil = st.selectbox("Selecciona tu archivo de partida:", [""] + archivos_log)
    
    if perfil:
        tipo = st.radio("¿Qué vas a reportar?", ["Captura de Pokémon", "Medalla Obtenida"])
        
        with st.form("form_registro"):
            if tipo == "Captura de Pokémon":
                dic_pokes = analizar_log(perfil)
                pokemon = st.selectbox("Pokémon atrapado:", list(dic_pokes.keys()))
                foto = st.file_uploader("Sube captura (Imagen)", type=["png", "jpg", "jpeg"])
                info_secreta = dic_pokes.get(pokemon, "No data")
            else:
                pokemon = st.selectbox("Medalla ganada:", ["1", "2", "3", "4", "5", "6", "7", "8"])
                foto = None
                info_secreta = "Progreso de medallas"

            boton_enviar = st.form_submit_button("Enviar Reporte Oficial")

        if boton_enviar:
            id_drive = "Sin_Imagen"
            if tipo == "Captura de Pokémon":
                if foto:
                    buf = io.BytesIO(foto.read())
                    nombre_archivo = f"{perfil}_{pokemon}_{datetime.now().strftime('%H%M%S')}.png"
                    with st.spinner("Subiendo evidencia..."):
                        id_drive = subir_a_drive(buf, nombre_archivo)
                else:
                    st.error("Es obligatorio subir una foto.")
                    st.stop()

            # GUARDAR EN GOOGLE SHEETS
            with st.spinner("Guardando reporte en la base de datos..."):
                try:
                    hoja = conectar_sheets()
                    nueva_fila = [
                        datetime.now().strftime("%d/%m %H:%M"),
                        perfil,
                        tipo,
                        pokemon,
                        info_secreta,
                        f"https://drive.google.com/open?id={id_drive}" if id_drive != "Sin_Imagen" else "N/A"
                    ]
                    hoja.append_row(nueva_fila)
                    st.success(f"✅ ¡Reporte de {perfil} enviado exitosamente!")
                except Exception as e:
                    st.error(f"Error al conectar con Google Sheets: {e}")

elif modo == "Owner":
    st.subheader("🕵️ Panel de Auditoría")
    if st.text_input("Contraseña:", type="password") == PASSWORD_OWNER:
        try:
            hoja = conectar_sheets()
            datos = hoja.get_all_records()
            if datos:
                df_final = pd.DataFrame(datos)
                st.dataframe(df_final, use_container_width=True)
                
                # Botón de descarga
                csv = df_final.to_csv(index=False).encode('utf-8')
                st.download_button("Descargar Backup CSV", csv, "reporte_respaldo.csv", "text/csv")
            else:
                st.info("Aún no hay datos registrados en Google Sheets.")
        except Exception as e:
            st.error(f"No se pudo leer la base de datos: {e}")