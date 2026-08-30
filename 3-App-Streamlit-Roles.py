import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# CONFIGURACIÓN GENERAL Y CONEXIÓN A GOOGLE SHEETS
# ==========================================
st.set_page_config(page_title="Sistema de Embarque Bananero", page_icon="🍌", layout="wide")

@st.cache_resource
def conectar_sheets():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    except Exception:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sh = client.open("SistemaEmbarquesBananero")
    return sh

try:
    sh = conectar_sheets()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    st.stop()

# ==========================================
# FUNCIONES AUXILIARES
# ==========================================
def get_df_safe(nombre_hoja):
    try:
        ws = sh.worksheet(nombre_hoja)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        return df, ws
    except Exception:
        return pd.DataFrame(), None

def ensure_columns_exist(ws, columnas_requeridas):
    try:
        existentes = ws.row_values(1)
        actualizadas = False
        for col in columnas_requeridas:
            if col not in existentes:
                existentes.append(col)
                actualizadas = True
        if actualizadas:
            ws.update('A1', [existentes])
    except Exception:
        pass

def append_row_dict_safe(ws, row_dict):
    headers = ws.row_values(1)
    row_values = [str(row_dict.get(h, '')) for h in headers]
    ws.append_row(row_values)

def lista_simple_no_concat(df, col_id, col_nombre):
    if df.empty or col_id not in df.columns or col_nombre not in df.columns:
        return [], {}
    nombres, mapa = [], {}
    for _, row in df.iterrows():
        i_val = str(row[col_id])
        n_val = str(row[col_nombre])
        display_str = f"{n_val} ({i_val})"
        nombres.append(display_str)
        mapa[display_str] = row.to_dict()
    return nombres, mapa

def lista_placas_mapeo_correcto(df):
    if df.empty:
        return [], {}
    col_placa = next((c for c in df.columns if "placa" in c), None)
    col_id = next((c for c in df.columns if "id_" in c or c == "id"), None)
    if not col_placa or not col_id:
        return [], {}
    placas, mapa = [], {}
    for _, row in df.iterrows():
        p_val = str(row[col_placa])
        if p_val and p_val.lower() != 'nan':
            placas.append(p_val)
            mapa[p_val] = row.to_dict()
    return placas, mapa

# ==========================================
# INICIALIZACIÓN DE ESTADOS DE SESIÓN
# ==========================================
if 'username' not in st.session_state:
    st.session_state.username = "operador.general"
if 'nombre_usuario' not in st.session_state:
    st.session_state.nombre_usuario = "Usuario Sistema"

# ==========================================
# BARRA LATERAL - NAVEGACIÓN ESPECÍFICA POR DESPACHO
# ==========================================
st.sidebar.markdown("### 📌 Navegación de Despachos")
st.sidebar.caption("Control Operativo por Finca / Planta / Oficina")

menu_opciones = {
    '📦 Crear Orden (Planta/Bodega)': '📦 Crear Orden (Planta/Bodega)',
    '🏷️ Remisión/Factura (Oficina)': '🏷️ Remisión/Factura (Oficina)',
    '📋 Órdenes Expedidas': 'Órdenes Expedidas',
    '🗺️ Seguimiento': 'Seguimiento'
}

selected_sidebar = st.sidebar.selectbox(
    "Menú Operativo", 
    list(menu_opciones.keys()), 
    index=list(menu_opciones.values()).index(st.session_state.get('menu_oficina', '📦 Crear Orden (Planta/Bodega)')) if st.session_state.get('menu_oficina', '📦 Crear Orden (Planta/Bodega)') in menu_opciones.values() else 0
)
st.session_state.menu_oficina = menu_opciones[selected_sidebar]

st.sidebar.markdown("---")
st.sidebar.success("🟢 Base de Datos Conectada")
st.sidebar.info(f"Sesión Activa: **{st.session_state.nombre_usuario}**")

