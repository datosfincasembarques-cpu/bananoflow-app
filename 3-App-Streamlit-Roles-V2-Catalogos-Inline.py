
"""
3 - APP BANANO FLOW - V2 con Catalogos inline en Crear Orden
Oficina Central: Crear operador, tracto, caja, cliente, destino, finca SIN salir de la pantalla
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
        return pd.DataFrame(ws.get_all_records()), ws
    except Exception as e:
        return pd.DataFrame(), None

def append_row_dict_safe(ws, data_dict):
    headers = ws.row_values(1)
    row = [data_dict.get(h, "") for h in headers]
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
    tab1, tab2, tab3 = st.tabs(["📦 Crear Orden Carga (TODO AQUI)", "📄 Guias Stock", "📊 Despachos y Catalogos"])
    
    with tab1:
        st.subheader("Nueva Orden de Carga - Todo a la mano")
        st.markdown("Si llega operador o carro nuevo, agrégalo aquí mismo sin salir a Sheets.")
        
        # Cargar catalogos
        df_op, ws_op = get_df_safe("Operadores")
        df_tr, ws_tr = get_df_safe("Tractos")
        df_cj, ws_cj = get_df_safe("Cajas")
        df_cli, ws_cli = get_df_safe("Clientes")
        df_des, ws_des = get_df_safe("Destinos")
        df_fin, ws_fin = get_df_safe("Fincas")

        # --- CATALOGOS INLINE ---
        with st.expander("➕ CATALOGOS RAPIDOS - Agregar Operador / Tracto / Caja / Cliente / Destino / Finca aquí mismo", expanded=False):
            colA, colB, colC = st.columns(3)
            with colA:
                st.markdown("**Nuevo Operador**")
                with st.form("form_op"):
                    id_op = st.text_input("ID Operador ej: OP-003")
                    nombre_op = st.text_input("Nombre")
                    lic_op = st.text_input("Licencia")
                    tel_op = st.text_input("Tel")
                    if st.form_submit_button("Guardar Operador"):
                        if ws_op is not None and id_op:
                            append_row_dict_safe(ws_op, {"id_operador": id_op, "nombre": nombre_op, "licencia": lic_op, "telefono": tel_op, "activo": "TRUE"})
                            st.success(f"{id_op} guardado"); st.cache_data.clear(); st.rerun()
            with colB:
                st.markdown("**Nuevo Tracto**")
                with st.form("form_tr"):
                    id_tr = st.text_input("ID Tracto ej: TRAC-03")
                    placa_tr = st.text_input("Placa")
                    econ_tr = st.text_input("No. Economico")
                    marca_tr = st.text_input("Marca")
                    if st.form_submit_button("Guardar Tracto"):
                        if ws_tr is not None and id_tr:
                            append_row_dict_safe(ws_tr, {"id_tractor": id_tr, "placa": placa_tr, "no_economico": econ_tr, "marca": marca_tr, "activo": "TRUE"})
                            st.success(f"{id_tr} guardado"); st.rerun()
            with colC:
                st.markdown("**Nueva Caja**")
                with st.form("form_cj"):
                    id_cj = st.text_input("ID Caja ej: CAJA-03")
                    placa_cj = st.text_input("Placa Caja")
                    tipo_cj = st.selectbox("Tipo", ["SECA", "REFRIGERADA"])
                    cap_cj = st.number_input("Capacidad cajas", value=1300)
                    if st.form_submit_button("Guardar Caja"):
                        if ws_cj is not None and id_cj:
                            append_row_dict_safe(ws_cj, {"id_caja": id_cj, "placa": placa_cj, "tipo": tipo_cj, "capacidad_cajas": cap_cj, "activo": "TRUE"})
                            st.success(f"{id_cj} guardado"); st.rerun()
            st.divider()
            colD, colE, colF = st.columns(3)
            with colD:
                st.markdown("**Nuevo Cliente**")
                with st.form("form_cli"):
                    id_cli = st.text_input("ID Cliente ej: CLI-03")
                    nom_cli = st.text_input("Nombre Cliente")
                    rfc_cli = st.text_input("RFC")
                    if st.form_submit_button("Guardar Cliente"):
                        if ws_cli is not None and id_cli:
                            append_row_dict_safe(ws_cli, {"id_cliente": id_cli, "nombre": nom_cli, "rfc": rfc_cli, "activo": "TRUE"})
                            st.success(f"{id_cli} guardado"); st.rerun()
            with colE:
                st.markdown("**Nuevo Destino**")
                with st.form("form_des"):
                    id_des = st.text_input("ID Destino ej: DEST-03")
                    nom_des = st.text_input("Ciudad / Destino")
                    pais_des = st.text_input("Pais", value="USA")
                    if st.form_submit_button("Guardar Destino"):
                        if ws_des is not None and id_des:
                            append_row_dict_safe(ws_des, {"id_destino": id_des, "nombre": nom_des, "pais": pais_des, "activo": "TRUE"})
                            st.success(f"{id_des} guardado"); st.rerun()
            with colF:
                st.markdown("**Nueva Finca**")
                with st.form("form_fin"):
                    id_fin = st.text_input("ID Finca ej: FIN-004")
                    nom_fin = st.text_input("Nombre Finca")
                    tipo_fin = st.selectbox("Tipo Finca", ["PROPIA", "TERCERO"])
                    emp_fin = st.text_input("Empresa")
                    if st.form_submit_button("Guardar Finca"):
                        if ws_fin is not None and id_fin:
                            append_row_dict_safe(ws_fin, {"id_finca": id_fin, "nombre": nom_fin, "tipo": tipo_fin, "empresa": emp_fin, "direccion": "", "tiene_camara_frio": "FALSE", "encargado": "", "activa": "TRUE"})
                            st.success(f"{id_fin} guardado"); st.rerun()

        st.divider()
        # FORMULARIO ORDEN
        col1, col2 = st.columns(2)
        with col1:
            # Listas dinamicas
            ops = df_op['id_operador'].tolist() if not df_op.empty and 'id_operador' in df_op.columns else []
            trs = df_tr['id_tractor'].tolist() if not df_tr.empty and 'id_tractor' in df_tr.columns else []
            cjs = df_cj['id_caja'].tolist() if not df_cj.empty and 'id_caja' in df_cj.columns else []
            
            operador = st.selectbox("Operador", ops if ops else ["OP-001"])
            tractor = st.selectbox("Tracto", trs if trs else ["TRAC-01"])
            caja1 = st.selectbox("Caja 1", cjs if cjs else ["CAJA-01"])
            caja2 = st.selectbox("Caja 2 (Full opcional)", [""] + cjs)
            
            # Mostrar detalles rapidos
            if not df_op.empty:
                det_op = df_op[df_op['id_operador']==operador]
                if not det_op.empty:
                    st.caption(f"Lic: {det_op.iloc[0].get('licencia','')} | {det_op.iloc[0].get('nombre','')}")
        with col2:
            fincas_opts = df_fin['id_finca'].tolist() if not df_fin.empty and 'id_finca' in df_fin.columns else ["FIN-001","FIN-002","FIN-003"]
            fincas = st.multiselect("Fincas a cargar (orden de visita)", fincas_opts)
            clientes_opts = df_cli['id_cliente'].tolist() if not df_cli.empty and 'id_cliente' in df_cli.columns else ["CLI-01"]
            destinos_opts = df_des['id_destino'].tolist() if not df_des.empty and 'id_destino' in df_des.columns else ["DEST-01"]
            cliente = st.selectbox("Cliente", clientes_opts)
            destino = st.selectbox("Destino", destinos_opts)
            folio_factura = st.text_input("Folio Factura")
            lote_override = st.text_input("Lote (opcional, si lo dejas vacio se autogenera)")

        if st.button("✅ Generar Orden + Lote + Ruta", type="primary"):
            if conectado and fincas:
                try:
                    id_orden = f"OC-{datetime.now().strftime('%Y%m%d%H%M')}-{operador}"
                    ws_ord, _ = get_df_safe("OrdenesCarga")
                    ws_ord_obj = sh.worksheet("OrdenesCarga")
                    row = { "id_orden": id_orden, "folio_orden": id_orden, "fecha_creacion": datetime.now().isoformat(), "id_usuario_crea": "OFICINA_CENTRAL", "id_operador": operador, "id_tractor": tractor, "id_caja1": caja1, "id_caja2": caja2, "id_cliente": cliente, "id_destino": destino, "id_lote": lote_override if lote_override else f"LOTE-{id_orden}", "estado": "ABIERTA", "ruta_fincas_ids": ",".join(fincas) }
                    append_row_dict_safe(ws_ord_obj, row)
                    # Ruta
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
            st.info("No hay stock - Registra compra en Google Sheets o desde aqui")
            with st.form("compra_guias"):
                cant = st.number_input("Cantidad juegos (ej 20)", value=20)
                precio = st.number_input("Precio unitario", value=150.0)
                folio = st.text_input("Folio compra AAPS")
                if st.form_submit_button("Registrar compra 20 juegos"):
                    try:
                        ws_comp = sh.worksheet("Compra_Guias")
                        ws_stock = sh.worksheet("Guias_Folios_Stock")
                        id_compra = f"COMP-{datetime.now().strftime('%Y%m%d%H%M')}"
                        append_row_dict_safe(ws_comp, {"id_compra": id_compra, "fecha_compra": datetime.now().isoformat(), "cantidad_juegos": cant, "precio_unitario": precio, "importe_total": cant*precio, "folio_compra_AAPS": folio, "estado": "DISPONIBLE"})
                        tipos = ["R","E","P","D4","D5"]
                        for tipo in tipos:
                            for i in range(1, cant+1):
                                folio_str = f"{tipo}{i:02d}" if tipo in ["R","E","P"] else f"{tipo}-{i:02d}"
                                append_row_dict_safe(ws_stock, {"id_folio": f"{id_compra}-{tipo}-{i}", "id_compra": id_compra, "tipo_documento": tipo, "folio": folio_str, "estado": "DISPONIBLE", "id_orden": "", "id_asignacion": ""})
                        st.success(f"Compra {id_compra} registrada - {cant*5} folios")
                    except Exception as e:
                        st.error(str(e))

    with tab3:
        st.subheader("Catálogos y Despachos")
        for nombre in ["Operadores","Tractos","Cajas","Clientes","Destinos","Fincas","OrdenesCarga","Despachos"]:
            df, _ = get_df_safe(nombre)
            with st.expander(f"{nombre} ({len(df)})"):
                st.dataframe(df)

elif st.session_state.rol == "VIGILANCIA":
    st.title(f"🚧 Vigilancia / Caseta - Finca {st.session_state.id_finca}")
    st.markdown("Registra ENTRADA cuando llega y SALIDA cuando se va cargado.")
    
    df_orden_fin, _ = get_df_safe("Orden_Fincas")
    df_ord, _ = get_df_safe("OrdenesCarga")
    
    # Mostrar ordenes de su finca
    if not df_orden_fin.empty and st.session_state.id_finca:
        filtradas = df_orden_fin[df_orden_fin['id_finca']==st.session_state.id_finca]
        # Unir con datos de orden
        if not df_ord.empty and not filtradas.empty:
            merged = filtradas.merge(df_ord, on='id_orden', how='left')
            st.dataframe(merged[['id_orden','id_finca','orden_visita','estado_carga','id_operador','id_tractor','id_caja1','estado']].tail(20))
        else:
            st.dataframe(filtradas)
    else:
        st.info("No hay ordenes para esta finca aun")
    
    st.divider()
    tab_entrada, tab_salida = st.tabs(["📥 REGISTRAR ENTRADA", "📤 REGISTRAR SALIDA"])
    
    with tab_entrada:
        st.subheader("Entrada de Unidad Vacia")
        col1, col2 = st.columns(2)
        with col1:
            orden_sel = st.selectbox("Selecciona Orden", df_orden_fin['id_orden'].unique().tolist() if not df_orden_fin.empty else ["OC-..."], key="ord_ent")
            hora_ent = st.time_input("Hora Entrada")
            km_ent = st.text_input("Kilometraje / Odometro entrada")
        with col2:
            foto_tractor_ent = st.file_uploader("Foto Tractor (placas)", key="foto_t_ent")
            foto_caja_ent = st.file_uploader("Foto Caja (placas)", key="foto_c_ent")
            foto_lic_ent = st.file_uploader("Foto Licencia Operador", key="foto_lic_ent")
            obs_ent = st.text_area("Observaciones entrada (ej: caja sucia, llanta baja)")
        
        if st.button("✅ Registrar ENTRADA", type="primary"):
            try:
                ws_bit = sh.worksheet("Bitacora_Vigilancia")
                # Crear registro entrada
                append_row_dict_safe(ws_bit, {
                    "id_bitacora": f"ENT-{orden_sel}-{datetime.now().strftime('%H%M%S')}",
                    "id_orden": orden_sel,
                    "id_finca": st.session_state.id_finca,
                    "tipo_movimiento": "ENTRADA",
                    "fecha_hora": datetime.now().isoformat(),
                    "hora_manual": str(hora_ent),
                    "odometro": km_ent,
                    "observaciones": obs_ent,
                    "id_usuario": f"VIG-{st.session_state.id_finca}",
                    "fotos_links": ""
                })
                # Actualizar estado en Orden_Fincas a EN_FINCA
                ws_of = sh.worksheet("Orden_Fincas")
                try:
                    cell = ws_of.find(f"{orden_sel}-{st.session_state.id_finca}")
                    ws_of.update_cell(cell.row, 5, "EN_FINCA") # estado_carga
                except:
                    pass
                st.success(f"Entrada {orden_sel} registrada {datetime.now().strftime('%H:%M')} - Unidad en finca")
                st.balloons()
            except Exception as e:
                st.error(f"Error: {e} - Asegurate que existe hoja Bitacora_Vigilancia")

    with tab_salida:
        st.subheader("Salida de Unidad Cargada")
        col1, col2 = st.columns(2)
        with col1:
            orden_sal = st.selectbox("Selecciona Orden (cargada)", df_orden_fin['id_orden'].unique().tolist() if not df_orden_fin.empty else ["OC-..."], key="ord_sal")
            hora_sal = st.time_input("Hora Salida")
            sellos = st.text_input("No. Sellos / Precintos")
            cajas_sal = st.number_input("Cajas que se lleva (verificar con Planta)", value=0)
        with col2:
            foto_sellos = st.file_uploader("Foto Sellos / Precintos", key="foto_sellos")
            foto_caja_cargada = st.file_uploader("Foto Caja Cargada / Cerrada", key="foto_c_sal")
            foto_temp = st.file_uploader("Foto Thermografo (opcional)", key="foto_temp_sal")
            obs_sal = st.text_area("Observaciones salida")
        
        if st.button("✅ Registrar SALIDA", type="primary"):
            try:
                ws_bit = sh.worksheet("Bitacora_Vigilancia")
                append_row_dict_safe(ws_bit, {
                    "id_bitacora": f"SAL-{orden_sal}-{datetime.now().strftime('%H%M%S')}",
                    "id_orden": orden_sal,
                    "id_finca": st.session_state.id_finca,
                    "tipo_movimiento": "SALIDA",
                    "fecha_hora": datetime.now().isoformat(),
                    "hora_manual": str(hora_sal),
                    "odometro": sellos,
                    "observaciones": f"Cajas:{cajas_sal} {obs_sal}",
                    "id_usuario": f"VIG-{st.session_state.id_finca}",
                    "fotos_links": ""
                })
                ws_of = sh.worksheet("Orden_Fincas")
                try:
                    cell = ws_of.find(f"{orden_sal}-{st.session_state.id_finca}")
                    ws_of.update_cell(cell.row, 5, "CARGADO_SALIO")
                except:
                    pass
                st.success(f"Salida {orden_sal} registrada - {cajas_sal} cajas - Sellos {sellos}")
                # Verificar si es ultima finca
                try:
                    df_of = pd.DataFrame(ws_of.get_all_records())
                    pendientes = df_of[(df_of['id_orden']==orden_sal) & (~df_of['estado_carga'].isin(['CARGADO_SALIO','CARGADO']))]
                    if pendientes.empty:
                        ws_oc = sh.worksheet("OrdenesCarga")
                        cell_oc = ws_oc.find(orden_sal)
                        ws_oc.update_cell(cell_oc.row, 11, "CERRADA") # estado
                        st.info("¡Era la ultima finca! Orden CERRADA automaticamente")
                except:
                    pass
            except Exception as e:
                st.error(f"Error: {e}")

    # Historial
    with st.expander("📜 Historial Entradas/Salidas de hoy"):
        df_bit, _ = get_df_safe("Bitacora_Vigilancia")
        if not df_bit.empty:
            if st.session_state.id_finca:
                df_bit = df_bit[df_bit['id_finca']==st.session_state.id_finca]
            st.dataframe(df_bit.tail(30))


elif st.session_state.rol == "JEFE_PLANTA":
    st.title(f"Planta - {st.session_state.id_finca}")
    cantidad = st.number_input("Cajas", value=450)
    if st.button("Cerrar Despacho Finca"):
        st.success("Despacho creado. Si es ultima finca, orden CERRADA")
