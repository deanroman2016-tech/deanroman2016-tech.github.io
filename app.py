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

# --- 2. FUNCIÓN DE EXTRACCIÓN ---
def extraer_datos_rut(file_content):
    # Intentamos con gemini-1.5-pro que es el más estable para PDFs
    model = genai.GenerativeModel('gemini-1.5-pro')
    
    prompt = """
    Analiza este RUT y extrae los datos en este formato JSON exacto:
    {
      "NIT": "",
      "Tipo_Contribuyente": "",
      "Razon_Social": "",
      "Primer_Apellido": "",
      "Segundo_Apellido": "",
      "Primer_Nombre": "",
      "Otros_Nombres": "",
      "Pais": "",
      "Departamento": "",
      "Ciudad": "",
      "Direccion": "",
      "Correo": "",
      "Telefono": "",
      "Actividad_Principal": "",
      "Codigo_Postal": ""
    }
    Instrucciones:
    1. Si es Persona Jurídica, usa la casilla 35 para Razon_Social.
    2. Si es Persona Natural, usa 31-34 para nombres.
    3. Extrae solo el valor, no etiquetas.
    4. Responde SOLO el JSON.
    """
    
    response = model.generate_content([
        prompt,
        {'mime_type': 'application/pdf', 'data': file_content}
    ])
    return response.text

# --- 3. INTERFAZ ---
files = st.file_uploader("Sube tus RUTs (PDF)", type="pdf", accept_multiple_files=True)

if files and st.button("🚀 Procesar Documentos"):
    resultados = []
    
    for f in files:
        with st.spinner(f"Procesando {f.name}..."):
            try:
                # Leemos el archivo
                content = f.read()
                res_text = extraer_datos_rut(content)
                
                # Limpieza de JSON
                if "```json" in res_text:
                    res_text = res_text.split("```json")[1].split("```")[0].strip()
                elif "```" in res_text:
                    res_text = res_text.split("```")[1].split("```")[0].strip()
                
                data = json.loads(res_text)
                
                # Nombre unificado para el Excel
                if data.get("Razon_Social"):
                    data["Nombre_Completo"] = data["Razon_Social"]
                else:
                    n = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                    data["Nombre_Completo"] = " ".join([p for p in n if p]).strip()
                
                resultados.append(data)
            except Exception as e:
                st.error(f"Error en {f.name}: {str(e)}")

    if resultados:
        df = pd.DataFrame(resultados)
        # Reordenar columnas clave
        cols = ["NIT", "Nombre_Completo", "Tipo_Contribuyente", "Ciudad", "Actividad_Principal", "Direccion", "Correo"]
        df_final = df[[c for c in cols if c in df.columns] + [c for c in df.columns if c not in cols]]
        
        st.success("✅ ¡Hecho!")
        st.dataframe(df_final)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Excel", output.getvalue(), "RUT_Procesado.xlsx")
