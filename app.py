import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import re

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="RUT AI Extractor Pro", layout="wide", page_icon="📑")

# --- BARRA LATERAL (SEGURIDAD Y PRIVACIDAD) ---
with st.sidebar:
    st.header("🔒 Seguridad y Privacidad")
    st.warning("""
    **Aviso Importante:**
    1. **Sin Almacenamiento:** Los archivos no se guardan en bases de datos.
    2. **Sesión Volátil:** Si cierras la pestaña, los datos se borran.
    3. **Privacidad Total:** Procesamiento en memoria RAM temporal.
    """)
    
    # RECOMENDACIÓN DE CARGA MÁXIMA
    st.info("💡 **Recomendación:** Para garantizar la estabilidad del servicio gratuito, carga un **máximo de 5 archivos** por cada tanda de procesamiento.")
    
    st.divider()
    st.caption("Motor: Gemini 3 Flash Preview | v.2026")

st.title("📑 Extractor de RUT Inteligente")
st.subheader("Procesamiento seguro de primera página")

# --- 2. CONFIGURACIÓN DE API ---
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Error: API Key no detectada en los Secrets de Streamlit.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 3. CARGA DE ARCHIVOS CON VALIDACIÓN ---
files = st.file_uploader("Sube los archivos RUT (PDF - Máx. 10MB c/u)", type="pdf", accept_multiple_files=True)

# Validación de cantidad simultánea
if files:
    if len(files) > 5:
        st.error(f"⚠️ Has subido {len(files)} archivos. Por favor, sube máximo 5 para evitar errores de saturación.")
        st.stop()

if files and st.button("🚀 Iniciar Procesamiento Seguro"):
    resultados = []
    
    # Selección de modelo
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
                Ignora cualquier página adicional.
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
                    data["Nombre_Empresa_Persona"] = data["Razon_Social"]
                else:
                    partes = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                             data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                    data["Nombre_Empresa_Persona"] = " ".join([n for n in partes if n]).strip()
                
                resultados.append(data)

            except Exception as e:
                st.error(f"Error en {f.name}: {str(e)[:100]}...")

    if resultados:
        # --- ESTRUCTURA RÍGIDA DE 21 COLUMNAS ---
        df_raw = pd.DataFrame(resultados)
        df_final = pd.DataFrame(columns=range(1, 22))
        
        mapeo_columnas = {
            1: "Nombre_Empresa_Persona", 5: "Direccion", 6: "Codigo_Postal", 
            7: "Ciudad", 8: "Telefono_1", 9: "Correo_Electronico", 
            10: "NIT", 11: "Tipo_Contribuyente", 21: "Actividad_Economica"
        }
        
        for col_id, campo_ia in mapeo_columnas.items():
            if campo_ia in df_raw.columns:
                df_final[col_id] = df_raw[campo_ia]
        
        # Limpieza de código de actividad
        if 21 in df_final.columns:
            def extraer_codigo(val):
                nums = re.findall(r'\d+', str(val))
                return nums[0] if nums else ""
            df_final[21] = df_final[21].apply(extraer_codigo)

        st.success("✅ Procesamiento completado.")
        st.dataframe(df_final.rename(columns=mapeo_columnas))
        
        # Generación de Excel
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Descargar Excel (21 Columnas)",
            data=buf.getvalue(),
            file_name="RUT_Extraido.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