if st.sidebar.button("Cerrar Sesión", use_container_width=True):
    st.session_state.clear()
    st.rerun()

# ==========================================
# CARGA DE DATAFRAMES
# ==========================================
df_emp, _ = get_df_safe("Empresas")
df_fin, _ = get_df_safe("Fincas")
df_lin, _ = get_df_safe("LineasTransporte")
df_op, _ = get_df_safe("Operadores")
df_tr, _ = get_df_safe("Tractos")
df_tr2, _ = get_df_safe("Tractocamiones")
df_cj, _ = get_df_safe("Cajas")
df_cj2, _ = get_df_safe("Cajas_Thermoking")
df_cli, _ = get_df_safe("Clientes")
df_des, _ = get_df_safe("Destinos")

for d in [df_fin, df_tr, df_tr2, df_cj, df_cj2, df_op, df_lin, df_cli, df_des]:
    if not d.empty:
        d.columns = [str(c).strip().lower() for c in d.columns]

df_tr_u = pd.concat([df_tr, df_tr2], ignore_index=True) if not df_tr.empty and not df_tr2.empty else (df_tr if not df_tr.empty else df_tr2)
df_cj_u = pd.concat([df_cj, df_cj2], ignore_index=True) if not df_cj.empty and not df_cj2.empty else (df_cj if not df_cj.empty else df_cj2)

