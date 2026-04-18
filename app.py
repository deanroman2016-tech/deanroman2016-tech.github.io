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
    st.info("💡 **Región:** Colombia. Pausa de 10s activa para evitar error 429.")
    st.button("🧹 Limpiar Todo", on_click=ejecutar_limpieza)
    st.divider()
    st.caption("Motor: Gemini Auto-Adaptive | v.2026")

st.title("📑 Extractor de RUT Inteligente")
st.subheader("Procesamiento seguro de primera página")

# --- 2. CONFIGURACIÓN DE API ---
if "GOOGLE_API_KEY" not in st.secrets:
    st.error("🔑 Error: API Key no detectada en los Secrets de Streamlit.")
    st.stop()

genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

# --- 3. CARGA DE ARCHIVOS ---
files = st.file_uploader(
    "Sube hasta 5 archivos RUT (PDF)", 
    type="pdf", 
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.limpiar_count}"
)

if files and len(files) > 5:
    st.error("⚠️ El límite del plan gratuito es de 5 archivos.")
    st.stop()

if files and st.button("🚀 Iniciar Procesamiento Seguro"):
    resultados = []
    model = None
    
    # AUTO-DETECCIÓN DE MODELO
    try:
        modelos_disponibles = [m.name for m in genai.list_models() 
                              if 'generateContent' in m.supported_generation_methods 
                              and 'flash' in m.name.lower()]
        if modelos_disponibles:
            nombre_modelo = modelos_disponibles[0]
            model = genai.GenerativeModel(nombre_modelo)
            st.toast(f"Conectado a: {nombre_modelo}", icon="✅")
        else:
            st.error("No se encontraron modelos compatibles.")
            st.stop()
    except Exception as e:
        st.error(f"Error de conexión: {str(e)[:100]}")
        st.stop()

    for i, f in enumerate(files):
        with st.spinner(f"Analizando {f.name} ({i+1}/{len(files)})..."):
            try:
                if i > 0:
                    time.sleep(10)
                
                f.seek(0)
                pdf_data = f.read()
                
                prompt = """
                Analiza la PRIMERA PÁGINA de este RUT. Extrae en JSON:
                NIT, Tipo_Contribuyente, Razon_Social, Primer_Apellido, Segundo_Apellido, 
                Primer_Nombre, Otros_Nombres, Ciudad, Direccion, Correo_Electronico, 
                Telefono_1, Actividad_Economica, Codigo_Postal.
                Responde ÚNICAMENTE el JSON plano.
                """
                
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': pdf_data}
                ])
                
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                
                if json_match:
                    data = json.loads(json_match.group())
                    # Unificación de nombre
                    if data.get("Razon_Social") and str(data["Razon_Social"]).strip():
                        data["Nombre_Final"] = data["Razon_Social"]
                    else:
                        partes = [data.get("Primer_Nombre",""), data.get("Otros_Nombres",""), 
                                 data.get("Primer_Apellido",""), data.get("Segundo_Apellido","")]
                        data["Nombre_Final"] = " ".join([str(n) for n in partes if n]).strip()
                    
                    resultados.append(data)
                else:
                    st.error(f"Error de lectura en {f.name}")
            except Exception as e:
                st.error(f"Error en {f.name}: {str(e)[:50]}")

    if resultados:
        # --- CONSTRUCCIÓN SEGURA DEL DATAFRAME (Sin KeyErrors) ---
        # Definimos los encabezados finales
        columnas_finales = [f"Col_{i}" for i in range(1, 22)]
        
        # Mapeo de campos a sus posiciones (índice 0-20)
        mapeo_posiciones = {
            0: ("Nombre_Completo", "Nombre_Final"),
            4: ("Direccion", "Direccion"),
            5: ("Codigo_Postal", "Codigo_Postal"),
            6: ("Ciudad", "Ciudad"),
            7: ("Telefono_1", "Telefono_1"),
            8: ("Correo_Electronico", "Correo_Electronico"),
            9: ("NIT", "NIT"),
            10: ("Tipo_Contribuyente", "Tipo_Contribuyente"),
            20: ("Actividad_Economica", "Actividad_Economica")
        }

        # Creamos una lista de diccionarios para el nuevo DataFrame
        filas_limpias = []
        for res in resultados:
            fila = [""] * 21 # Fila vacía de 21 espacios
            for idx, (nombre_header, campo_json) in mapeo_posiciones.items():
                fila[idx] = res.get(campo_json, "")
            filas_limpias.append(fila)

        # Creamos el DataFrame final con los nombres de columnas ya definidos
        nombres_headers = [f"Col_{i}" for i in range(1, 22)]
        for idx, (nombre_header, _) in mapeo_posiciones.items():
            nombres_headers[idx] = nombre_header

        df_final = pd.DataFrame(filas_limpias, columns=nombres_headers)

        # Limpieza de actividad
        if "Actividad_Economica" in df_final.columns:
            df_final["Actividad_Economica"] = df_final["Actividad_Economica"].apply(
                lambda x: "".join(re.findall(r'\d+', str(x)))
            )

        st.success("✅ Extracción completada.")
        
        # Mostramos el DataFrame (Esto ya no debería dar KeyError)
        st.dataframe(df_final)
        
        # Generación de Excel
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Descargar Excel Estructurado",
            data=buf.getvalue(),
            file_name="RUT_Extraido.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
