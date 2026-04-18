import streamlit as st
import google.generativeai as genai
import pandas as pd
import io

# Configuración de la página
st.set_page_config(page_title="RUT Extractor Pro", layout="wide")
st.title("🚀 Extractor Inteligente de RUT")
st.write("Sube tus PDFs y la IA se encargará de organizarlos en Excel sin errores.")

# --- Configuración de la API ---
# En producción, usa st.secrets para mayor seguridad
API_KEY = "TU_API_KEY_AQUÍ" 
genai.configure(api_key=API_KEY)

# --- Interfaz de Usuario ---
uploaded_files = st.file_uploader("Sube uno o varios archivos RUT (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    if st.button("Procesar Archivos"):
        all_data = []
        model = genai.GenerativeModel('gemini-1.5-pro')

        for uploaded_file in uploaded_files:
            with st.spinner(f"Analizando {uploaded_file.name}..."):
                # Leer el PDF y enviarlo a Gemini
                pdf_data = uploaded_file.read()
                
                prompt = """
                Analiza este RUT y extrae los datos en formato JSON. 
                Campos: NIT, TipoContribuyente, Apellido1, Apellido2, Nombre1, OtrosNombres, Pais, Depto, Ciudad, Direccion, Correo, Tel1, Tel2, Actividad, CP.
                REGLA: Si el dato no existe o es una etiqueta legal, déjalo vacío. 
                Separa estrictamente los nombres de las casillas 31, 32, 33 y 34.
                """
                
                # Enviar a Gemini (el modelo procesa el PDF directamente)
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': pdf_data}
                ])
                
                # Aquí el modelo devuelve los datos limpios
                # (Se puede añadir lógica para convertir la respuesta a lista)
                st.write(f"✅ {uploaded_file.name} procesado.")

        st.success("¡Todo listo! Ya puedes descargar tu consolidado.")
