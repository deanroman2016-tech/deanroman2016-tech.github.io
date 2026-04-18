import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Extractor RUT IA", page_icon="📄", layout="centered")

st.title("📄 Extractor Inteligente de RUT")
st.markdown("""
Esta aplicación utiliza **Gemini 1.5 Pro** para extraer datos de PDFs del RUT de forma precisa, 
eliminando automáticamente el texto legal y las etiquetas de las casillas.
""")

# --- CONFIGURACIÓN DE API (USANDO SECRETS) ---
# Si estás probando local, puedes reemplazar st.secrets por tu llave entre comillas
try:
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        api_key = st.sidebar.text_input("Ingresa tu Google API Key:", type="password")
    
    if api_key:
        genai.configure(api_key=api_key)
    else:
        st.warning("⚠️ Falta la API Key. Configúrala en los Secrets de Streamlit o en la barra lateral.")
        st.stop()
except Exception as e:
    st.error("Error al configurar la API Key.")
    st.stop()

# --- INTERFAZ DE CARGA ---
uploaded_files = st.file_uploader("Sube uno o varios archivos RUT (PDF)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    if st.button("🚀 Procesar y Generar Excel"):
        all_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        model = genai.GenerativeModel('gemini-1.5-pro')

        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"Procesando: {uploaded_file.name}...")
            
            try:
                # Leer el PDF
                pdf_content = uploaded_file.read()
                
                # PROMPT MAESTRO
                prompt = """
                Analiza este documento RUT y extrae la información ÚNICAMENTE en formato JSON plano.
                No incluyas explicaciones, saludos ni bloques de código markdown.
                
                Mapeo de campos (Extrae solo el valor, elimina etiquetas como 'Primer Apellido'):
                - NIT: Casilla 5 (solo números).
                - Tipo: 'Persona Natural' o 'Persona Jurídica'.
                - Apellido1: Casilla 31.
                - Apellido2: Casilla 32.
                - Nombre1: Casilla 33.
                - OtrosNombres: Casilla 34.
                - Ciudad: Nombre del municipio (Casilla 40).
                - Depto: Nombre del departamento (Casilla 39).
                - Direccion: Casilla 41.
                - Correo: Email válido encontrado.
                - Tel1: Teléfono principal.
                - Actividad: Código de 4 dígitos (Casilla 46).
                """

                # Llamada a la IA
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': pdf_content}
                ])
                
                # Limpieza de la respuesta (por si trae markdown ```json)
                text_response = response.text.strip()
                if "```json" in text_response:
                    text_response = text_response.split("```json")[1].split("```")[0].strip()
                elif "```" in text_response:
                    text_response = text_response.split("```")[1].split("```")[0].strip()
                
                # Convertir a diccionario
                data_dict = json.loads(text_response)
                all_results.append(data_dict)
                
            except Exception as e:
                st.error(f"Error en {uploaded_file.name}: {str(e)}")
            
            progress_bar.progress((i + 1) / len(uploaded_files))

        status_text.text("✅ Procesamiento completado.")

        if all_results:
            # Crear DataFrame y mostrar vista previa
            df = pd.DataFrame(all_results)
            st.subheader("Vista previa de los datos")
            st.dataframe(df)

            # Crear Excel en memoria
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Datos_RUT')
            
            # Botón de descarga
            st.download_button(
                label="📥 Descargar Excel Consolidado",
                data=output.getvalue(),
                file_name="RUT_Consolidado_IA.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# --- NOTA DE PRIVACIDAD ---
st.info("Nota: Los archivos se procesan en memoria y no se guardan permanentemente en el servidor.")
