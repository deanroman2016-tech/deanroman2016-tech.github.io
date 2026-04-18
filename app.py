import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import re
import time

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
    st.info("💡 **Región:** Colombia. Procesamiento optimizado para estabilidad de cuota.")
    st.button("🧹 Limpiar Todo", on_click=ejecutar_limpieza)
    st.divider()
    st.caption("Motor: Gemini Auto-Detect | v.2026")

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
    st.error("⚠️ Máximo 5 archivos por tanda.")
    st.stop()

if files and st.button("🚀 Iniciar Procesamiento"):
    resultados = []
    
    # --- LÓGICA DE AUTO-DETECCIÓN DE MODELO ---
    model = None
    # Probamos nombres en orden de modernidad para 2026
    candidatos = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-flash-8b']
    
    with st.status("Verificando conexión con Google AI...", expanded=False) as status:
        for nombre in candidatos:
            try:
                m = genai.GenerativeModel(nombre)
                # Intento de generación mínima para validar
                m.generate_content("test") 
                model = m
                st.write(f"Conectado exitosamente a: {nombre}")
                break
            except:
                continue
        
        if not model:
            st.error("No se encontraron modelos disponibles. Revisa tu API Key.")
            st.stop()
        status.update(label="Conexión establecida", state="complete")

    for i, f in enumerate(files):
        with st.spinner(f"Analizando {f.name} ({i+1}/{len(files)})..."):
            try:
                # Pausa de 10s para evitar Error 429 en plan gratuito
                if i > 0:
                    time.sleep(10)
                
                f.seek(0)
                pdf_data = f.read()
                
                prompt = """
                Analiza la PRIMERA PÁGINA de este RUT. Extrae en JSON:
                NIT, Tipo_Contribuyente, Razon_Social, Primer_Apellido, Segundo_Apellido, 
                Primer_Nombre, Otros_Nombres, Ciudad, Direccion, Correo_Electronico, 
                Telefono_1, Actividad_Economica, Codigo_Postal.
                Responde ÚNICAMENTE el objeto JSON.
                """
                
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': pdf_data}
                ])
                
                # Extraer JSON con Regex robusto
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                
                if json_match:
                    data = json.loads(json_match.group())
                    
                    # Lógica de nombre unificado
                    if data.get("Razon_Social") and str(data["Razon_Social"]).strip():
                        data["Nombre_Final"] = data["Razon_Social"]
                    else:
                        partes = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                                 data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                        data["Nombre_Final"] = " ".join([str(n) for n in partes if n]).strip()
                    
                    resultados.append(data)
                else:
                    st.error(f"Error de formato en {f.name}")

            except Exception as e:
                st.error(f"No se pudo procesar {f.name}: {str(e)[:100]}")

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
        
        # Limpieza de actividad (solo números)
        if "Actividad_Econ" in df_final.columns:
            df_final["Actividad_Econ"] = df_final["Actividad_Econ"].apply(
                lambda x: "".join(re.findall(r'\d+', str(x)))
            )

        st.success("✅ Extracción finalizada.")
        st.dataframe(df_final)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button("📥 Descargar Excel", buf.getvalue(), "RUT_Extraido_Final.xlsx")