# ==========================================
# MÓDULO 1: CREAR ORDEN (JEFES DE PLANTA Y BODEGA)
# ==========================================
if st.session_state.menu_oficina == '📦 Crear Orden (Planta/Bodega)':
    emp_nombres, emp_mapa = lista_simple_no_concat(df_emp, "id_empresa", "razon_social")

    col_title, col_emp_top = st.columns([2, 2])
    with col_title:
        st.markdown("<h2 style='margin:0;'>Módulo Planta y Bodega</h2>", unsafe_allow_html=True)
        st.caption("Elaboración y Registro de Órdenes de Carga (Jefes de Planta / Encargados de Bodega)")
    with col_emp_top:
        st.markdown("**🏢 Empresa Expedidora (Comercializadora)**")
        emp_sel_principal = st.selectbox("Empresa", emp_nombres if emp_nombres else ["EMP-01"], key="emp_top_planta")
        emp_data_principal = emp_mapa.get(emp_sel_principal, {})
        id_emp_principal = str(emp_data_principal.get('id_empresa', '') or emp_sel_principal)
        emp_nombre_principal = str(emp_data_principal.get('razon_social', '') or emp_sel_principal)

    st.markdown("---")
    st.subheader("🚛 Configuración del Despacho y Recorrido del Camión")

    fin_todos_nombres, fin_todos_mapa = lista_simple_no_concat(df_fin, "id_finca", "nombre")
    
    col_tipo_finca = next((c for c in df_fin.columns if "tipo" in c), None) if not df_fin.empty else None
    df_fincas_propias = df_fin[df_fin[col_tipo_finca].astype(str).str.upper() == 'PROPIA'] if col_tipo_finca else df_fin
    fin_prop_nombres, fin_prop_mapa = lista_simple_no_concat(df_fincas_propias, "id_finca", "nombre")
    lin_nombres, lin_mapa = lista_simple_no_concat(df_lin, "id_linea", "razon_social")
    ops_nombres, ops_mapa = lista_simple_no_concat(df_op, "id_operador", "nombre")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fin_guia_sel = st.selectbox("Finca PROPIA Guía (Fitosanitaria)", fin_prop_nombres if fin_prop_nombres else fin_todos_nombres, key="fin_guia_p")
        fin_guia_data = fin_prop_mapa.get(fin_guia_sel, {}) or fin_todos_mapa.get(fin_guia_sel, {})
        id_fin_guia = str(fin_guia_data.get('id_finca', '') or fin_guia_sel)
    with col_f2:
        fin_ruta_sel = st.multiselect("Fincas en el Recorrido (Ruta de Carga)", fin_todos_nombres, key="fin_ruta_p")
        ids_fin_ruta = [str(fin_todos_mapa.get(fn, {}).get('id_finca', '') or fn) for fn in fin_ruta_sel]

    col_l1, col_l2 = st.columns([2, 1])
    with col_l1:
        lin_sel = st.selectbox("Línea de Transporte", lin_nombres if lin_nombres else ["LIN-01"], key="lin_p")
        lin_data = lin_mapa.get(lin_sel, {})
        id_lin = str(lin_data.get('id_linea', '') or lin_sel)
    with col_l2:
        st.text_input("ID Línea", value=id_lin, disabled=True, key="id_lin_p")

    col_id_lin_tr = next((c for c in df_tr_u.columns if "linea" in c), None) if not df_tr_u.empty else None
    df_tr_filt = df_tr_u[df_tr_u[col_id_lin_tr].astype(str).str.upper() == id_lin.upper()] if col_id_lin_tr else df_tr_u
    
    col_id_lin_cj = next((c for c in df_cj_u.columns if "linea" in c), None) if not df_cj_u.empty else None
    df_cj_filt = df_cj_u[df_cj_u[col_id_lin_cj].astype(str).str.upper() == id_lin.upper()] if col_id_lin_cj else df_cj_u

    st.markdown("#### 👤 Operador Asignado")
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        op_sel = st.selectbox("Operador", ops_nombres if ops_nombres else ["No hay operadores"], key="op_p", label_visibility="collapsed")
        op_data = ops_mapa.get(op_sel, {})
        id_op = str(op_data.get('id_operador', '') or op_sel)
    with c2: st.text_input("ID Op", value=id_op, disabled=True, key="id_op_p", label_visibility="collapsed")
    with c3: st.text_input("Licencia", value=str(op_data.get('licencia_num', '') or op_data.get('licencia', '')), disabled=True, key="lic_p", label_visibility="collapsed")
    with c4: st.text_input("Tel", value=str(op_data.get('telefono', '')), disabled=True, key="tel_p", label_visibility="collapsed")

    st.markdown(f"#### 🚛 Equipamiento - {lin_sel}")
    tr_placas, tr_mapa_placa = lista_placas_mapeo_correcto(df_tr_filt)
    cj_placas, cj_mapa_placa = lista_placas_mapeo_correcto(df_cj_filt)
    cli_nombres, cli_mapa = lista_simple_no_concat(df_cli, "id_cliente", "razon_social")
    des_nombres, des_mapa = lista_simple_no_concat(df_des, "id_destino", "ciudad")

    ct1, ct2, ct3 = st.columns(3)
    with ct1:
        tr_placa_sel = st.selectbox("Placa Tracto", tr_placas if tr_placas else ["No hay"], key="tr_p", label_visibility="collapsed")
        id_tr = str(tr_mapa_placa.get(tr_placa_sel, {}).get('id_tractor', '') or tr_placa_sel)
        st.text_input("ID Tracto", value=id_tr, disabled=True, key="id_tr_p")
    with ct2:
        cj1_placa_sel = st.selectbox("Placa Caja1", cj_placas if cj_placas else ["No hay"], key="cj1_p", label_visibility="collapsed")
        id_cj1 = str(cj_mapa_placa.get(cj1_placa_sel, {}).get('id_caja', '') or cj1_placa_sel)
        st.text_input("ID Caja1", value=id_cj1, disabled=True, key="id_cj1_p")
    with ct3:
        cj2_placa_sel = st.selectbox("Caja2", ["(Vacío - Sencillo)"] + cj_placas, key="cj2_p", label_visibility="collapsed")
        id_cj2 = str(cj_mapa_placa.get(cj2_placa_sel, {}).get('id_caja', '') or cj2_placa_sel) if cj2_placa_sel != "(Vacío - Sencillo)" else ""
        st.text_input("ID Caja2", value=id_cj2 if id_cj2 else "N/A", disabled=True, key="id_cj2_p")

    st.markdown("### 📄 Cliente y Destino Comercial")
    col_cli1, col_cli2 = st.columns(2)
    with col_cli1:
        cli_sel = st.selectbox("Cliente Comercial", cli_nombres if cli_nombres else ["No hay clientes"], key="cli_p")
        id_cli = str(cli_mapa.get(cli_sel, {}).get('id_cliente', '') or cli_sel)
    with col_cli2:
        des_sel = st.selectbox("Destino Final", des_nombres if des_nombres else ["No hay destinos"], key="des_p")
        id_des = str(des_mapa.get(des_sel, {}).get('id_destino', '') or des_sel)
        
    obs_val = st.text_area("Observaciones de Planta", key="obs_p")

    st.markdown("---")
    if st.button("🚀 GENERAR ORDEN DE CARGA", type="primary", use_container_width=True):
        if not fin_ruta_sel:
            st.warning("⚠️ Debe seleccionar al menos una finca en el recorrido de carga.")
        elif "No hay" in tr_placa_sel or "No hay" in cj1_placa_sel:
            st.warning("⚠️ Debe seleccionar un tracto y una caja válidos.")
        else:
            try:
                id_orden = f"OC-{datetime.now().strftime('%Y%m%d%H%M')}-{id_op}"
                ws_ord = sh.worksheet("OrdenesCarga")
                ensure_columns_exist(ws_ord, ["id_empresa_expedidora", "empresa_nombre", "id_finca_guia_titular", "id_linea", "linea_nombre", "observaciones", "ruta_fincas_ids"])
                
                row = {
                    "id_orden": id_orden,
                    "folio_orden": id_orden,
                    "fecha_creacion": datetime.now().isoformat(),
                    "id_usuario_crea": st.session_state.username,
                    "id_empresa_expedidora": id_emp_principal,
                    "empresa_nombre": emp_nombre_principal,
                    "id_finca_guia_titular": id_fin_guia,
                    "id_operador": id_op,
                    "id_tractor": id_tr,
                    "id_caja1": id_cj1,
                    "id_caja2": id_cj2,
                    "id_linea": id_lin,
                    "linea_nombre": lin_sel,
                    "id_cliente": id_cli,
                    "id_destino": id_des,
                    "estado": "ABIERTA",
                    "observaciones": obs_val,
                    "ruta_fincas_ids": ",".join(ids_fin_ruta)
                }
                
                append_row_dict_safe(ws_ord, row)
                
                ws_ruta = sh.worksheet("Orden_Fincas")
                ensure_columns_exist(ws_ruta, ["id", "id_orden", "id_finca", "orden_visita", "lote", "remision", "factura", "estado_carga"])
                
                for idx, fid in enumerate(ids_fin_ruta):
                    append_row_dict_safe(ws_ruta, {
                        "id": f"{id_orden}-{fid}", 
                        "id_orden": id_orden, 
                        "id_finca": fid, 
                        "orden_visita": idx + 1,
                        "lote": "",
                        "remision": "",
                        "factura": "",
                        "estado_carga": "PENDIENTE_FACTURACION"
                    })
                    
                st.balloons()
                st.success(f"✅ ¡Orden de Carga **{id_orden}** creada con éxito por planta/bodega! Quedó a la espera de que el departamento de facturación asigne los lotes, remisiones y facturas correspondientes por cada finca.")
            except Exception as e:
                st.error(f"Error al registrar la orden: {e}")

