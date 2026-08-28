
"""
3 - APP BANANO FLOW - V3.1 con IDs como TEXTO, limpiar forms, editar/eliminar catalogos
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

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

def get_df_safe(sheet_name):
    try:
        ws = sh.worksheet(sheet_name)
        # Force all data as string to preserve 06 -> "06"
        records = ws.get_all_records()
        df = pd.DataFrame(records, dtype=str)
        return df, ws
    except Exception as e:
        return pd.DataFrame(dtype=str), None

def append_row_dict_safe(ws, data_dict):
    # Ensure everything saved as string to preserve leading zeros
    headers = ws.row_values(1)
    row = [str(data_dict.get(h, "")) for h in headers]
    ws.append_row(row, value_input_option='USER_ENTERED')
    return True

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
    st.session_state.form_counter = 0

with st.sidebar:
    st.title("🍌 Banano Flow")
    if conectado:
        st.success(f"Conectado: {SPREADSHEET_NAME}")
    else:
        st.error(f"Error: {err_conexion if 'err_conexion' in locals() else 'revisa secrets'}")
    if st.session_state.rol is None:
        rol = st.selectbox("Rol", ROLES)
        id_finca = st.text_input("ID Finca (Vigilancia/Planta) Ej: FIN-001")
        if st.button("Entrar"):
            st.session_state.rol = rol
            st.session_state.id_finca = id_finca
            st.rerun()
    else:
        st.success(f"{st.session_state.rol} | {st.session_state.id_finca or 'TODAS'}")
        if st.button("Salir"):
            st.session_state.rol = None
            st.rerun()
    st.divider()
    st.caption(f"Fotos Drive: {FOTOS_FOLDER_ID}")

if st.session_state.rol is None:
    st.title("Bienvenido - Sistema de Embarque Banano")
    st.markdown("### ¡Sistema en linea!")
    st.info("Oficina Central crea ordenes. Vigilancia entrada/salida. Planta despacho, thermografo, filtro, firma.")
    if conectado:
        df_fincas, _ = get_df_safe("Fincas")
        if not df_fincas.empty:
            st.dataframe(df_fincas)
    st.stop()

# ================= OFICINA CENTRAL =================
if st.session_state.rol == "OFICINA_CENTRAL":
    tab1, tab2, tab3 = st.tabs(["📦 Crear Orden Carga (TODO AQUI)", "📄 Guias Stock", "📊 Catalogos - Editar/Eliminar"])
    
    with tab1:
        st.subheader("Nueva Orden de Carga - Todo a la mano")
        df_op, ws_op = get_df_safe("Operadores")
        df_tr, ws_tr = get_df_safe("Tractos")
        df_cj, ws_cj = get_df_safe("Cajas")
        df_cli, ws_cli = get_df_safe("Clientes")
        df_des, ws_des = get_df_safe("Destinos")
        df_fin, ws_fin = get_df_safe("Fincas")

        # --- CATALOGOS INLINE CON LIMPIEZA ---
        with st.expander("➕ CATALOGOS RAPIDOS - Agregar Operador / Tracto / Caja / Cliente / Destino / Finca", expanded=False):
            st.info("Todos los codigos son TEXTO - si pones 06 se guarda 06, no 6. Al guardar, el formulario se limpia solo.")
            colA, colB, colC = st.columns(3)
            with colA:
                st.markdown("**Nuevo Operador**")
                with st.form(f"form_op_{st.session_state.form_counter}", clear_on_submit=True):
                    id_op = st.text_input("ID Operador (TEXTO) ej: 06 o OP-003")
                    nombre_op = st.text_input("Nombre")
                    lic_op = st.text_input("Licencia")
                    tel_op = st.text_input("Tel")
                    if st.form_submit_button("Guardar Operador"):
                        if ws_op is not None and id_op:
                            append_row_dict_safe(ws_op, {"id_operador": id_op, "nombre": nombre_op, "licencia": lic_op, "telefono": tel_op, "activo": "TRUE"})
                            st.session_state.form_counter += 1
                            st.success(f"{id_op} guardado"); st.rerun()
            with colB:
                st.markdown("**Nuevo Tracto**")
                with st.form(f"form_tr_{st.session_state.form_counter}", clear_on_submit=True):
                    id_tr = st.text_input("ID Tracto (TEXTO) ej: 06")
                    placa_tr = st.text_input("Placa")
                    econ_tr = st.text_input("No. Economico (TEXTO)")
                    marca_tr = st.text_input("Marca")
                    if st.form_submit_button("Guardar Tracto"):
                        if ws_tr is not None and id_tr:
                            append_row_dict_safe(ws_tr, {"id_tractor": id_tr, "placa": placa_tr, "no_economico": econ_tr, "marca": marca_tr, "activo": "TRUE"})
                            st.session_state.form_counter += 1
                            st.success(f"{id_tr} guardado"); st.rerun()
            with colC:
                st.markdown("**Nueva Caja**")
                with st.form(f"form_cj_{st.session_state.form_counter}", clear_on_submit=True):
                    id_cj = st.text_input("ID Caja (TEXTO) ej: 06")
                    placa_cj = st.text_input("Placa Caja")
                    tipo_cj = st.selectbox("Tipo", ["SECA", "REFRIGERADA"])
                    cap_cj = st.text_input("Capacidad cajas (TEXTO) ej: 1300", value="1300")
                    if st.form_submit_button("Guardar Caja"):
                        if ws_cj is not None and id_cj:
                            append_row_dict_safe(ws_cj, {"id_caja": id_cj, "placa": placa_cj, "tipo": tipo_cj, "capacidad_cajas": cap_cj, "activo": "TRUE"})
                            st.session_state.form_counter += 1
                            st.success(f"{id_cj} guardado"); st.rerun()
            st.divider()
            colD, colE, colF = st.columns(3)
            with colD:
                st.markdown("**Nuevo Cliente**")
                with st.form(f"form_cli_{st.session_state.form_counter}", clear_on_submit=True):
                    id_cli = st.text_input("ID Cliente (TEXTO) ej: 06")
                    nom_cli = st.text_input("Nombre Cliente")
                    rfc_cli = st.text_input("RFC")
                    if st.form_submit_button("Guardar Cliente"):
                        if ws_cli is not None and id_cli:
                            append_row_dict_safe(ws_cli, {"id_cliente": id_cli, "nombre": nom_cli, "rfc": rfc_cli, "activo": "TRUE"})
                            st.session_state.form_counter += 1
                            st.success(f"{id_cli} guardado"); st.rerun()
            with colE:
                st.markdown("**Nuevo Destino**")
                with st.form(f"form_des_{st.session_state.form_counter}", clear_on_submit=True):
                    id_des = st.text_input("ID Destino (TEXTO) ej: 06")
                    nom_des = st.text_input("Ciudad / Destino")
                    pais_des = st.text_input("Pais", value="USA")
                    if st.form_submit_button("Guardar Destino"):
                        if ws_des is not None and id_des:
                            append_row_dict_safe(ws_des, {"id_destino": id_des, "nombre": nom_des, "pais": pais_des, "activo": "TRUE"})
                            st.session_state.form_counter += 1
                            st.success(f"{id_des} guardado"); st.rerun()
            with colF:
                st.markdown("**Nueva Finca**")
                with st.form(f"form_fin_{st.session_state.form_counter}", clear_on_submit=True):
                    id_fin = st.text_input("ID Finca (TEXTO) ej: 06 o FIN-006 - Se respeta texto")
                    nom_fin = st.text_input("Nombre Finca")
                    tipo_fin = st.selectbox("Tipo Finca", ["PROPIA", "TERCERO"])
                    emp_fin = st.text_input("Empresa")
                    dir_fin = st.text_input("Direccion")
                    if st.form_submit_button("Guardar Finca"):
                        if ws_fin is not None and id_fin:
                            append_row_dict_safe(ws_fin, {"id_finca": id_fin, "nombre": nom_fin, "tipo": tipo_fin, "empresa": emp_fin, "direccion": dir_fin, "tiene_camara_frio": "FALSE", "encargado": "", "activa": "TRUE"})
                            st.session_state.form_counter += 1
                            st.success(f"Finca {id_fin} guardada como TEXTO!"); st.rerun()

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            ops = df_op['id_operador'].tolist() if not df_op.empty and 'id_operador' in df_op.columns else []
            trs = df_tr['id_tractor'].tolist() if not df_tr.empty and 'id_tractor' in df_tr.columns else []
            cjs = df_cj['id_caja'].tolist() if not df_cj.empty and 'id_caja' in df_cj.columns else []
            operador = st.selectbox("Operador", ops if ops else ["OP-001"])
            tractor = st.selectbox("Tracto", trs if trs else ["TRAC-01"])
            caja1 = st.selectbox("Caja 1", cjs if cjs else ["CAJA-01"])
            caja2 = st.selectbox("Caja 2 (Full opcional)", [""] + cjs)
        with col2:
            fincas_opts = df_fin['id_finca'].tolist() if not df_fin.empty and 'id_finca' in df_fin.columns else ["FIN-001"]
            fincas = st.multiselect("Fincas a cargar (orden de visita)", fincas_opts)
            clientes_opts = df_cli['id_cliente'].tolist() if not df_cli.empty and 'id_cliente' in df_cli.columns else ["CLI-01"]
            destinos_opts = df_des['id_destino'].tolist() if not df_des.empty and 'id_destino' in df_des.columns else ["DEST-01"]
            cliente = st.selectbox("Cliente", clientes_opts)
            destino = st.selectbox("Destino", destinos_opts)
            folio_factura = st.text_input("Folio Factura")
            lote_override = st.text_input("Lote (opcional)")

        if st.button("✅ Generar Orden + Lote + Ruta", type="primary"):
            if conectado and fincas:
                try:
                    id_orden = f"OC-{datetime.now().strftime('%Y%m%d%H%M')}-{operador}"
                    ws_ord_obj = sh.worksheet("OrdenesCarga")
                    row = { "id_orden": id_orden, "folio_orden": id_orden, "fecha_creacion": datetime.now().isoformat(), "id_usuario_crea": "OFICINA_CENTRAL", "id_operador": operador, "id_tractor": tractor, "id_caja1": caja1, "id_caja2": caja2, "id_cliente": cliente, "id_destino": destino, "id_lote": lote_override if lote_override else f"LOTE-{id_orden}", "estado": "ABIERTA", "ruta_fincas_ids": ",".join(fincas) }
                    append_row_dict_safe(ws_ord_obj, row)
                    ws_ruta = sh.worksheet("Orden_Fincas")
                    for idx, finca_id in enumerate(fincas):
                        d = {"id": f"{id_orden}-{finca_id}", "id_orden": id_orden, "id_finca": finca_id, "orden_visita": idx+1, "estado_carga": "PENDIENTE"}
                        append_row_dict_safe(ws_ruta, d)
                    st.success(f"Orden {id_orden} creada! Lote: {row['id_lote']} Ruta: {fincas}")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Selecciona al menos una finca")

    with tab2:
        st.subheader("Stock Guías (R,E,P,D4,D5)")
        df_stock, _ = get_df_safe("Guias_Folios_Stock")
        if not df_stock.empty:
            st.metric("Disponibles", len(df_stock[df_stock['estado']=='DISPONIBLE']))
            st.dataframe(df_stock.tail(100))
        else:
            st.info("No hay stock")

    with tab3:
        st.subheader("📊 Catalogos - Ver, Editar, Eliminar")
        st.warning("Edicion: Modifica directo en la tabla y dale Guardar Cambios. Para eliminar, borra la fila en la tabla y guarda. Los IDs se guardan como TEXTO para respetar 06.")
        
        for nombre in ["Fincas","Operadores","Tractos","Cajas","Clientes","Destinos"]:
            df, ws = get_df_safe(nombre)
            with st.expander(f"✏️ {nombre} ({len(df)}) - Editar / Eliminar", expanded=False):
                if not df.empty:
                    edited = st.data_editor(df, num_rows="dynamic", key=f"editor_{nombre}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"💾 Guardar Cambios {nombre}", key=f"save_{nombre}"):
                            try:
                                ws.clear()
                                # Convert all to string to preserve 06
                                edited_str = edited.astype(str)
                                ws.update([edited_str.columns.values.tolist()] + edited_str.values.tolist(), value_input_option='USER_ENTERED')
                                st.success(f"{nombre} actualizado - IDs como TEXTO preservados")
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
                    with col2:
                        if st.button(f"🔄 Recargar {nombre}", key=f"reload_{nombre}"):
                            st.rerun()
                else:
                    st.info(f"{nombre} vacio")

        st.divider()
        st.subheader("Ordenes y Despachos")
        for nombre in ["OrdenesCarga","Orden_Fincas","Despachos","Bitacora_Vigilancia"]:
            df, _ = get_df_safe(nombre)
            with st.expander(f"{nombre} ({len(df)})"):
                st.dataframe(df.tail(50))




elif st.session_state.rol == "VIGILANCIA":
    st.title(f"🚧 Vigilancia - {st.session_state.id_finca or 'TODAS'}")
    st.markdown("**Entrada y Salida con solo un botón - sin anotar nada**")
    
    df_orden_fin, _ = get_df_safe("Orden_Fincas")
    
    if not df_orden_fin.empty:
        st.dataframe(df_orden_fin.tail(20), use_container_width=True)
        orden_opts = df_orden_fin['id_orden'].unique().tolist()
    else:
        orden_opts = []
    
    st.divider()
    
    # Seleccionar orden
    orden_sel = st.selectbox("📦 Selecciona Orden", orden_opts if orden_opts else ["No hay ordenes"], key="orden_simple")
    
    if orden_sel and orden_sel != "No hay ordenes":
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📥 LLEGÓ")
            st.caption("Cuando el camión llega vacío")
            if st.button("✅ REGISTRAR ENTRADA", type="primary", use_container_width=True, key="btn_entrada_simple"):
                try:
                    try:
                        ws_bit = sh.worksheet("Bitacora_Vigilancia")
                    except:
                        ws_bit = sh.add_worksheet(title="Bitacora_Vigilancia", rows=1000, cols=10)
                        ws_bit.append_row(["id_bitacora","id_orden","id_finca","tipo_movimiento","fecha_hora","hora_manual","odometro","observaciones","id_usuario","fotos_links"])
                    append_row_dict_safe(ws_bit, {
                        "id_bitacora": f"ENT-{orden_sel}-{datetime.now().strftime('%H%M%S')}",
                        "id_orden": orden_sel,
                        "id_finca": st.session_state.id_finca or "TODAS",
                        "tipo_movimiento": "ENTRADA",
                        "fecha_hora": datetime.now().isoformat(),
                        "hora_manual": datetime.now().strftime('%H:%M'),
                        "odometro": "",
                        "observaciones": "",
                        "id_usuario": f"VIG-{st.session_state.id_finca}",
                        "fotos_links": ""
                    })
                    try:
                        ws_of = sh.worksheet("Orden_Fincas")
                        for idx, r in enumerate(ws_of.get_all_records(), start=2):
                            if r.get('id_orden') == orden_sel:
                                ws_of.update_cell(idx, 5, "EN_FINCA")
                    except:
                        pass
                    st.success(f"✅ Entrada {orden_sel} - {datetime.now().strftime('%H:%M')}")
                    st.balloons()
                except Exception as e:
                    st.error(str(e))
        
        with col2:
            st.markdown("### 📤 SE VA")
            st.caption("Cuando ya cargó y se va")
            if st.button("✅ REGISTRAR SALIDA", type="secondary", use_container_width=True, key="btn_salida_simple"):
                try:
                    try:
                        ws_bit = sh.worksheet("Bitacora_Vigilancia")
                    except:
                        ws_bit = sh.add_worksheet(title="Bitacora_Vigilancia", rows=1000, cols=10)
                        ws_bit.append_row(["id_bitacora","id_orden","id_finca","tipo_movimiento","fecha_hora","hora_manual","odometro","observaciones","id_usuario","fotos_links"])
                    append_row_dict_safe(ws_bit, {
                        "id_bitacora": f"SAL-{orden_sel}-{datetime.now().strftime('%H%M%S')}",
                        "id_orden": orden_sel,
                        "id_finca": st.session_state.id_finca or "TODAS",
                        "tipo_movimiento": "SALIDA",
                        "fecha_hora": datetime.now().isoformat(),
                        "hora_manual": datetime.now().strftime('%H:%M'),
                        "odometro": "",
                        "observaciones": "",
                        "id_usuario": f"VIG-{st.session_state.id_finca}",
                        "fotos_links": ""
                    })
                    try:
                        ws_of = sh.worksheet("Orden_Fincas")
                        for idx, r in enumerate(ws_of.get_all_records(), start=2):
                            if r.get('id_orden') == orden_sel:
                                ws_of.update_cell(idx, 5, "CARGADO_SALIO")
                        df_of = pd.DataFrame(ws_of.get_all_records())
                        pendientes = df_of[(df_of['id_orden']==orden_sel) & (~df_of['estado_carga'].isin(['CARGADO_SALIO','CARGADO']))]
                        if pendientes.empty:
                            ws_oc = sh.worksheet("OrdenesCarga")
                            cell_oc = ws_oc.find(orden_sel)
                            ws_oc.update_cell(cell_oc.row, 11, "CERRADA")
                            st.info("¡Ultima finca! Orden CERRADA")
                    except:
                        pass
                    st.success(f"✅ Salida {orden_sel} - {datetime.now().strftime('%H:%M')}")
                except Exception as e:
                    st.error(str(e))
    
    with st.expander("📜 Historial"):
        df_bit, _ = get_df_safe("Bitacora_Vigilancia")
        st.dataframe(df_bit.tail(20), use_container_width=True)



elif st.session_state.rol == "JEFE_PLANTA":
    st.title(f"Planta - {st.session_state.id_finca}")
    cantidad = st.text_input("Cajas (TEXTO) para respetar 06", value="450")
    if st.button("Cerrar Despacho Finca"):
        st.success("Despacho creado. Si es ultima finca, orden CERRADA")
