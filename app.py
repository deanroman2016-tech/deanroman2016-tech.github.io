import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io

st.set_page_config(page_title="RUT Extractor Pro", page_icon="📑", layout="wide")

st.title("📑 Extractor de RUT Inteligente (Multiformato)")
st.markdown("Soporta **Persona Jurídica** y **Persona Natural**. Extrae datos limpios listos para contabilidad.")

# --- 1. CONFIGURACIÓN DE API ---
try:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
except Exception:
    st.error("🔑 Error: Configura la 'GOOGLE_API_KEY' en los Secrets de Streamlit.")
    st.stop()

# --- 2. MOTOR DE IA ---
@st.cache_resource
def get_model():
    # Buscamos la mejor versión disponible en 2026
    return genai.GenerativeModel('gemini-1.5-pro')

# --- 3. LÓGICA DE EXTRACCIÓN ---
files = st.file_uploader("Sube uno o varios archivos RUT (PDF)", type="pdf", accept_multiple_files=True)

if files and st.button("🚀 Procesar Documentos"):
    resultados = []
    model = get_model()
    
    for f in files:
        with st.spinner(f"Analizando {f.name}..."):
            try:
                # Prompt diseñado para distinguir entre Natural y Jurídica
                prompt = """
                Analiza el RUT adjunto y extrae los datos exactamente en este formato JSON:
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
                  "Correo": "casilla 42",
                  "Telefono": "casilla 44 o 45",
                  "Actividad_Principal": "casilla 46 (solo los 4 dígitos)",
                  "Codigo_Postal": "casilla 43"
                }
                IMPORTANTE: 
                - Si es Persona Jurídica, las casillas de nombres (31-34) estarán vacías.
                - Si es Persona Natural, la casilla de Razón Social (35) estará vacía.
                - No incluyas etiquetas como 'Primer Apellido' dentro del valor, solo el dato real.
                """
                
                pdf_data = f.read()
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': pdf_data}
                ])
                
                # Limpiar la respuesta de la IA
                clean_json = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(clean_json)
                
                # CREAR CAMPO UNIFICADO PARA EL NOMBRE (Para que el Excel sea fácil de leer)
                if data.get("Razon_Social"):
                    data["Nombre_Completo_o_Empresa"] = data["Razon_Social"]
                else:
                    partes = [data.get("Primer_Nombre", ""), data.get("Otros_Nombres", ""), 
                              data.get("Primer_Apellido", ""), data.get("Segundo_Apellido", "")]
                    data["Nombre_Completo_o_Empresa"] = " ".join([p for p in partes if p]).strip()
                
                resultados.append(data)
            except Exception as e:
                st.warning(f"No se pudo extraer {f.name}. Error: {str(e)}")

    if resultados:
        df = pd.DataFrame(resultados)
        
        # Reordenar columnas para que sea profesional
        cols = ["NIT", "Nombre_Completo_o_Empresa", "Tipo_Contribuyente", "Ciudad", "Departamento", "Actividad_Principal", "Direccion", "Correo", "Telefono"]
        # Filtrar solo las que existen
        df_final = df[[c for c in cols if c in df.columns]]
        
        st.success("✅ Extracción completada.")
        st.dataframe(df_final)
        
        # Generar el archivo Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False, sheet_name='Base_Datos_RUT')
        
        st.download_button(
            label="📥 Descargar Excel Consolidado",
            data=output.getvalue(),
            file_name="RUT_Consolidado_Pro.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
