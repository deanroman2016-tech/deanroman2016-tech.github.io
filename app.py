import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io

st.set_page_config(page_title="RUT AI Extractor", page_icon="📑", layout="wide")
st.title("📑 Extractor de RUT Inteligente")

# --- 1. CONFIGURACIÓN DE API ---
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Error: Configura 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 2. MOTOR DE IA CON SELECCIÓN INTELIGENTE ---
@st.cache_resource
def get_model():
    # Buscamos modelos que soporten generación de contenido y archivos
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    # Prioridades para 2026
    opciones = ['models/gemini-1.5-pro', 'models/gemini-1.5-pro-latest', 'models/gemini-pro']
    for opcion in opciones:
        if opcion in available_models:
            return genai.GenerativeModel(opcion)
    # Si no encuentra ninguno de los anteriores, usa el primero disponible
    return genai.GenerativeModel(available_models[0])

# --- 3. INTERFAZ Y LÓGICA ---
files = st.file_uploader("Sube tus RUTs (PDF)", type="pdf", accept_multiple_files=True)

if files and st.button("🚀 Procesar Documentos"):
    resultados = []
    model = get_model()
    
    for f in files:
        with st.spinner(f"Analizando {f.name}..."):
            try:
                # Prompt pulido para detectar ambos tipos de contribuyente
                prompt = """
                Analiza este RUT y extrae los datos en este JSON exacto:
                {
                  "NIT": "casilla 5",
                  "Tipo_Contribuyente": "Persona Jurídica o Persona Natural",
                  "Razon_Social": "casilla 35",
                  "Primer_Apellido": "casilla 31",
                  "Segundo_Apellido": "casilla 32",
                  "Primer_Nombre": "casilla 33",
                  "Otros_Nombres": "casilla 34",
                  "Ciudad": "casilla 40 (solo el nombre)",
                  "Actividad": "casilla 46 (solo los 4 números)"
                }
                IMPORTANTE: Si la casilla 35 tiene datos (Empresa), Razon_Social es prioritaria.
                Responde ÚNICAMENTE el JSON plano.
                """
                
                content = f.read()
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': content}
                ])
                
                # Limpiador de Markdown
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(res_text)
                
                # Unificación de Nombre para el Excel
                if data.get("Razon_Social"):
                    data["Nombre_Completo"] = data["Razon_Social"]
                else:
                    n = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                         data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                    data["Nombre_Completo"] = " ".join([p for p in n if p]).strip()
                
                resultados.append(data)
            except Exception as e:
                st.error(f"Error en {f.name}: El modelo no está disponible o el archivo es ilegible.")

    if resultados:
        df = pd.DataFrame(resultados)
        # Columnas finales ordenadas
        cols_finales = ["NIT", "Nombre_Completo", "Tipo_Contribuyente", "Ciudad", "Actividad"]
        df_display = df[[c for c in cols_finales if c in df.columns]]
        
        st.success("✅ Procesamiento terminado.")
        st.dataframe(df_display)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Excel", output.getvalue(), "RUT_Procesado.xlsx")
