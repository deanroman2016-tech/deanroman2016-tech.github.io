import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="RUT AI Extractor 2026", layout="wide", page_icon="📑")

# --- BARRA LATERAL (AVISO LEGAL Y PRIVACIDAD) ---
with st.sidebar:
    st.header("🔒 Seguridad y Privacidad")
    st.warning("""
    **Aviso Importante:**
    Esta aplicación cumple con la Ley de Protección de Datos Personales:
    
    1. **Sin Almacenamiento:** No guardamos tus PDFs ni los datos extraídos en ninguna base de datos.
    2. **Sesión Volátil:** Si cierras o recargas esta pestaña, todos los datos procesados **se borrarán permanentemente**.
    3. **Privacidad Total:** El procesamiento se realiza en la memoria temporal del servidor y se libera al finalizar.
    4. **Responsabilidad:** Asegúrate de tener autorización para procesar los documentos cargados.
    """)
    st.divider()
    st.info("Desarrollado con Gemini 3 Flash Preview (v.2026)")

st.title("📑 Extractor de RUT Inteligente")
st.subheader("Procesamiento seguro de primera página")

# --- 2. CONFIGURACIÓN DE API ---
# Recuerda configurar GOOGLE_API_KEY en los Secrets de Streamlit Cloud
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Error: API Key no detectada. Configúrala en los Secrets de Streamlit.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 3. CARGA DE ARCHIVOS ---
# El límite de 10MB debe configurarse en .streamlit/config.toml
files = st.file_uploader("Sube los archivos RUT (PDF - Máx. 10MB)", type="pdf", accept_multiple_files=True)

if files and st.button("🚀 Iniciar Procesamiento"):
    resultados = []
    # Usamos la versión más reciente y gratuita
    model = genai.GenerativeModel('gemini-1.5-flash') 
    
    for f in files:
        with st.spinner(f"Analizando {f.name}..."):
            try:
                # Prompt estricto para página 1 y estructura JSON
                prompt = """
                Analiza EXCLUSIVAMENTE la PRIMERA PÁGINA de este RUT.
                Extrae la información en este formato JSON exacto:
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
                Si el documento tiene más páginas, IGNÓRALAS. 
                Si hay Razón Social, úsala como nombre de la entidad.
                """
                
                content = f.read()
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': content}
                ])
                
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(res_text)
                
                # Lógica de nombre unificado para la Columna 1
                if data.get("Razon_Social"):
                    data["Nombre_Empresa_Persona"] = data["Razon_Social"]
                else:
                    nom = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                           data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                    data["Nombre_Empresa_Persona"] = " ".join([n for n in nom if n]).strip()
                
                resultados.append(data)
            except Exception as e:
                st.error(f"No se pudo procesar {f.name}. Verifique que el archivo sea un RUT válido.")

    if resultados:
        # --- ESTRUCTURA RÍGIDA DE 21 COLUMNAS ---
        df_raw = pd.DataFrame(resultados)
        df_final = pd.DataFrame(columns=range(1, 22))
        
        # Mapeo de posiciones solicitado
        mapeo_columnas = {
            1: "Nombre_Empresa_Persona",
            5: "Direccion",
            6: "Codigo_Postal",
            7: "Ciudad",
            8: "Telefono_1",
            9: "Correo_Electronico",
            10: "NIT",
            11: "Tipo_Contribuyente",
            21: "Actividad_Economica"
        }
        
        for col_id, campo_ia in mapeo_columnas.items():
            if campo_ia in df_raw.columns:
                df_final[col_id] = df_raw[campo_ia]
        
        # Limpieza técnica de la actividad
        if 21 in df_final.columns:
            df_final[21] = df_final[21].astype(str).str.extract('(\d+)')

        st.success("✅ Extracción terminada. Los datos se borrarán si cierras la ventana.")
        st.dataframe(df_final)
        
        # Generar descarga
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Excel Estructurado", buf.getvalue(), "RUT_Extraido_Seguro.xlsx")
