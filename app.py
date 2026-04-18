import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import re

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="RUT AI Extractor Pro", layout="wide", page_icon="📑")

if "limpiar_count" not in st.session_state:
    st.session_state.limpiar_count = 0

def ejecutar_limpieza():
    st.session_state.limpiar_count += 1

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🔒 Seguridad y Privacidad")
    st.warning("1. Sin Almacenamiento.\n2. Sesión Volátil.\n3. Privacidad Total.")
    st.info("💡 **Recomendación:** Carga máximo 5 archivos.")
    st.button("🧹 Limpiar Todo", on_click=ejecutar_limpieza)
    st.divider()
    st.caption("Motor: Gemini 3 Flash | v.2026")

st.title("📑 Extractor de RUT Inteligente")

# --- 2. API CONFIG ---
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Falta API Key en Secrets.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 3. CARGA DE ARCHIVOS ---
files = st.file_uploader(
    "Sube los archivos RUT (PDF)", 
    type="pdf", 
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.limpiar_count}"
)

if files and len(files) > 5:
    st.error("⚠️ Máximo 5 archivos.")
    st.stop()

if files and st.button("🚀 Iniciar Procesamiento"):
    resultados = []
    
    # Intentamos forzar el uso de Gemini 1.5 Flash si el 3 da problemas de legibilidad
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    for f in files:
        with st.spinner(f"Analizando {f.name}..."):
            try:
                # RESET DEL PUNTERO DEL ARCHIVO
                f.seek(0)
                pdf_data = f.read()
                
                # PROMPT REFORZADO PARA ARCHIVOS "DIFÍCILES"
                prompt = """
                Eres un sistema OCR avanzado. Analiza la PRIMERA PÁGINA de este RUT.
                Incluso si el archivo parece protegido o tiene firmas digitales, extrae el texto visible.
                Genera este JSON plano:
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
                Si no puedes leer un campo, deja "". Responde SOLO el JSON.
                """
                
                # ENVIAR COMO BYTES DIRECTOS
                response = model.generate_content([
                    {'mime_type': 'application/pdf', 'data': pdf_data},
                    prompt
                ])
                
                # Limpieza de la respuesta de texto
                raw_text = response.text
                json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                
                if json_match:
                    data = json.loads(json_match.group())
                    
                    # Unificación de nombre
                    if data.get("Razon_Social") and data["Razon_Social"].strip():
                        data["Nombre_Final"] = data["Razon_Social"]
                    else:
                        partes = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                                 data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                        data["Nombre_Final"] = " ".join([n for n in partes if n]).strip()
                    
                    resultados.append(data)
                else:
                    st.error(f"La IA no pudo estructurar los datos de {f.name}")

            except Exception as e:
                st.error(f"Error técnico en {f.name}: {str(e)[:100]}")

    if resultados:
        # --- ESTRUCTURA DE 21 COLUMNAS ---
        df_raw = pd.DataFrame(resultados)
        cols_finales = [f"Columna_{i}" for i in range(1, 22)]
        df_final = pd.DataFrame(columns=cols_finales)
        
        mapeo = {
            0: ("Nombre_Completo", "Nombre_Final"),
            4: ("Direccion", "Direccion"),
            5: ("Codigo_Postal", "Codigo_Postal"),
            6: ("Ciudad", "Ciudad"),
            7: ("Telefono_1", "Telefono_1"),
            8: ("Correo_Electronico", "Correo_Electronico"),
            9: ("NIT", "NIT"),
            10: ("Tipo_Contribuyente", "Tipo_Contribuyente"),
            20: ("Actividad_Econ", "Actividad_Economica")
        }
        
        for idx, (header, campo) in mapeo.items():
            if campo in df_raw.columns:
                df_final.iloc[:, idx] = df_raw[campo]
            df_final.columns.values[idx] = header
        
        # Limpieza de actividad
        if "Actividad_Econ" in df_final.columns:
            df_final["Actividad_Econ"] = df_final["Actividad_Econ"].apply(lambda x: "".join(re.findall(r'\d+', str(x))))

        st.success("✅ Procesamiento terminado.")
        st.dataframe(df_final)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Excel", buf.getvalue(), "RUT_Extraido.xlsx")
