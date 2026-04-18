import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import re

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="RUT AI Extractor Pro", layout="wide", page_icon="📑")

# --- LÓGICA DE LIMPIEZA (SESSION STATE) ---
if "limpiar_count" not in st.session_state:
    st.session_state.limpiar_count = 0

def ejecutar_limpieza():
    # Incrementamos un contador para forzar un cambio de KEY en el uploader
    st.session_state.limpiar_count += 1

# --- BARRA LATERAL (SEGURIDAD Y PRIVACIDAD) ---
with st.sidebar:
    st.header("🔒 Seguridad y Privacidad")
    st.warning("""
    **Aviso Importante:**
    1. **Sin Almacenamiento:** Los archivos no se guardan en el servidor.
    2. **Sesión Volátil:** Si cierras la pestaña, los datos se borran.
    3. **Privacidad Total:** Procesamiento en memoria RAM temporal.
    """)
    
    st.info("💡 **Recomendación:** Carga un **máximo de 5 archivos** para estabilidad.")
    
    # BOTÓN DE LIMPIEZA
    st.button("🧹 Limpiar Todo", on_click=ejecutar_limpieza)

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
# El key dinámico permite resetear el componente al presionar "Limpiar"
files = st.file_uploader(
    "Sube los archivos RUT (PDF - Máx. 10MB c/u)", 
    type="pdf", 
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.limpiar_count}"
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
                st.error(f"Error en {f.name}: Archivo no legible o protegido.")

    if resultados:
        # --- ESTRUCTURA RÍGIDA DE 21 COLUMNAS ---
        df_raw = pd.DataFrame(resultados)
        
        # Crear DataFrame con nombres genéricos del 1 al 21
        cols_finales = [f"Columna_{i}" for i in range(1, 22)]
        df_final = pd.DataFrame(columns=cols_finales)
        
        # Mapeo de posiciones (Índice - 1 porque Python cuenta desde 0)
        mapeo = {
            0: ("Nombre_Completo_o_Empresa", "Nombre_Final"),
            4: ("Direccion", "Direccion"),
            5: ("Codigo_Postal", "Codigo_Postal"),
            6: ("Ciudad", "Ciudad"),
            7: ("Telefono_1", "Telefono_1"),
            8: ("Correo_Electronico", "Correo_Electronico"),
            9: ("NIT", "NIT"),
            10: ("Tipo_Contribuyente", "Tipo_Contribuyente"),
            20: ("Actividad_Economica", "Actividad_Economica")
        }
        
        # Llenar datos y renombrar encabezados específicos
        for idx, (nombre_header, campo_ia) in mapeo.items():
            if campo_ia in df_raw.columns:
                df_final.iloc[:, idx] = df_raw[campo_ia]
            
            # Cambiamos el nombre del encabezado de "Columna_X" al nombre real
            df_final.columns.values[idx] = nombre_header
        
        # Limpieza de actividad (solo números)
        if "Actividad_Economica" in df_final.columns:
            df_final["Actividad_Economica"] = df_final["Actividad_Economica"].apply(
                lambda x: "".join(re.findall(r'\d+', str(x)))
            )

        st.success("✅ Procesamiento completado.")
        st.dataframe(df_final)
        
        # Generación de Excel
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Descargar Excel Estructurado",
            data=buf.getvalue(),
            file_name="RUT_Extraido.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
