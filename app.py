import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="RUT Extractor 2026", page_icon="⚡")
st.title("⚡ Extractor RUT - Edición 2026")

# --- CONEXIÓN CON LA API ---
try:
    # Intenta obtener la clave de los Secrets de Streamlit
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("🔑 No se encontró la API KEY en los Secrets de Streamlit.")
    st.stop()

# --- SELECCIÓN DINÁMICA DE MODELO (Abril 2026) ---
# Intentamos usar la versión más potente disponible hoy
try:
    # Lista de modelos por orden de preferencia para extracción de PDF
    modelos_disponibles = [m.name for m in genai.list_models()]
    
    if 'models/gemini-2.5-pro-latest' in modelos_disponibles:
        target_model = 'gemini-2.5-pro-latest'
    elif 'models/gemini-2.0-pro-exp' in modelos_disponibles:
        target_model = 'gemini-2.0-pro-exp'
    else:
        target_model = 'gemini-1.5-pro' # Versión estable de respaldo
except:
    target_model = 'gemini-1.5-pro'

st.info(f"🤖 Motor activo: {target_model}")

# --- INTERFAZ ---
uploaded_files = st.file_uploader("Arrastra tus archivos RUT aquí", type="pdf", accept_multiple_files=True)

if uploaded_files and st.button("Extraer Datos"):
    resultados = []
    model = genai.GenerativeModel(target_model)
    
    for f in uploaded_files:
        with st.spinner(f"Analizando {f.name}..."):
            # Prompt optimizado para modelos 2.0/2.5
            prompt = """
            Actúa como un extractor de datos contables experto. 
            Analiza el PDF del RUT y extrae: NIT (casilla 5), Apellido1 (31), Apellido2 (32), 
            Nombre1 (33), OtrosNombres (34), Depto (39), Ciudad (40), Direccion (41), 
            Correo (42), Tel1 (43), Actividad (46).
            
            RESPUESTA EXCLUSIVA EN JSON. No incluyas texto extra ni advertencias legales.
            """
            
            response = model.generate_content([
                prompt,
                {'mime_type': 'application/pdf', 'data': f.read()}
            ])
            
            try:
                # Limpiador de formato Markdown para la respuesta de la IA
                clean_text = response.text.replace('```json', '').replace('```', '').strip()
                resultados.append(json.loads(clean_text))
            except Exception as e:
                st.error(f"Error procesando {f.name}. Verifica que sea un RUT válido.")

    if resultados:
        df = pd.DataFrame(resultados)
        st.success("¡Extracción exitosa!")
        st.dataframe(df)

        # Generar Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        
        st.download_button(
            label="⬇️ Descargar Excel",
            data=output.getvalue(),
            file_name="consolidado_rut_2026.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
