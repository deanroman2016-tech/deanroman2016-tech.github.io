import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io

# Configuración de página
st.set_page_config(page_title="RUT Extractor v2026", layout="wide")
st.title("📑 Extractor RUT - Formato Estricto 21 Columnas")

# --- 1. CONFIGURACIÓN DE API ---
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Error: Configura 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 2. PROCESAMIENTO ---
files = st.file_uploader("Sube tus RUTs (PDF)", type="pdf", accept_multiple_files=True)

if files and st.button("🚀 Procesar"):
    resultados = []
    
    # Forzamos Gemini 1.5 Flash que tiene mayor disponibilidad y menos errores 404
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    for f in files:
        with st.spinner(f"Leyendo {f.name}..."):
            try:
                # Prompt con las nuevas restricciones de página e índices
                prompt = """
                Analiza EXCLUSIVAMENTE la PRIMERA PÁGINA de este RUT.
                Extrae estos datos en un JSON plano:
                {
                  "NIT": "casilla 5",
                  "Tipo_Contribuyente": "Persona Jurídica o Persona Natural",
                  "Razon_Social": "casilla 35",
                  "Primer_Apellido": "casilla 31",
                  "Segundo_Apellido": "casilla 32",
                  "Primer_Nombre": "casilla 33",
                  "Otros_Nombres": "casilla 34",
                  "Ciudad": "casilla 40 (solo el nombre del municipio)",
                  "Direccion": "casilla 41",
                  "Correo_Electronico": "casilla 42",
                  "Telefono_1": "casilla 44",
                  "Actividad_Economica": "casilla 46 (solo los 4 dígitos)",
                  "Codigo_Postal": "casilla 43"
                }
                Si la casilla 35 tiene texto, úsala como nombre principal. Responde solo JSON.
                """
                
                content = f.read()
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': content}
                ])
                
                # Limpiar y cargar JSON
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(res_text)
                
                # Lógica de Nombre para la Columna 1
                if data.get("Razon_Social"):
                    data["Nombre_Final"] = data["Razon_Social"]
                else:
                    n = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                         data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                    data["Nombre_Final"] = " ".join([p for p in n if p]).strip()
                
                resultados.append(data)
            except Exception as e:
                st.error(f"Error procesando {f.name}: {str(e)}")

    if resultados:
        # --- ESTRUCTURA DE 21 COLUMNAS ---
        df_raw = pd.DataFrame(resultados)
        
        # Creamos el DataFrame con columnas del 1 al 21
        df_excel = pd.DataFrame(columns=range(1, 22))
        
        # Mapeo según tus instrucciones exactas
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
        
        # Llenar las columnas específicas
        for col_num, campo in mapeo.items():
            if campo in df_raw.columns:
                df_excel[col_num] = df_raw[campo]
            else:
                df_excel[col_num] = ""
        
        # Renombrar solo para visualización
        df_excel.columns = [mapeo.get(i, f"Columna_{i}") for i in df_excel.columns]

        st.success("✅ Extracción exitosa.")
        st.dataframe(df_excel)
        
        # Exportar a Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_excel.to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Excel", output.getvalue(), "RUT_Estructurado.xlsx")
