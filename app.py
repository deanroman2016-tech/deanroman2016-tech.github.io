import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import re
import time

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="RUT AI Extractor Pro", layout="wide", page_icon="📑")

if "limpiar_count" not in st.session_state:
    st.session_state.limpiar_count = 0

def ejecutar_limpieza():
    st.session_state.limpiar_count += 1

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔒 Seguridad y Privacidad")
    st.warning("1. Sin Almacenamiento.\n2. Sesión Volátil.\n3. Privacidad Total.")
    st.info("💡 **Nota:** Se aplica una pausa de 10s entre archivos para proteger la cuota gratuita.")
    st.button("🧹 Limpiar Todo", on_click=ejecutar_limpieza)
    st.divider()
    st.caption("Motor: Gemini 2.0/3.0 Flash | v.2026")

st.title("📑 Extractor de RUT Inteligente")

# --- 2. API CONFIG ---
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Falta API Key en Secrets.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 3. CARGA DE ARCHIVOS ---
files = st.file_uploader(
    "Sube los archivos RUT (PDF)", 
    type="pdf", 
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.limpiar_count}"
)

if files and len(files) > 5:
    st.error("⚠️ Máximo 5 archivos por tanda.")
    st.stop()

if files and st.button("🚀 Iniciar Procesamiento"):
    resultados = []
    
    # Usamos el identificador 2.0 Flash que es compatible con la estructura de la serie 3
    # y es el más estable para la API v1beta en este momento.
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    
    for i, f in enumerate(files):
        with st.spinner(f"Procesando {f.name} ({i+1}/{len(files)})..."):
            try:
                # Pausa obligatoria para evitar el error 429
                if i > 0:
                    time.sleep(10)
                
                f.seek(0)
                pdf_data = f.read()
                
                prompt = """
                Analiza la PRIMERA PÁGINA de este RUT. Extrae los datos en este JSON plano:
                {
                  "NIT": "casilla 5",
                  "Tipo_Contribuyente": "Persona Jurídica o Natural",
                  "Razon_Social": "casilla 35",
                  "Primer_Apellido": "casilla 31",
                  "Segundo_Apellido": "casilla 32",
                  "Primer_Nombre": "casilla 33",
                  "Otros_Nombres": "casilla 34",
                  "Ciudad": "casilla 40",
                  "Direccion": "casilla 41",
                  "Correo_Electronico": "casilla 42",
                  "Telefono_1": "casilla 44",
                  "Actividad_Economica": "casilla 46",
                  "Codigo_Postal": "casilla 43"
                }
                IMPORTANTE: Responde SOLO el JSON. Si no puedes leer algo, deja "".
                """
                
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': pdf_data}
                ])
                
                # Extraer JSON de la respuesta
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                
                if json_match:
                    data = json.loads(json_match.group())
                    
                    # Unificación de nombre
                    if data.get("Razon_Social") and data["Razon_Social"].strip():
                        data["Nombre_Final"] = data["Razon_Social"]
                    else:
                        partes = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                                 data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                        data["Nombre_Final"] = " ".join([n for n in partes if n]).strip()
                    
                    resultados.append(data)
                else:
                    st.error(f"La IA no pudo procesar el formato de {f.name}")

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    st.error(f"⏳ Límite de cuota alcanzado en {f.name}. Espera un momento antes de reintentar.")
                elif "404" in error_msg:
                    st.error(f"🚫 Error de modelo (404). El nombre del modelo ha cambiado en tu región.")
                else:
                    st.error(f"Error en {f.name}: {error_msg[:100]}")

    if resultados:
        # --- ESTRUCTURA DE 21 COLUMNAS ---
        df_raw = pd.DataFrame(resultados)
        cols_finales = [f"Columna_{i}" for i in range(1, 22)]
        df_final = pd.DataFrame(columns=cols_finales)
        
        mapeo = {
            0: ("Nombre_Completo", "Nombre_Final"),
            4: ("Direccion", "Direccion"),
            5: ("Codigo_Postal", "Codigo_Postal"),
            6: ("Ciudad", "Ciudad"),
            7: ("Telefono_1", "Telefono_1"),
            8: ("Correo_Electronico", "Correo_Electronico"),
            9: ("NIT", "NIT"),
            10: ("Tipo_Contribuyente", "Tipo_Contribuyente"),
            20: ("Actividad_Econ", "Actividad_Economica")
        }
        
        for idx, (header, campo) in mapeo.items():
            if campo in df_raw.columns:
                df_final.iloc[:, idx] = df_raw[campo]
            df_final.columns.values[idx] = header
        
        # Limpieza de actividad
        if "Actividad_Econ" in df_final.columns:
            df_final["Actividad_Econ"] = df_final["Actividad_Econ"].apply(lambda x: "".join(re.findall(r'\d+', str(x))))

        st.success("✅ Extracción terminada.")
        st.dataframe(df_final)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Excel", buf.getvalue(), "RUT_Extraido.xlsx")
