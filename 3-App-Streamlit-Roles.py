
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
        id_finca = st.text_input("ID Finca (Obligatorio para Vigilancia/Planta) Ej: 06 o FIN-001")
        # Password field
        password = st.text_input("Contraseña Finca / Usuario", type="password", help="Para Vigilancia: pide clave a Oficina Central. Oficina Central usa clave maestra")
        
        # Diccionario de claves simples (puedes moverlo a Google Sheets hoja Usuarios)
        CLAVES_FINCAS = {
            "06": "06",
            "FIN-001": "finca001",
            "FIN-002": "finca002",
            "FIN-003": "finca003",
            "OFICINA_CENTRAL": "admin123",
            "JEFE_PLANTA": "planta123"
        }
        # También aceptar clave maestra
        CLAVE_MAESTRA = "Banano2026"
        
        if st.button("Entrar"):
            id_finca = id_finca.strip()
            # Validaciones de seguridad
            if rol in ["VIGILANCIA", "JEFE_PLANTA"] and not id_finca:
                st.error("❌ Debes poner ID Finca. No puedes entrar en blanco. Ej: 06")
            elif rol in ["VIGILANCIA", "JEFE_PLANTA"] and not password:
                st.error("❌ Debes poner contraseña de la finca")
            else:
                # Validar finca existe y clave
                df_fincas_check, _ = get_df_safe("Fincas")
                finca_valida = True
                if rol in ["VIGILANCIA", "JEFE_PLANTA"]:
                    if not df_fincas_check.empty:
                        # Si hay catalogo de fincas, verificar que exista
                        existe = df_fincas_check['id_finca'].astype(str).str.upper().str.contains(id_finca.upper(), na=False).any()
                        if not existe and id_finca.upper() != "TODAS":
                            # Si no existe en catalogo, permitir solo con clave maestra
                            if password != CLAVE_MAESTRA:
                                st.error(f"❌ Finca {id_finca} no existe en catálogo. Pide alta a Oficina Central")
                                finca_valida = False
                            else:
                                finca_valida = True
                        else:
                            finca_valida = True
                    
                    # Validar contraseña
                    if finca_valida:
                        clave_esperada = CLAVES_FINCAS.get(id_finca, CLAVES_FINCAS.get(id_finca.upper(), None))
                        # Si no está en diccionario, aceptar clave = mismo ID o clave maestra
                        if password == CLAVE_MAESTRA or password == id_finca or (clave_esperada and password == clave_esperada):
                            st.session_state.rol = rol
                            st.session_state.id_finca = id_finca
                            st.rerun()
                        else:
                            st.error("❌ Contraseña incorrecta para esa finca. Pide clave a Oficina Central")
                else:
                    # Oficina Central
                    if password == CLAVE_MAESTRA or password == CLAVES_FINCAS.get("OFICINA_CENTRAL"):
                        st.session_state.rol = rol
                        st.session_state.id_finca = id_finca or "OFICINA"
                        st.rerun()
                    else:
                        st.error("❌ Contraseña incorrecta. Clave maestra: Banano2026 (cámbiala en código)")
    else:
        st.success(f"{st.session_state.rol} | {st.session_state.id_finca}")
        if st.button("Salir"):
            st.session_state.rol = None
            st.session_state.id_finca = None
            st.rerun()
    st.divider()
    st.caption(f"Fotos Drive: {FOTOS_FOLDER_ID}")


