import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io

st.set_page_config(page_title="RUT AI Extractor", page_icon="📑", layout="wide")
st.title("📑 Extractor de RUT Personalizado")

# --- 1. CONFIGURACIÓN DE API ---
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Error: Configura 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 2. MOTOR DE IA ---
@st.cache_resource
def get_model():
    return genai.GenerativeModel('gemini-1.5-pro')

# --- 3. INTERFAZ Y PROCESAMIENTO ---
files = st.file_uploader("Sube tus RUTs (PDF)", type="pdf", accept_multiple_files=True)

if files and st.button("🚀 Procesar Documentos"):
    resultados = []
    model = get_model()
    
    for f in files:
        with st.spinner(f"Analizando {f.name}..."):
            try:
                # Prompt con instrucción de Primera Página e índices específicos
                prompt = """
                Analiza ÚNICAMENTE la PRIMERA PÁGINA de este documento RUT. 
                Ignora cualquier información que se encuentre en las páginas 2 en adelante.
                
                Extrae la información en este formato JSON estricto:
                {
                  "NIT": "casilla 5",
                  "Tipo_Contribuyente": "Persona Jurídica o Persona Natural",
                  "Razon_Social": "casilla 35",
                  "Primer_Apellido": "casilla 31",
                  "Segundo_Apellido": "casilla 32",
                  "Primer_Nombre": "casilla 33",
                  "Otros_Nombres": "casilla 34",
                  "Ciudad": "casilla 40 (solo texto)",
                  "Direccion": "casilla 41",
                  "Correo_Electronico": "casilla 42",
                  "Telefono_1": "casilla 44",
                  "Actividad_Economica": "casilla 46 (solo los 4 dígitos)",
                  "Codigo_Postal": "casilla 43"
                }
                
                IMPORTANTE: Si la casilla 35 tiene datos, es una empresa. 
                Responde ÚNICAMENTE el JSON plano.
                """
                
                content = f.read()
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': content}
                ])
                
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(res_text)
                
                # Unificación de Nombre
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
        # 1. Crear DataFrame base
        df_raw = pd.DataFrame(resultados)
        
        # 2. Crear DataFrame de 21 columnas (Índices del 1 al 21)
        df_final = pd.DataFrame(columns=range(1, 22))
        
        # 3. Mapeo a posiciones exactas solicitadas
        mapeo = {
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
        
        for col_index, field_name in mapeo.items():
            if field_name in df_raw.columns:
                df_final[col_index] = df_raw[field_name]
            else:
                df_final[col_index] = ""

        # Opcional: Renombrar para que el usuario vea qué es cada columna en la web
        df_final = df_final.rename(columns=mapeo)

        st.success("✅ Extracción terminada (Solo primera página procesada).")
        st.dataframe(df_final)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Excel Estructurado", output.getvalue(), "RUT_Final_Estructurado.xlsx")