# ==========================================
# MÓDULO 2: REMISIÓN / FACTURA (OFICINA CENTRAL / FACTURACIÓN)
# ==========================================
elif st.session_state.menu_oficina == '🏷️ Remisión/Factura (Oficina)':
    st.markdown("<h2 style='margin:0;'>Oficina Central - Módulo Remisión / Factura</h2>", unsafe_allow_html=True)
    st.caption("Asignación posterior de datos de trazabilidad (Número de lote, Remisión y Factura) por cada finca según el volumen cargado en ruta.")
    st.markdown("---")

    df_oc, _ = get_df_safe("OrdenesCarga")
    df_ruta, ws_ruta = get_df_safe("Orden_Fincas")

    if df_oc.empty:
        st.info("No hay órdenes de carga registradas en el sistema.")
    else:
        folios = df_oc["id_orden"].tolist() if "id_orden" in df_oc.columns else []
        orden_sel = st.selectbox("Seleccionar Orden de Carga Expedida", folios)
        
        if orden_sel:
            datos_orden = df_oc[df_oc["id_orden"].astype(str) == str(orden_sel)].to_dict('records')[0]
            st.info(f"**Cliente:** {datos_orden.get('id_cliente')} | **Línea:** {datos_orden.get('linea_nombre')} | **Operador:** {datos_orden.get('id_operador')} | **Estado General:** {datos_orden.get('estado')}")
            
            fincas_orden = df_ruta[df_ruta["id_orden"].astype(str) == str(orden_sel)] if not df_ruta.empty else pd.DataFrame()
            
            if fincas_orden.empty:
                st.warning("Esta orden no contiene fincas asociadas en su ruta de carga.")
            else:
                st.markdown("#### 🏷️ Captura de Datos de Facturación por Finca en Ruta")
                
                with st.form(key=f"form_facturacion_{orden_sel}"):
                    actualizaciones = []
                    for _, row_f in fincas_orden.iterrows():
                        fid = str(row_f["id_finca"])
                        nombre_finca_obj = df_fin[df_fin["id_finca"].astype(str) == fid]
                        nombre_finca = nombre_finca_obj["nombre"].values[0] if not nombre_finca_obj.empty and "nombre" in nombre_finca_obj.columns else fid
                        
                        st.markdown(f"📍 **Finca del Recorrido:** `{nombre_finca}` (ID: {fid})")
                        
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            val_lote = st.text_input(f"Número de Lote ({nombre_finca})", value=str(row_f.get("lote", "")), placeholder="Ej: LOTE-27-01", key=f"lote_{orden_sel}_{fid}")
                        with c2:
                            val_rem = st.text_input(f"Folio Remisión ({nombre_finca})", value=str(row_f.get("remision", "")), placeholder="Ej: REM-9821", key=f"rem_{orden_sel}_{fid}")
                        with c3:
                            val_fac = st.text_input(f"Folio Factura ({nombre_finca})", value=str(row_f.get("factura", "")), placeholder="Ej: FAC-4412", key=f"fac_{orden_sel}_{fid}")
                        
                        actualizaciones.append({
                            "id": row_f.get("id"),
                            "id_orden": orden_sel,
                            "id_finca": fid,
                            "orden_visita": row_f.get("orden_visita"),
                            "lote": val_lote,
                            "remision": val_rem,
                            "factura": val_fac,
                            "estado_carga": "FACTURADO" if (val_lote or val_rem or val_fac) else "PENDIENTE_FACTURACION"
                        })
                        st.markdown("---")
                        
                    btn_guardar_fac = st.form_submit_button("💾 Guardar y Actualizar Lotes, Remisiones y Facturas", type="primary")
                    if btn_guardar_fac:
                        try:
                            ws_all_data = ws_ruta.get_all_records()
                            for act in actualizaciones:
                                for idx, row_sheet in enumerate(ws_all_data):
                                    if str(row_sheet.get("id")) == str(act["id"]) or (str(row_sheet.get("id_orden")) == str(orden_sel) and str(row_sheet.get("id_finca")) == str(act["id_finca"])):
                                        row_num = idx + 2  # Salto de cabecera y base 1
                                        ws_ruta.update_cell(row_num, ws_ruta.find("lote").col, act["lote"])
                                        ws_ruta.update_cell(row_num, ws_ruta.find("remision").col, act["remision"])
                                        ws_ruta.update_cell(row_num, ws_ruta.find("factura").col, act["factura"])
                                        ws_ruta.update_cell(row_num, ws_ruta.find("estado_carga").col, act["estado_carga"])
                            st.success("✅ ¡Datos de trazabilidad, remisión y factura actualizados correctamente por la oficina central!")
                        except Exception as e:
                            st.error(f"Error al sincronizar con Google Sheets: {e}")

