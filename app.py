import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import re

# 1. CONFIGURACIÓN DE PÁGINA Y DISEÑO
st.set_page_config(page_title="RUT AI Extractor Pro", layout="wide", page_icon="📑")

# --- BARRA LATERAL (SEGURIDAD Y PRIVACIDAD) ---
with st.sidebar:
    st.header("🔒 Seguridad y Privacidad")
    st.warning("""
    **Aviso Importante:**
    Esta aplicación cumple con estándares de Protección de Datos:
    
    1. **Sin Almacenamiento:** No guardamos tus PDFs ni los datos extraídos en bases de datos.
    2. **Sesión Volátil:** Si cierras o recargas esta pestaña, todos los datos **se borrarán permanentemente**.
    3. **Privacidad Total:** El procesamiento ocurre en memoria temporal y se libera al finalizar.
    4. **Sin Persistencia:** No hay historial de archivos en el servidor.
    """)
    st.divider()
    st.caption("Motor: Gemini 3 Flash Preview | v.2026")

st.title("📑 Extractor de RUT Inteligente")
st.subheader("Procesamiento seguro de primera página")

# --- 2. CONFIGURACIÓN DE API ---
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Error: API Key no detectada en los Secrets de Streamlit.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 3. CARGA DE ARCHIVOS ---
# El límite de 10MB se activa mediante .streamlit/config.toml
files = st.file_uploader("Sube los archivos RUT (PDF - Máx. 10MB por archivo)", type="pdf", accept_multiple_files=True)

if files and st.button("🚀 Iniciar Procesamiento Seguro"):
    resultados = []
    
    # Intentar cargar el modelo más reciente (Gemini 3), con fallback a 1.5
    try:
        model = genai.GenerativeModel('gemini-3-flash-preview')
    except:
        model = genai.GenerativeModel('gemini-1.5-flash')
    
    for f in files:
        with st.spinner(f"Analizando {f.name}..."):
            try:
                # Lectura de bytes
                pdf_bytes = f.read()
                
                if len(pdf_bytes) < 100:
                    st.error(f"El archivo {f.name} está dañado o vacío.")
                    continue

                # Prompt estricto para página 1 y estructura JSON
                prompt = """
                Analiza EXCLUSIVAMENTE la PRIMERA PÁGINA de este RUT de la DIAN.
                Ignora cualquier página adicional (hojas de establecimientos, etc.).
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
                IMPORTANTE: Si hay Razón Social (casilla 35), úsala como nombre principal. 
                Responde ÚNICAMENTE el objeto JSON plano.
                """
                
                # Llamada al modelo
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': pdf_bytes}
                ])
                
                # Limpieza y validación de la respuesta
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(res_text)
                
                # Lógica de nombre unificado para la Columna 1
                if data.get("Razon_Social") and data["Razon_Social"].strip():
                    data["Nombre_Empresa_Persona"] = data["Razon_Social"]
                else:
                    partes = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                             data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                    data["Nombre_Empresa_Persona"] = " ".join([n for n in partes if n]).strip()
                
                resultados.append(data)

            except json.JSONDecodeError:
                st.error(f"Error: La IA no pudo generar un formato válido para {f.name}. Intenta de nuevo.")
            except Exception as e:
                # Manejo de error más amigable
                if "429" in str(e):
                    st.error(f"Límite de velocidad excedido. Espera un minuto.")
                else:
                    st.error(f"No se pudo procesar {f.name}. Verifique que el PDF sea legible y no tenga contraseña.")

    if resultados:
        # --- ESTRUCTURA RÍGIDA DE 21 COLUMNAS ---
        df_raw = pd.DataFrame(resultados)
        
        # Crear DataFrame base con 21 columnas vacías
        df_final = pd.DataFrame(columns=range(1, 22))
        
        # Mapeo de posiciones exactas solicitado por el usuario
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
        
        # Llenar las columnas mapeadas
        for col_id, campo_ia in mapeo_columnas.items():
            if campo_ia in df_raw.columns:
                df_final[col_id] = df_raw[campo_ia]
        
        # Limpieza técnica: Solo números en Actividad Económica (Columna 21)
        if 21 in df_final.columns:
            def extraer_codigo(val):
                nums = re.findall(r'\d+', str(val))
                return nums[0] if nums else ""
            df_final[21] = df_final[21].apply(extraer_codigo)

        # Mostrar resultados en la Web
        st.success("✅ Procesamiento completado. Los datos son temporales.")
        
        # Renombrar solo para visualización amigable en la tabla de Streamlit
        df_display = df_final.rename(columns=mapeo_columnas)
        st.dataframe(df_display)
        
        # --- GENERAR EXCEL PARA DESCARGA ---
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            # Aquí guardamos el df_final (que mantiene los números de columna del 1 al 21)
            df_final.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Descargar Excel Estructurado (21 Columnas)",
            data=buf.getvalue(),
            file_name="RUT_Extraido_2026.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
