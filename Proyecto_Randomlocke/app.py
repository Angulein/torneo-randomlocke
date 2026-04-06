import streamlit as st
import pandas as pd
import os
import io
import os.path
from datetime import datetime
import json

# --- LIBRERÍAS DE GOOGLE (OAuth 2.0) ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- 1. CONFIGURACIÓN ---
ID_CARPETA_DRIVE = "1saGgOvIbMaldfVhziwLDkeG6Kz7qpBpz" 
RUTA_CLIENT_SECRET = "client_secret.json" 
CARPETA_SEEDS = "Proyecto_Randomlocke/seeds/"
ARCHIVO_REPORTES = "reportes_oficiales.csv"
PASSWORD_OWNER = "1234"

# --- 2. CONEXIÓN OAUTH 2.0 (MODO NUBE CON SECRETS) ---
def conectar_drive():
    token_info = json.loads(st.secrets["google_token"])
    creds = Credentials.from_authorized_user_info(token_info, ["https://www.googleapis.com/auth/drive.file"])
    
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        
    return build('drive', 'v3', credentials=creds)

def subir_a_drive(file_buffer, file_name):
    service = conectar_drive()
    file_metadata = {'name': file_name, 'parents': [ID_CARPETA_DRIVE]}
    media = MediaIoBaseUpload(file_buffer, mimetype='image/png')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

# --- 3. LÓGICA DE LOGS (CORREGIDA PARA EL RADAR) ---
def analizar_log(nombre_perfil):
    # Revisa si el archivo está en 'seeds/' o si está suelto en la raíz
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


if not os.path.exists(CARPETA_SEEDS):
    os.makedirs(CARPETA_SEEDS)

# --- RADAR DE ARCHIVOS ---
archivos_log = []
if os.path.exists(CARPETA_SEEDS):
    archivos_log.extend([f.replace(".log", "") for f in os.listdir(CARPETA_SEEDS) if f.endswith(".log")])
archivos_log.extend([f.replace(".log", "") for f in os.listdir(".") if f.endswith(".log")])
archivos_log = list(set(archivos_log))

# --- MENÚ LATERAL (Corregido, sin duplicar) ---
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
                    with st.spinner("Subiendo a Drive..."):
                        id_drive = subir_a_drive(buf, nombre_archivo)
                else:
                    st.error("Sube una foto.")
                    st.stop()

            nuevo_dato = {
                "Fecha": datetime.now().strftime("%d/%m %H:%M"),
                "Jugador": perfil,
                "Tipo": tipo,
                "Detalle": pokemon,
                "Validación_Secreta": info_secreta,
                "Link_Evidencia": f"https://drive.google.com/open?id={id_drive}" if id_drive != "Sin_Imagen" else "N/A"
            }
            df = pd.read_csv(ARCHIVO_REPORTES) if os.path.exists(ARCHIVO_REPORTES) else pd.DataFrame()
            pd.concat([df, pd.DataFrame([nuevo_dato])], ignore_index=True).to_csv(ARCHIVO_REPORTES, index=False)
            st.success("✅ ¡Reporte enviado!")

elif modo == "Owner":
    st.subheader("🕵️ Panel Admin")
    clave = st.text_input("Contraseña:", type="password")
    if clave == PASSWORD_OWNER:
        if os.path.exists(ARCHIVO_REPORTES):
            st.dataframe(pd.read_csv(ARCHIVO_REPORTES), use_container_width=True)
        else:
            st.info("No hay reportes aún.")