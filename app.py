import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io

# Configuración visual de la App
st.set_page_config(page_title="RUT AI Extractor 2026", layout="wide")
st.title("📑 Extractor RUT - Gemini 3 Flash")
st.markdown("Extracción estricta de **primera página** con formato de 21 columnas.")

# --- 1. CONFIGURACIÓN DE SEGURIDAD (API KEY) ---
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Falta la clave 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 2. PROCESAMIENTO CON MODELO 2026 ---
files = st.file_uploader("Sube tus archivos RUT (PDF)", type="pdf", accept_multiple_files=True)

if files and st.button("🚀 Ejecutar Extracción Inteligente"):
    resultados = []
    
    # Usamos la versión más reciente disponible en el Free Tier
    try:
        model = genai.GenerativeModel('gemini-3-flash-preview')
    except:
        # Fallback de seguridad por si la región aún no actualizó el nombre del modelo
        model = genai.GenerativeModel('gemini-1.5-flash')
    
    for f in files:
        with st.spinner(f"Gemini 3 analizando: {f.name}..."):
            try:
                # Prompt optimizado para evitar errores de campos vacíos
                prompt = """
                Analiza EXCLUSIVAMENTE la PRIMERA PÁGINA de este RUT.
                Extrae los datos en este JSON plano (si el dato no existe, deja ""):
                {
                  "NIT": "casilla 5",
                  "Tipo_Contribuyente": "Persona Jurídica o Persona Natural",
                  "Razon_Social": "casilla 35",
                  "Primer_Apellido": "casilla 31",
                  "Segundo_Apellido": "casilla 32",
                  "Primer_Nombre": "casilla 33",
                  "Otros_Nombres": "casilla 34",
                  "Ciudad": "casilla 40 (solo nombre)",
                  "Direccion": "casilla 41",
                  "Correo_Electronico": "casilla 42",
                  "Telefono_1": "casilla 44",
                  "Actividad_Economica": "casilla 46 (4 dígitos)",
                  "Codigo_Postal": "casilla 43"
                }
                Responde únicamente el JSON plano.
                """
                
                content = f.read()
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': content}
                ])
                
                # Limpieza de caracteres extra
                clean_res = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(clean_res)
                
                # Unificación de Nombre (Lógica Contable)
                if data.get("Razon_Social"):
                    data["Nombre_Final"] = data["Razon_Social"]
                else:
                    n = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                         data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                    data["Nombre_Final"] = " ".join([p for p in n if p]).strip()
                
                resultados.append(data)
            except Exception as e:
                st.error(f"No se pudo procesar {f.name}. Verifica que sea un PDF de RUT legible.")

    if resultados:
        # --- CREACIÓN DE ESTRUCTURA DE 21 COLUMNAS ---
        df_raw = pd.DataFrame(resultados)
        
        # Creamos el molde de 21 columnas (vacías)
        df_excel = pd.DataFrame(columns=range(1, 22))
        
        # Mapeo según tus índices de columna específicos
        mapeo_indices = {
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
        
        for num_col, campo_ia in mapeo_indices.items():
            if campo_ia in df_raw.columns:
                df_excel[num_col] = df_raw[campo_ia]
        
        # Limpieza de Actividad (solo los números)
        if 21 in df_excel.columns:
            df_excel[21] = df_excel[21].astype(str).str.extract('(\d+)')

        # Mostrar en pantalla con nombres amigables
        df_display = df_excel.rename(columns=mapeo_indices)
        st.success("✅ Extracción terminada.")
        st.dataframe(df_display)
        
        # Preparar Excel para descarga
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_excel.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Descargar Excel Estructurado (21 Cols)",
            data=output.getvalue(),
            file_name="RUT_Extraido_2026.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
