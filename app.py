import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io

st.set_page_config(page_title="RUT AI Fix", page_icon="🔧")
st.title("🔧 Extractor RUT - Versión Estable")

# --- 1. CONFIGURACIÓN DE API ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("🔑 API KEY no configurada en Secrets.")
    st.stop()

# --- 2. DETECCIÓN AUTOMÁTICA DE MODELO (Solución al error NotFound) ---
@st.cache_resource # Para no repetir esto en cada clic
def get_best_model():
    try:
        # Listamos los modelos que TU API KEY tiene permitidos
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # Prioridad de modelos para 2026
        prioridades = [
            'models/gemini-2.0-pro-exp-02-05', # Versión específica Pro
            'models/gemini-1.5-pro-latest',    # Versión estable Pro
            'models/gemini-1.5-pro',           # Respaldo total
            'models/gemini-1.5-flash'          # Última opción (rápida)
        ]
        
        for p in prioridades:
            if p in models:
                return p
        return models[0] if models else None
    except Exception as e:
        return "models/gemini-1.5-pro" # Fallback manual

target_model = get_best_model()
st.caption(f"Usando motor: {target_model}")

# --- 3. PROCESAMIENTO ---
files = st.file_uploader("Sube tus RUTs", type="pdf", accept_multiple_files=True)

if files and st.button("Extraer"):
    resultados = []
    # Usamos el nombre del modelo detectado dinámicamente
    model = genai.GenerativeModel(target_model)
    
    for f in files:
        with st.spinner(f"Leyendo {f.name}..."):
            try:
                # Prompt reforzado para JSON
                prompt = "Extrae del RUT: NIT (casilla 5), Apellido1 (31), Apellido2 (32), Nombre1 (33), OtrosNombres (34), Ciudad (40), Actividad (46). Responde SOLO JSON puro."
                
                # Leemos el contenido del archivo
                pdf_data = f.read()
                
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': pdf_data}
                ])
                
                # Limpiador de texto para evitar errores de formato
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                resultados.append(json.loads(res_text))
            except Exception as e:
                st.warning(f"No se pudo leer {f.name}. Error: {str(e)}")

    if resultados:
        df = pd.DataFrame(resultados)
        st.dataframe(df)
        
        # Generación de Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        
        st.download_button("Descargar Excel", buffer.getvalue(), "RUT_IA.xlsx")
