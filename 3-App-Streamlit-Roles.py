
"""
3 - APP BANANO FLOW - PROD conectado a Google Sheets + Drive via st.secrets
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

st.set_page_config(page_title="Banano Flow - Embarques", layout="wide", page_icon="🍌")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
FOTOS_FOLDER_ID = st.secrets["app_config"]["fotos_folder_id"] if "app_config" in st.secrets else "1AW6qmZddxQG12q4rHKQmro7Ai3RYXhAR"
SPREADSHEET_NAME = st.secrets["app_config"]["spreadsheet_name"] if "app_config" in st.secrets else "Sistema_Banano_BD"

@st.cache_resource
def get_db():
    creds_dict = dict(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    sh = client.open(SPREADSHEET_NAME)
    drive_service = build('drive', 'v3', credentials=creds)
    return client, sh, drive_service

try:
    client, sh, drive_service = get_db()
    conectado = True
except Exception as e:
    conectado = False
    err_conexion = str(e)

ROLES = ["OFICINA_CENTRAL", "VIGILANCIA", "JEFE_PLANTA"]

if 'rol' not in st.session_state:
    st.session_state.rol = None
    st.session_state.id_finca = None

with st.sidebar:
    st.title("🍌 Banano Flow")
    if conectado:
        st.success(f"Conectado: {SPREADSHEET_NAME}")
    else:
        st.error(f"Error conexion: {err_conexion if 'err_conexion' in locals() else 'revisa secrets'}")
    if st.session_state.rol is None:
        rol = st.selectbox("Rol", ROLES)
        id_finca = st.text_input("ID Finca (para Vigilancia/Planta) Ej: FIN-001")
        if st.button("Entrar"):
            st.session_state.rol = rol
            st.session_state.id_finca = id_finca
            st.rerun()
    else:
        st.success(f"Rol: {st.session_state.rol} | Finca: {st.session_state.id_finca or 'TODAS'}")
        if st.button("Salir"):
            st.session_state.rol = None
            st.rerun()
    st.divider()
    st.caption(f"Fotos: https://drive.google.com/drive/folders/{FOTOS_FOLDER_ID}")

if st.session_state.rol is None:
    st.title("Bienvenido - Sistema de Embarque Banano")
    st.markdown("### Sistema en linea!")
    st.markdown(f"**App:** https://bananoflow-app-htktgfkahsmdsww3wdjztv.streamlit.app")
    st.markdown("Por favor inicia sesion en la barra lateral.")
    st.info("Oficina Central crea ordenes. Vigilancia registra entrada/salida. Planta registra despacho, thermografo, firma operador.")
    if conectado:
        try:
            ws = sh.worksheet("Fincas")
            df = pd.DataFrame(ws.get_all_records())
            st.dataframe(df.head(20))
        except Exception as e:
            st.warning(f"No se pudo leer Fincas: {e} - Asegurate de haber creado la BD con 1_crear_estructura_BD.py")
    st.stop()

# --- OFICINA CENTRAL ---
if st.session_state.rol == "OFICINA_CENTRAL":
    tab1, tab2, tab3, tab4 = st.tabs(["📦 Crear Orden Carga", "📄 Guias Fitosanitaria (5 docs)", "🚚 Transporte", "📊 Despachos"])
    with tab1:
        st.subheader("Nueva Orden de Carga")
        col1, col2 = st.columns(2)
        with col1:
            operador = st.selectbox("Operador", ["OP-001 Juan - Lic A123", "OP-002 Pedro - Lic B456"])
            tractor = st.selectbox("Tracto", ["TRAC-01 Placa ABC123 Econ 101", "TRAC-02 Placa XYZ789 Econ 102"])
            caja1 = st.selectbox("Caja 1", ["CAJA-01 Placa CJA001", "CAJA-02 Placa CJA002"])
            caja2 = st.selectbox("Caja 2 (Full opcional)", ["", "CAJA-02 Placa CJA002"])
        with col2:
            fincas = st.multiselect("Fincas a cargar (orden de visita)", ["FIN-001 La Esperanza (PROPIA)", "FIN-002 San Jorge (TERCERO)"])
            cliente = st.selectbox("Cliente", ["CLI-01 Chiquita USA", "CLI-02 Walmart MX"])
            destino = st.selectbox("Destino", ["McAllen, TX, USA", "Tapachula, Chiapas, MX"])
            folio_factura = st.text_input("Folio Factura")
        if st.button("Generar Orden + Lote"):
            if conectado:
                try:
                    id_orden = f"OC-{datetime.now().strftime('%Y%m%d%H%M')}-{operador.split()[0]}"
                    ws = sh.worksheet("OrdenesCarga")
                    headers = ws.row_values(1)
                    row = { "id_orden": id_orden, "folio_orden": id_orden, "fecha_creacion": datetime.now().isoformat(), "id_usuario_crea": "OFICINA_CENTRAL", "id_operador": operador, "id_tractor": tractor, "id_caja1": caja1, "id_caja2": caja2, "id_cliente": cliente, "id_destino": destino, "id_lote": f"LOTE-{id_orden}", "estado": "ABIERTA", "ruta_fincas_ids": ",".join(fincas) }
                    ws.append_row([row.get(h,"") for h in headers], value_input_option='USER_ENTERED')
                    # Crear ruta en Orden_Fincas
                    ws2 = sh.worksheet("Orden_Fincas")
                    headers2 = ws2.row_values(1)
                    for idx, finca_id in enumerate(fincas):
                        d = {"id": f"{id_orden}-{finca_id}", "id_orden": id_orden, "id_finca": finca_id.split()[0], "orden_visita": idx+1, "estado_carga": "PENDIENTE"}
                        ws2.append_row([d.get(h,"") for h in headers2], value_input_option='USER_ENTERED')
                    st.success(f"Orden {id_orden} creada. Lote: LOTE-{id_orden} Ruta: {fincas}")
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.success("Modo demo: Orden creada")

    with tab2:
        st.subheader("Compra y Asignacion de Guias (R,E,P,D4,D5)")
        st.info("5 documentos por juego. Si son 2 cajas, se consumen 2 juegos. Si amparas 1300 pero despachas 1360, no hay saldo.")
        # Listar stock
        if conectado:
            try:
                ws = sh.worksheet("Guias_Folios_Stock")
                df_stock = pd.DataFrame(ws.get_all_records())
                st.metric("Folios DISPONIBLES", len(df_stock[df_stock['estado']=='DISPONIBLE']))
                st.dataframe(df_stock.head(30))
            except Exception as e:
                st.warning(f"Error leyendo stock: {e}")

    with tab3:
        st.subheader("Catalogos")
        if conectado:
            for hoja in ["Operadores","Tractos","Cajas","Clientes","Destinos","Fincas"]:
                try:
                    ws = sh.worksheet(hoja)
                    df = pd.DataFrame(ws.get_all_records())
                    with st.expander(f"{hoja} ({len(df)})"):
                        st.dataframe(df)
                except: pass

    with tab4:
        st.subheader("Despachos")
        if conectado:
            try:
                ws = sh.worksheet("Despachos")
                df = pd.DataFrame(ws.get_all_records())
                st.dataframe(df.tail(50))
            except Exception as e:
                st.write(f"No hay despachos aun: {e}")

elif st.session_state.rol == "VIGILANCIA":
    st.title(f"Caseta Vigilancia - {st.session_state.id_finca}")
    st.warning("Solo ves ordenes de tu finca")
    if conectado:
        try:
            ws = sh.worksheet("Orden_Fincas")
            df = pd.DataFrame(ws.get_all_records())
            filtradas = df[df['id_finca'] == st.session_state.id_finca] if st.session_state.id_finca else df
            st.dataframe(filtradas)
        except Exception as e:
            st.error(str(e))
    foto_t = st.file_uploader("Foto Tractor placas")
    foto_c = st.file_uploader("Foto Caja placas")
    if st.button("Registrar Entrada"):
        st.success(f"Entrada {datetime.now()} registrada")

elif st.session_state.rol == "JEFE_PLANTA":
    st.title(f"Planta Empacadora - {st.session_state.id_finca}")
    tab1, tab2 = st.tabs(["Revision Llegada", "Despacho / Carga"])
    with tab2:
        cantidad = st.number_input("Cantidad cajas", value=450)
        tipo_carton = st.selectbox("Tipo carton", ["CART-01 18.5kg", "CART-02 14kg"])
        thermografo = st.selectbox("Thermografo", ["THERMO-001 Folio T100", "THERMO-002"])
        filtro = st.selectbox("Filtro", ["FILT-01 Num 50", "FILT-02"])
        temp = st.number_input("Grado pulpa")
        firma = st.file_uploader("Firma operador")
        if st.button("Cerrar Despacho por Finca"):
            st.success("Despacho creado. Si es ultima finca, orden se cierra.")
