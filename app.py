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

# --- 2. SELECCIÓN DE MODELO ---
@st.cache_resource
def get_model():
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    opciones = ['models/gemini-1.5-pro', 'models/gemini-1.5-flash']
    for opcion in opciones:
        if opcion in available_models:
            return genai.GenerativeModel(opcion)
    return genai.GenerativeModel(available_models[0])

# --- 3. INTERFAZ Y PROCESAMIENTO ---
files = st.file_uploader("Sube tus RUTs (PDF)", type="pdf", accept_multiple_files=True)

if files and st.button("🚀 Procesar Documentos"):
    resultados = []
    model = get_model()
    
    for f in files:
        with st.spinner(f"Analizando {f.name}..."):
            try:
                # Prompt reforzado para no omitir campos clave
                prompt = """
                Analiza este RUT y extrae la información en este formato JSON estricto:
                {
                  "NIT": "casilla 5",
                  "Tipo_Contribuyente": "Persona Jurídica o Persona Natural",
                  "Razon_Social": "casilla 35",
                  "Primer_Apellido": "casilla 31",
                  "Segundo_Apellido": "casilla 32",
                  "Primer_Nombre": "casilla 33",
                  "Otros_Nombres": "casilla 34",
                  "Pais": "casilla 38",
                  "Departamento": "casilla 39 (solo texto)",
                  "Ciudad": "casilla 40 (solo texto)",
                  "Direccion": "casilla 41",
                  "Correo_Electronico": "casilla 42",
                  "Telefono_1": "casilla 44",
                  "Telefono_2": "casilla 45",
                  "Actividad_Economica": "casilla 46 (4 dígitos)",
                  "Codigo_Postal": "casilla 43"
                }
                IMPORTANTE: No omitas ningún campo. Si la casilla está vacía en el PDF, devuelve un texto vacío "".
                Responde ÚNICAMENTE el JSON.
                """
                
                content = f.read()
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': content}
                ])
                
                # Limpieza de JSON
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(res_text)
                
                # Unificación de Nombre (Lógica para Jurídica vs Natural)
                if data.get("Razon_Social"):
                    data["Nombre_Completo_o_Empresa"] = data["Razon_Social"]
                else:
                    partes = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                              data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                    data["Nombre_Completo_o_Empresa"] = " ".join([p for p in partes if p]).strip()
                
                resultados.append(data)
            except Exception as e:
                st.error(f"Error en {f.name}: {str(e)}")

    if resultados:
        df = pd.DataFrame(resultados)
        
        # Definimos el orden de las columnas para asegurar que aparezcan las que faltaban
        columnas_orden = [
            "NIT", 
            "Nombre_Completo_o_Empresa", 
            "Tipo_Contribuyente", 
            "Departamento", 
            "Ciudad", 
            "Direccion", 
            "Correo_Electronico", 
            "Telefono_1", 
            "Telefono_2", 
            "Actividad_Economica",
            "Codigo_Postal"
        ]
        
        # Filtramos solo las columnas que logramos extraer
        df_final = df[[c for c in columnas_orden if c in df.columns]]
        
        st.success("✅ Extracción terminada con todas las columnas.")
        st.dataframe(df_final)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Excel Completo", output.getvalue(), "RUT_Consolidado_Final.xlsx")
