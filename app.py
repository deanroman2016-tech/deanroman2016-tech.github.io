import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io

st.set_page_config(page_title="RUT AI Extractor", page_icon="📑", layout="wide")
st.title("📑 Extractor RUT - Solo 1ra Página")

# --- 1. CONFIGURACIÓN DE API ---
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Error: Configura 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 2. MOTOR DE IA (Fallback a Flash si Pro falla) ---
def get_model():
    # Intentamos con 1.5-pro, si da 404, usamos 1.5-flash
    try:
        return genai.GenerativeModel('gemini-1.5-pro')
    except:
        return genai.GenerativeModel('gemini-1.5-flash')

# --- 3. PROCESAMIENTO ---
files = st.file_uploader("Sube tus RUTs (PDF)", type="pdf", accept_multiple_files=True)

if files and st.button("🚀 Procesar Documentos"):
    resultados = []
    model = get_model()
    
    for f in files:
        with st.spinner(f"Analizando {f.name}..."):
            try:
                # Instrucción estricta de Primera Página
                prompt = """
                Analiza EXCLUSIVAMENTE la PRIMERA PÁGINA de este RUT.
                Extrae estos datos en JSON:
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
                Si es empresa, Razon_Social es el nombre. Responde solo JSON.
                """
                
                content = f.read()
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': content}
                ])
                
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(res_text)
                
                # Unificar Nombre
                if data.get("Razon_Social"):
                    data["Nombre_Final"] = data["Razon_Social"]
                else:
                    n = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                         data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                    data["Nombre_Final"] = " ".join([p for p in n if p]).strip()
                
                resultados.append(data)
            except Exception as e:
                st.error(f"Error en {f.name}: Revisa que tu API Key tenga permisos.")

    if resultados:
        # --- LÓGICA DE 21 COLUMNAS ---
        df_raw = pd.DataFrame(resultados)
        
        # Crear estructura de 21 columnas (vacías)
        df_excel = pd.DataFrame(columns=range(1, 22))
        
        # Mapeo según tus índices exactos
        mapeo = {
            1: "Nombre_Final",
            5: "Direccion",
            6: "Codigo_Postal",
            7: "Ciudad",
            8: "Telefono_1",
            9: "Correo_Electronico",
            10: "NIT",
            11: "Tipo_Contribuyente",
            21: "Actividad_Economica"
        }
        
        for num, campo in mapeo.items():
            if campo in df_raw.columns:
                df_excel[num] = df_raw[campo]
        
        # Limpieza final de la Actividad (solo números)
        if 21 in df_excel.columns:
            df_excel[21] = df_excel[21].astype(str).str.extract('(\d+)')

        st.success("✅ Procesado con éxito.")
        st.dataframe(df_excel)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_excel.to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Excel Estructurado", output.getvalue(), "RUT_Final.xlsx")