# ==========================================
# MÓDULO 3: ÓRDENES EXPEDIDAS
# ==========================================
elif st.session_state.menu_oficina == 'Órdenes Expedidas':
    st.subheader("📋 Órdenes de Carga Registradas")
    df_oc, _ = get_df_safe("OrdenesCarga")
    if not df_oc.empty:
        st.dataframe(df_oc, use_container_width=True)
    else:
        st.info("No hay órdenes de carga registradas en el sistema.")

# ==========================================
# MÓDULO 4: SEGUIMIENTO
# ==========================================
elif st.session_state.menu_oficina == 'Seguimiento':
    st.markdown("<h2 style='margin:0;'>Módulo de Seguimiento y Monitoreo de Rutas</h2>", unsafe_allow_html=True)
    st.caption("Visualización en tiempo real del estatus logístico y comercial de los camiones en su recorrido por las diferentes fincas.")
    st.markdown("---")

    df_oc, _ = get_df_safe("OrdenesCarga")
    df_ruta, _ = get_df_safe("Orden_Fincas")

    if df_oc.empty:
        st.info("No hay órdenes de carga registradas para realizar seguimiento.")
    else:
        tab_seg1, tab_seg2 = st.tabs(["📊 Vista General de Despachos", "🗺️ Detalle por Ruta de Fincas"])

        with tab_seg1:
            st.markdown("#### Listado General de Órdenes de Carga")
            st.dataframe(df_oc, use_container_width=True)

        with tab_seg2:
            st.markdown("#### Seguimiento de Paradas y Carga por Finca")
            folios_seg = df_oc["id_orden"].tolist() if "id_orden" in df_oc.columns else []
            orden_seg_sel = st.selectbox("Seleccione Orden para ver detalle de ruta", folios_seg, key="sel_orden_seguimiento")

            if orden_seg_sel:
                info_orden = df_oc[df_oc["id_orden"].astype(str) == str(orden_seg_sel)].to_dict('records')
                if info_orden:
                    dat_o = info_orden[0]
                    c_info1, c_info2, c_info3 = st.columns(3)
                    with c_info1:
                        st.metric("Línea de Transporte", dat_o.get("linea_nombre", "N/A"))
                        st.metric("Operador ID", dat_o.get("id_operador", "N/A"))
                    with c_info2:
                        st.metric("Tracto", dat_o.get("id_tractor", "N/A"))
                        st.metric("Caja 1", dat_o.get("id_caja1", "N/A"))
                    with c_info3:
                        st.metric("Estado General", dat_o.get("estado", "ABIERTA"))
                        st.metric("Cliente Destino", dat_o.get("id_cliente", "N/A"))

                st.markdown("---")
                fincas_ruta_df = df_ruta[df_ruta["id_orden"].astype(str) == str(orden_seg_sel)] if not df_ruta.empty else pd.DataFrame()
                
                if fincas_ruta_df.empty:
                    st.warning("No hay fincas registradas para esta ruta.")
                else:
                    # Enriquecer con nombres de fincas si es posible
                    if not df_fin.empty and "id_finca" in df_fin.columns and "nombre" in df_fin.columns:
                        fincas_ruta_df = fincas_ruta_df.merge(df_fin[["id_finca", "nombre"]], on="id_finca", how="left")
                    
                    st.dataframe(fincas_ruta_df, use_container_width=True)

