import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import re

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="RUT AI Extractor Pro", layout="wide", page_icon="📑")

# --- LÓGICA DE LIMPIEZA (SESSION STATE) ---
if "limpiar" not in st.session_state:
    st.session_state.limpiar = False

def limpiar_todo():
    st.session_state.limpiar = True
    st.rerun()

# --- BARRA LATERAL (SEGURIDAD Y PRIVACIDAD) ---
with st.sidebar:
    st.header("🔒 Seguridad y Privacidad")
    st.warning("""
    **Aviso Importante:**
    1. **Sin Almacenamiento:** Los archivos no se guardan en bases de datos.
    2. **Sesión Volátil:** Si cierras la pestaña, los datos se borran.
    3. **Privacidad Total:** Procesamiento en memoria RAM temporal.
    """)
    
    st.info("💡 **Recomendación:** Carga un **máximo de 5 archivos** para garantizar la estabilidad.")
    
    # BOTÓN DE LIMPIEZA EN EL SIDEBAR
    if st.button("🧹 Limpiar Todo", on_click=limpiar_todo):
        st.write("Limpiando...")

    st.divider()
    st.caption("Motor: Gemini 3 Flash Preview | v.2026")

st.title("📑 Extractor de RUT Inteligente")
st.subheader("Procesamiento seguro de primera página")

# --- 2. CONFIGURACIÓN DE API ---
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Error: API Key no detectada en los Secrets de Streamlit.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 3. CARGA DE ARCHIVOS ---
# Si se activó la limpieza, reseteamos el key del uploader
uploader_key = "uploader_limpio" if not st.session_state.limpiar else "uploader_nuevo"
if st.session_state.limpiar:
    st.session_state.limpiar = False

files = st.file_uploader(
    "Sube los archivos RUT (PDF - Máx. 10MB c/u)", 
    type="pdf", 
    accept_multiple_files=True,
    key=uploader_key
)

# Validación de cantidad
if files and len(files) > 5:
    st.error(f"⚠️ Has subido {len(files)} archivos. Por favor, sube máximo 5.")
    st.stop()

if files and st.button("🚀 Iniciar Procesamiento Seguro"):
    resultados = []
    
    try:
        model = genai.GenerativeModel('gemini-3-flash-preview')
    except:
        model = genai.GenerativeModel('gemini-1.5-flash')
    
    for f in files:
        with st.spinner(f"Analizando {f.name}..."):
            try:
                pdf_bytes = f.read()
                
                prompt = """
                Analiza EXCLUSIVAMENTE la PRIMERA PÁGINA de este RUT de la DIAN.
                Extrae la información en este formato JSON exacto:
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
                Si hay Razón Social, úsala como nombre principal. Responde solo JSON.
                """
                
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': pdf_bytes}
                ])
                
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(res_text)
                
                # Unificación de nombre
                if data.get("Razon_Social") and data["Razon_Social"].strip():
                    data["Nombre_Final"] = data["Razon_Social"]
                else:
                    partes = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                             data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                    data["Nombre_Final"] = " ".join([n for n in partes if n]).strip()
                
                resultados.append(data)

            except Exception as e:
                st.error(f"Error en {f.name}: {str(e)[:50]}")

    if resultados:
        # --- ESTRUCTURA RÍGIDA DE 21 COLUMNAS ---
        df_raw = pd.DataFrame(resultados)
        df_final = pd.DataFrame(columns=range(1, 22))
        
        # Mapeo de posiciones y NOMBRES DE ENCABEZADOS
        mapeo_columnas = {
            1: "Nombre_Completo_o_Empresa",
            5: "Direccion",
            6: "Codigo_Postal",
            7: "Ciudad",
            8: "Telefono_1",
            9: "Correo_Electronico",
            10: "NIT",
            11: "Tipo_Contribuyente",
            21: "Actividad_Economica"
        }
        
        # Llenar datos
        for col_id, campo_ia in mapeo_columnas.items():
            col_source = "Nombre_Final" if campo_ia == "Nombre_Completo_o_Empresa" else campo_ia
            if col_source in df_raw.columns:
                df_final[col_id] = df_raw[col_source]
        
        # Limpieza de actividad
        if 21 in df_final.columns:
            df_final[21] = df_final[21].apply(lambda x: "".join(re.findall(r'\d+', str(x))))

        # ASIGNAR NOMBRES A LOS ENCABEZADOS (Reemplaza los números por los nombres en el Excel)
        df_final = df_final.rename(columns=mapeo_columnas)

        st.success("✅ Procesamiento completado.")
        st.dataframe(df_final)
        
        # Generación de Excel
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Descargar Excel con Encabezados",
            data=buf.getvalue(),
            file_name="RUT_Extraido_Final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
