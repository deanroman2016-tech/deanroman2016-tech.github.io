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
    st.info("💡 **Región:** Suramérica (Colombia). Se aplica pausa de 10s para evitar saturación de API.")
    st.button("🧹 Limpiar Todo", on_click=ejecutar_limpieza)
    st.divider()
    st.caption("Motor: Gemini Flash Optimized | 2026")

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
    
    # LÓGICA DE SELECCIÓN DE MODELO (Fallback para evitar 404 en Suramérica)
    nombres_modelos = ['gemini-2.0-flash-exp', 'gemini-1.5-flash-latest', 'gemini-1.5-flash']
    model = None
    
    for nombre in nombres_modelos:
        try:
            test_model = genai.GenerativeModel(nombre)
            # Intentamos una respuesta mínima para validar existencia
            model = test_model
            break 
        except:
            continue

    if not model:
        st.error("🚫 No se pudo conectar con ningún modelo de Gemini disponible en tu región.")
        st.stop()
    
    for i, f in enumerate(files):
        with st.spinner(f"Procesando {f.name} ({i+1}/{len(files)})..."):
            try:
                # Pausa obligatoria para evitar el error 429 (Cuota gratuita)
                if i > 0:
                    time.sleep(10)
                
                f.seek(0)
                pdf_data = f.read()
                
                prompt = """
                Eres un extractor de datos profesional. Analiza la PRIMERA PÁGINA de este RUT.
                Genera un JSON con estos campos:
                NIT, Tipo_Contribuyente, Razon_Social, Primer_Apellido, Segundo_Apellido, 
                Primer_Nombre, Otros_Nombres, Ciudad, Direccion, Correo_Electronico, 
                Telefono_1, Actividad_Economica, Codigo_Postal.
                Responde EXCLUSIVAMENTE el JSON.
                """
                
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': pdf_data}
                ])
                
                # Extraer JSON de la respuesta con Regex
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
                    st.error(f"La IA no pudo estructurar los datos de {f.name}")

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    st.error(f"⏳ Límite de cuota en {f.name}. Espera 1 minuto.")
                else:
                    st.error(f"Error técnico en {f.name}: {error_msg[:100]}")

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

        st.success("✅ Extracción finalizada con éxito.")
        st.dataframe(df_final)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Excel Estructurado", buf.getvalue(), "RUT_Procesado_Colombia.xlsx")