# ==========================================
# MÓDULO 5: CATALOGOS Y MANTENIMIENTO
# ==========================================
elif st.session_state.menu_oficina == 'Catálogos y Mantenimiento':
    st.markdown("<h2 style='margin:0;'>Módulo de Administración de Catálogos</h2>", unsafe_allow_html=True)
    st.caption("Gestión y control maestro de entidades, fincas, flotas, operadores y clientes.")
    st.markdown("---")

    cat_tab1, cat_tab2, cat_tab3, cat_tab4, cat_tab5 = st.tabs([
        "🏢 Empresas", "🏡 Fincas", "🚛 Flota (Tractos/Cajas)", "👥 Operadores", "🤝 Clientes y Destinos"
    ])

    with cat_tab1:
        st.markdown("#### Directorio de Empresas Comercializadoras")
        if not df_emp.empty:
            st.dataframe(df_emp, use_container_width=True)
        else:
            st.info("No hay empresas registradas.")

    with cat_tab2:
        st.markdown("#### Directorio de Fincas Productoras")
        if not df_fin.empty:
            st.dataframe(df_fin, use_container_width=True)
        else:
            st.info("No hay fincas registradas.")

    with cat_tab3:
        st.markdown("#### Parque Vehicular (Tractocamiones y Cajas Thermoking)")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("**Tractores / Tractocamiones**")
            if not df_tr_u.empty:
                st.dataframe(df_tr_u, use_container_width=True)
            else:
                st.info("Sin registros de tractores.")
        with col_c2:
            st.markdown("**Cajas de Carga / Termoking**")
            if not df_cj_u.empty:
                st.dataframe(df_cj_u, use_container_width=True)
            else:
                st.info("Sin registros de cajas.")

    with cat_tab4:
        st.markdown("#### Directorio de Operadores y Conductores")
        if not df_op.empty:
            st.dataframe(df_op, use_container_width=True)
        else:
            st.info("No hay operadores registrados.")

    with cat_tab5:
        st.markdown("#### Clientes Comerciales y Destinos de Exportación")
        col_cl1, col_cl2 = st.columns(2)
        with col_cl1:
            st.markdown("**Clientes**")
            if not df_cli.empty:
                st.dataframe(df_cli, use_container_width=True)
            else:
                st.info("Sin clientes registrados.")
        with col_cl2:
            st.markdown("**Destinos**")
            if not df_des.empty:
                st.dataframe(df_des, use_container_width=True)
            else:
                st.info("Sin destinos registrados.")