if st.session_state.rol is None:
    st.title("Bienvenido - Sistema de Embarque Banano")
    st.markdown("### ¡Sistema en linea!")
    st.info("Oficina Central crea ordenes. Vigilancia entrada/salida. Planta despacho, thermografo, filtro, firma.")
    st.markdown("---")
    st.caption("Selecciona Rol, ID Finca y Contraseña en la barra lateral para entrar")
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
    st.title(f"🚧 Vigilancia - Finca {st.session_state.id_finca or 'TODAS'}")
    st.markdown("**Automático por finca - solo órdenes pendientes de TU finca**")
    
    df_orden_fin, _ = get_df_safe("Orden_Fincas")
    df_ordenes, _ = get_df_safe("OrdenesCarga")
    
    if df_orden_fin.empty:
        st.warning("No hay órdenes en sistema aún. Oficina Central debe crear una.")
        st.stop()
    
    # Filtrar por finca del vigilante
    id_finca_vig = (st.session_state.id_finca or "").strip()
    if id_finca_vig and id_finca_vig.upper() != "TODAS":
        df_filtrada = df_orden_fin[df_orden_fin['id_finca'].astype(str).str.upper() == id_finca_vig.upper()]
        # Si no encuentra por mayusculas exactas, probar contiene (para 06 vs FIN-06)
        if df_filtrada.empty:
            df_filtrada = df_orden_fin[df_orden_fin['id_finca'].astype(str).str.contains(id_finca_vig, na=False)]
    else:
        df_filtrada = df_orden_fin
        id_finca_vig = "TODAS"
    
    if df_filtrada.empty:
        st.info(f"No hay órdenes pendientes para tu finca: {id_finca_vig}")
        st.dataframe(df_orden_fin.tail(20), use_container_width=True)
        st.stop()
    
    # Solo pendientes (no EN_FINCA, no CARGADO_SALIO)
    df_pendientes = df_filtrada[~df_filtrada['estado_carga'].isin(['CARGADO_SALIO','CARGADO'])]
    df_en_finca = df_filtrada[df_filtrada['estado_carga'] == 'EN_FINCA']
    
    st.success(f"📍 Tu finca: {id_finca_vig} | Pendientes: {len(df_pendientes)} | En finca: {len(df_en_finca)}")
    
    # Mostrar pendientes automáticamente
    if not df_pendientes.empty:
        st.subheader(f"🚛 Órdenes PENDIENTES para {id_finca_vig} (automático)")
        for idx, row in df_pendientes.iterrows():
            id_orden = row['id_orden']
            # Buscar datos de la orden
            info_orden = df_ordenes[df_ordenes['id_orden']==id_orden] if not df_ordenes.empty else pd.DataFrame()
            operador = info_orden.iloc[0]['id_operador'] if not info_orden.empty else "?"
            tractor = info_orden.iloc[0]['id_tractor'] if not info_orden.empty else "?"
            caja1 = info_orden.iloc[0]['id_caja1'] if not info_orden.empty else "?"
            
            with st.container(border=True):
                col_info, col_btn1, col_btn2 = st.columns([3,1,1])
                with col_info:
                    st.markdown(f"**{id_orden}**")
                    st.caption(f"Finca: {row['id_finca']} | Op: {operador} | Tractor: {tractor} | Caja: {caja1} | Estado: {row['estado_carga']}")
                with col_btn1:
                    if st.button(f"✅ ENTRADA", key=f"ent_{id_orden}_{row['id_finca']}_{idx}", type="primary", use_container_width=True):
                        try:
                            try:
                                ws_bit = sh.worksheet("Bitacora_Vigilancia")
                            except:
                                ws_bit = sh.add_worksheet(title="Bitacora_Vigilancia", rows=1000, cols=10)
                                ws_bit.append_row(["id_bitacora","id_orden","id_finca","tipo_movimiento","fecha_hora","hora_manual","odometro","observaciones","id_usuario","fotos_links"])
                            append_row_dict_safe(ws_bit, {
                                "id_bitacora": f"ENT-{id_orden}-{datetime.now().strftime('%H%M%S')}",
                                "id_orden": id_orden,
                                "id_finca": row['id_finca'],
                                "tipo_movimiento": "ENTRADA",
                                "fecha_hora": datetime.now().isoformat(),
                                "hora_manual": datetime.now().strftime('%H:%M'),
                                "odometro": "",
                                "observaciones": "",
                                "id_usuario": f"VIG-{id_finca_vig}",
                                "fotos_links": ""
                            })
                            ws_of = sh.worksheet("Orden_Fincas")
                            # Actualizar exactamente esta fila
                            all_recs = ws_of.get_all_records()
                            for r_idx, r in enumerate(all_recs, start=2):
                                if r.get('id') == row.get('id') or (r.get('id_orden')==id_orden and r.get('id_finca')==row['id_finca']):
                                    ws_of.update_cell(r_idx, 5, "EN_FINCA")
                                    break
                            st.success(f"Entrada {id_orden} registrada {datetime.now().strftime('%H:%M')}")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                with col_btn2:
                    if st.button(f"📤 SALIDA", key=f"sal_{id_orden}_{row['id_finca']}_{idx}", use_container_width=True):
                        st.warning("Primero debe registrar ENTRADA, está aún PENDIENTE")
    else:
        st.info(f"No hay pendientes para {id_finca_vig}")
    
    # Mostrar EN_FINCA para poder sacarlos
    if not df_en_finca.empty:
        st.divider()
        st.subheader(f"📦 Unidades EN FINCA {id_finca_vig} - Listas para SALIDA")
        for idx, row in df_en_finca.iterrows():
            id_orden = row['id_orden']
            with st.container(border=True):
                col_info, col_btn = st.columns([3,1])
                with col_info:
                    st.markdown(f"**{id_orden}** - EN FINCA desde entrada")
                    st.caption(f"Finca: {row['id_finca']} | Estado: EN_FINCA")
                with col_btn:
                    if st.button(f"✅ SALIDA", key=f"sal_en_{id_orden}_{row['id_finca']}_{idx}", type="secondary", use_container_width=True):
                        try:
                            try:
                                ws_bit = sh.worksheet("Bitacora_Vigilancia")
                            except:
                                ws_bit = sh.add_worksheet(title="Bitacora_Vigilancia", rows=1000, cols=10)
                                ws_bit.append_row(["id_bitacora","id_orden","id_finca","tipo_movimiento","fecha_hora","hora_manual","odometro","observaciones","id_usuario","fotos_links"])
                            append_row_dict_safe(ws_bit, {
                                "id_bitacora": f"SAL-{id_orden}-{datetime.now().strftime('%H%M%S')}",
                                "id_orden": id_orden,
                                "id_finca": row['id_finca'],
                                "tipo_movimiento": "SALIDA",
                                "fecha_hora": datetime.now().isoformat(),
                                "hora_manual": datetime.now().strftime('%H:%M'),
                                "odometro": "",
                                "observaciones": "",
                                "id_usuario": f"VIG-{id_finca_vig}",
                                "fotos_links": ""
                            })
                            ws_of = sh.worksheet("Orden_Fincas")
                            all_recs = ws_of.get_all_records()
                            for r_idx, r in enumerate(all_recs, start=2):
                                if r.get('id') == row.get('id') or (r.get('id_orden')==id_orden and r.get('id_finca')==row['id_finca']):
                                    ws_of.update_cell(r_idx, 5, "CARGADO_SALIO")
                                    break
                            # Cerrar orden si es ultima
                            try:
                                df_of = pd.DataFrame(ws_of.get_all_records())
                                pendientes = df_of[(df_of['id_orden']==id_orden) & (~df_of['estado_carga'].isin(['CARGADO_SALIO','CARGADO']))]
                                if pendientes.empty:
                                    ws_oc = sh.worksheet("OrdenesCarga")
                                    cell_oc = ws_oc.find(id_orden)
                                    ws_oc.update_cell(cell_oc.row, 11, "CERRADA")
                                    st.info("¡Última finca! Orden CERRADA")
                            except:
                                pass
                            st.success(f"Salida {id_orden} - {datetime.now().strftime('%H:%M')}")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
    
    with st.expander("📜 Historial de hoy - tu finca"):
        df_bit, _ = get_df_safe("Bitacora_Vigilancia")
        if not df_bit.empty and id_finca_vig != "TODAS":
            df_bit = df_bit[df_bit['id_finca'].astype(str).str.contains(id_finca_vig, na=False)]
        st.dataframe(df_bit.tail(30), use_container_width=True)



elif st.session_state.rol == "JEFE_PLANTA":
    st.title(f"Planta - {st.session_state.id_finca}")
    cantidad = st.text_input("Cajas (TEXTO) para respetar 06", value="450")
    if st.button("Cerrar Despacho Finca"):
        st.success("Despacho creado. Si es ultima finca, orden CERRADA")