# ==========================================
# MÓDULO 6: REPORTES Y ESTADÍSTICAS
# ==========================================
elif st.session_state.menu_oficina == 'Reportes y Estadísticas':
    st.markdown("<h2 style='margin:0;'>Módulo de Reportes y Analítica</h2>", unsafe_allow_html=True)
    st.caption("Consolidados y métricas operativas de despacho bananero.")
    st.markdown("---")

    df_oc_rep, _ = get_df_safe("OrdenesCarga")
    df_ruta_rep, _ = get_df_safe("Orden_Fincas")

    if df_oc_rep.empty:
        st.info("No hay suficiente información para generar reportes estadísticos.")
    else:
        col_rep1, col_rep2 = st.columns(2)
        with col_rep1:
            st.metric("Total Órdenes Registradas", len(df_oc_rep))
        with col_rep2:
            st.metric("Total Paradas en Rutas de Fincas", len(df_ruta_rep) if not df_ruta_rep.empty else 0)

        st.markdown("#### Resumen Analítico de Órdenes")
        if "estado" in df_oc_rep.columns:
            conteo_estados = df_oc_rep["estado"].value_counts().reset_index()
            conteo_estados.columns = ["Estado", "Cantidad"]
            st.bar_chart(conteo_estados.set_index("Estado"))
        
        st.markdown("#### Vista Tabular Completa de Auditoría")
        st.dataframe(df_oc_rep, use_container_width=True)
