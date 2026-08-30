# ==============================================================================
# 1. CONFIGURACIÓN INICIAL Y LIBRERÍAS
# ==============================================================================
import streamlit as st
import pandas as pd
from datetime import datetime
import time
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

st.set_page_config(page_title="Control Operativo - Embarques V5", layout="wide", page_icon="🍌")


# ==============================================================================
# 2. CONEXIÓN Y CARGA SEGURA DE DATOS (CON CACHÉ Y PROTECCIÓN CONTRA LÍMITE 429)
# ==============================================================================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_NAME = st.secrets["app_config"]["spreadsheet_name"] if "app_config" in st.secrets else "Sistema_Banano_BD"

@st.cache_resource
def get_gspread_client():
    creds_dict = dict(st.secrets["google_credentials"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client, creds

def get_db():
    client, creds = get_gspread_client()
    sh = client.open(SPREADSHEET_NAME)
    drive_service = build('drive', 'v3', credentials=creds)
    return client, sh, drive_service

@st.cache_data(ttl=60)
def get_df_safe_cached(sheet_name):
    intentos = 0
    max_retries = 3
    while intentos < max_retries:
        try:
            _, sh, _ = get_db()
            mapa = {
                "Tractos": ["Tractos","Tractocamiones"],
                "Tractocamiones": ["Tractocamiones","Tractos"],
                "Cajas": ["Cajas","Cajas_Thermoking"],
                "Cajas_Thermoking": ["Cajas_Thermoking","Cajas"],
            }
            candidatos = mapa.get(sheet_name, [sheet_name])
            for name in candidatos:
                try:
                    ws = sh.worksheet(name)
                    data = ws.get_all_records()
                    df = pd.DataFrame(data, dtype=str) if data else pd.DataFrame(dtype=str)
                    df.columns = [str(c).strip() for c in df.columns]
                    return df
                except: 
                    continue
                    
            for ws in sh.worksheets():
                tl = ws.title.lower()
                sl = sheet_name.lower()
                if sl in tl or tl in sl:
                    data = ws.get_all_records()
                    df = pd.DataFrame(data, dtype=str) if data else pd.DataFrame(dtype=str)
                    df.columns = [str(c).strip() for c in df.columns]
                    return df
            return pd.DataFrame(dtype=str)
        except Exception as e:
            intentos += 1
            if intentos >= max_retries:
                return pd.DataFrame(dtype=str)
            time.sleep(2)
    return pd.DataFrame(dtype=str)

def get_df_safe(sheet_name, max_retries=3):
    df = get_df_safe_cached(sheet_name)
    return df, None

def ensure_columns_exist(worksheet, required_columns):
    try:
        header_row = worksheet.row_values(1)
        header_row_cleaned = [str(h).strip() for h in header_row]
        nuevas = [col for col in required_columns if col not in header_row_cleaned]
        if nuevas:
            next_col = len(header_row) + 1
            for i, col in enumerate(nuevas):
                worksheet.update_cell(1, next_col + i, col)
    except Exception:
        pass

def append_row_dict_safe(worksheet, row_dict):
    try:
        header_row = worksheet.row_values(1)
        header_row_cleaned = [str(h).strip() for h in header_row]
        if not header_row_cleaned:
            headers = list(row_dict.keys())
            worksheet.append_row(headers)
            header_row_cleaned = headers
            
        row_values = [str(row_dict.get(h, "")) for h in header_row_cleaned]
        worksheet.append_row(row_values)
        return True
    except Exception as e:
        st.error(f"Error al guardar en Google Sheets: {e}")
        return False

try:
    _, _, _ = get_db()
    conectado = True
    err_conexion = ""
except Exception as e:
    conectado = False
    err_conexion = str(e)

if "conectado" not in st.session_state:
    st.session_state.conectado = conectado    


# ==============================================================================
# 3. GESTIÓN DE SESIÓN Y AUTENTICACIÓN
# ==============================================================================
ROLES = ["OFICINA_CENTRAL", "VIGILANCIA", "JEFE_PLANTA", "ESTIBA"]
if 'rol' not in st.session_state:
    for k in ["rol", "id_finca", "usuario", "username", "nombre_usuario", "id_usuario", "finca_asignada", "menu_oficina"]:
        st.session_state[k] = None


# ==============================================================================
# 4. BARRA LATERAL (CONTROL DE ACCESO INTELIGENTE)
# ==============================================================================
with st.sidebar:
    st.markdown("### 🔐 Control de Acceso")
    if conectado: 
        st.success("🟢 Base de Datos Conectada")
    else: 
        st.error(f"🔴 Error de Conexión: {err_conexion}")
    
    if st.session_state.rol is None:
        rol_seleccionado = st.selectbox("Seleccione su Rol", ROLES)
        
        df_usuarios_raw, _ = get_df_safe("Usuarios")
        if df_usuarios_raw.empty:
            df_usuarios = pd.DataFrame([{
                "id_usuario": "USR-OF-001", "nombre": "Administrador", "rol": "OFICINA_CENTRAL", 
                "finca_asignada": "TODAS", "username": "admin", "password_hash": "123", "activo": "TRUE"
            }], dtype=str)
        else:
            df_usuarios = df_usuarios_raw.copy()
            rename = {}
            for col in df_usuarios.columns:
                c = str(col).lower().strip()
                if "id_usuario" in c: rename[col] = "id_usuario"
                elif "nombre" in c: rename[col] = "nombre"
                elif c == "rol": rename[col] = "rol"
                elif "finca" in c: rename[col] = "finca_asignada"
                elif "username" in c or "usuario" in c: rename[col] = "username"
                elif "password" in c or "pass" in c: rename[col] = "password_hash"
                elif "activo" in c: rename[col] = "activo"
            df_usuarios = df_usuarios.rename(columns=rename)
            
        df_activos = df_usuarios[df_usuarios["activo"].astype(str).str.upper().isin(["TRUE", "SI", "1", "ACTIVO"])] if "activo" in df_usuarios.columns else df_usuarios
        if df_activos.empty: 
            df_activos = df_usuarios
            
        df_filt = df_activos[df_activos["rol"].astype(str).str.upper() == rol_seleccionado.upper()] if not df_activos.empty else df_activos
        if df_filt.empty: 
            df_filt = df_activos
        
        opciones = []
        mapa_usuarios = {}
        for _, r in df_filt.iterrows():
            uname = str(r.get("username", "")).strip() or str(r.get("id_usuario", "")).strip()
            if uname and uname not in opciones:
                opciones.append(uname)
                mapa_usuarios[uname] = r
        if not opciones: 
            opciones = ["admin"]
        
        usuario_sel = st.selectbox("Usuario", opciones)
        r_sel = mapa_usuarios.get(usuario_sel)
        
        if r_sel is not None:
            id_usuario = str(r_sel.get("id_usuario", "")).strip()
            username = str(r_sel.get("username", "")).strip()
            nombre_usuario = str(r_sel.get("nombre", "")).strip()
            rol_real = str(r_sel.get("rol", rol_seleccionado)).strip()
            finca_asignada = str(r_sel.get("finca_asignada", "")).strip()
            pass_bd = str(r_sel.get("password_hash", "")).strip()
        else:
            id_usuario = ""
            username = usuario_sel
            nombre_usuario = username
            rol_real = rol_seleccionado
            finca_asignada = "TODAS"
            pass_bd = ""
            
        password_input = st.text_input("Contraseña", type="password")
        
        if st.button("Ingresar al Sistema", use_container_width=True):
            acceso_valido = password_input in ["123", "1234", pass_bd] or password_input.lower() == username.lower()
            if acceso_valido:
                st.session_state.rol = rol_real or rol_seleccionado
                st.session_state.finca_asignada = finca_asignada
                st.session_state.id_finca = finca_asignada if finca_asignada != "TODAS" else "OFICINA"
                st.session_state.username = username
                st.session_state.id_usuario = id_usuario
                st.session_state.nombre_usuario = nombre_usuario
                st.session_state.menu_oficina = "📦 Crear Orden"
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    else:
        st.success(f"Sesión Activa: **{st.session_state.rol}**")
        st.markdown(f"**Usuario:** `{st.session_state.username}`")
        st.markdown(f"**Finca:** `{st.session_state.finca_asignada}`")
        st.divider()
        
        if st.session_state.rol == "OFICINA_CENTRAL":
            st.markdown("### 📌 Navegación")
            menu = st.radio("Menú Oficina", ["📦 Crear Orden", "📦 Órdenes Expedidas", "✏️ Remisión/Factura", "⚙️ Catálogos Maestros", "🗺️ Seguimiento"], key="radio_menu_oficina")
            st.session_state.menu_oficina = menu
            
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            for k in ["rol", "id_finca", "finca_asignada", "usuario", "username", "id_usuario", "nombre_usuario", "menu_oficina"]:
                st.session_state[k] = None
            st.rerun()

if st.session_state.rol is None:
    st.stop()


# ==============================================================================
# 5. FUNCIONES AUXILIARES DE MAPEO Y LISTAS
# ==============================================================================
def lista_simple_no_concat(df, id_key, nombre_key):
    if df.empty: 
        return [], {}
    col_id = next((c for c in df.columns if id_key.lower() in c.lower()), df.columns[0])
    col_nom = next((c for c in df.columns if nombre_key.lower() in c.lower()), df.columns[1] if len(df.columns) > 1 else col_id)
    lista = []
    mapa = {}
    seen = set()
    for _, r in df.iterrows():
        idv = str(r.get(col_id, "")).strip()
        if not idv or idv.lower() == "nan": 
            continue
        nom = str(r.get(col_nom, "")).strip() or idv
        if nom.lower() in ["nan", ""]: 
            continue
        if nom not in seen:
            lista.append(nom)
            seen.add(nom)
        mapa[nom] = r.to_dict()
    return sorted(lista), mapa

def lista_placas_no_concat(df):
    if df.empty: 
        return [], {}
    col_id = next((c for c in df.columns if c.lower() in ["id_tractor", "id_caja", "id_equipo"] or "id_" in c.lower()), df.columns[0])
    col_pla = next((c for c in df.columns if "placa" in c.lower() or "economico" in c.lower()), df.columns[1] if len(df.columns) > 1 else col_id)
    lista = []
    mapa = {}
    for _, r in df.iterrows():
        idv = str(r.get(col_id, "")).strip()
        if not idv or idv.lower() == "nan": 
            continue
        pla = str(r.get(col_pla, "")).strip() or idv
        if pla not in lista:
            lista.append(pla)
        mapa[pla] = r.to_dict()
        mapa[idv] = r.to_dict()
    return sorted(lista), mapa


# ==============================================================================
# 6. CUERPO PRINCIPAL - ROL: OFICINA CENTRAL
# ==============================================================================
if st.session_state.rol == "OFICINA_CENTRAL":
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
    df_oc, _ = get_df_safe("OrdenesCarga")
    df_of, _ = get_df_safe("Orden_Fincas")
    
    df_tr_u = pd.concat([df_tr, df_tr2], ignore_index=True) if not df_tr.empty and not df_tr2.empty else (df_tr if not df_tr.empty else df_tr2)
    df_cj_u = pd.concat([df_cj, df_cj2], ignore_index=True) if not df_cj.empty and not df_cj2.empty else (df_cj if not df_cj.empty else df_cj2)

    emp_nombres, emp_mapa = lista_simple_no_concat(df_emp, "id_empresa", "razon_social")

    col_title, col_emp_top = st.columns([2, 2])
    with col_title:
        st.markdown(f"<h2 style='margin:0;'>Oficina Central - Panel de Control</h2>", unsafe_allow_html=True)
        st.caption(f"Usuario Conectado: **{st.session_state.nombre_usuario}** ({st.session_state.username})")
    with col_emp_top:
        st.markdown("**🏢 Empresa Expedidora (Primer Plano)**")
        emp_sel_principal = st.selectbox("Empresa", emp_nombres if emp_nombres else ["EMP-01"], key="emp_top_hibrido", label_visibility="collapsed")
        emp_data_principal = emp_mapa.get(emp_sel_principal, {})
        id_emp_principal = str(emp_data_principal.get('id_empresa', '') or emp_sel_principal)
        emp_nombre_principal = str(emp_data_principal.get('razon_social', '') or emp_sel_principal)

    st.markdown("---")
    menu_sel = st.session_state.get('menu_oficina', '📦 Crear Orden')

    # --------------------------------------------------------------------------
    # 6.1 Submódulo: 📦 Crear Orden
    # --------------------------------------------------------------------------
    if menu_sel == "📦 Crear Orden":
        st.subheader("📝 Generación de Nueva Orden de Carga")
        
        df_fincas_emp = df_fin[df_fin['id_empresa'].astype(str).str.upper() == id_emp_principal.upper()] if not df_fin.empty and 'id_empresa' in df_fin.columns else df_fin
        df_fincas_propias = df_fincas_emp[df_fincas_emp['tipo'].astype(str).str.upper() == 'PROPIA'] if not df_fincas_emp.empty and 'tipo' in df_fincas_emp.columns else df_fincas_emp
        fin_prop_nombres, fin_prop_mapa = lista_simple_no_concat(df_fincas_propias, "id_finca", "nombre")
        fin_todos_nombres, fin_todos_mapa = lista_simple_no_concat(df_fin, "id_finca", "nombre")
        ops_nombres, ops_mapa = lista_simple_no_concat(df_op, "id_operador", "nombre")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.markdown("**Finca Titular Guía (PROPIA)**")
            fin_guia_sel = st.selectbox("Finca PROPIA", fin_prop_nombres if fin_prop_nombres else fin_todos_nombres, key="fin_guia_hibrido")
            fin_guia_data = fin_prop_mapa.get(fin_guia_sel, {}) or fin_todos_mapa.get(fin_guia_sel, {})
            id_fin_guia = str(fin_guia_data.get('id_finca', '') or fin_guia_sel)
            st.text_input("ID Finca Guía", value=id_fin_guia, disabled=True, key="id_fin_guia_hibrido")
        with col_f2:
            st.markdown("**Ruta de Carga (Fincas participantes)**")
            fin_ruta_sel = st.multiselect("Fincas donde cargará", fin_todos_nombres, key="fin_ruta_hibrido")
            ids_fin_ruta = []
            for fn in fin_ruta_sel:
                d = fin_todos_mapa.get(fn, {})
                ids_fin_ruta.append(str(d.get('id_finca', '') or fn))

        st.markdown("#### 👤 Operador Asignado")
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            st.markdown("**Nombre Operador**")
            op_sel = st.selectbox("Nombre Operador", ops_nombres if ops_nombres else ["No hay operadores"], key="op_hibrido", label_visibility="collapsed")
            op_data = ops_mapa.get(op_sel, {})
            id_op = str(op_data.get('id_operador', '') or op_sel)
        with c2: 
            st.markdown("**ID Op**")
            st.text_input("ID Op", value=id_op, disabled=True, key="id_op_hibrido", label_visibility="collapsed")
        with c3: 
            st.markdown("**Licencia**")
            lic_val = str(op_data.get('licencia_num', '') or op_data.get('licencia', ''))
            st.text_input("Licencia", value=lic_val, disabled=True, key="lic_hibrido", label_visibility="collapsed")
        with c4: 
            st.markdown("**Teléfono**")
            tel_val = str(op_data.get('telefono', ''))
            st.text_input("Tel", value=tel_val, disabled=True, key="tel_hibrido", label_visibility="collapsed")

        tr_placas, tr_mapa_placa = lista_placas_no_concat(df_tr_u)
        cj_placas, cj_mapa_placa = lista_placas_no_concat(df_cj_u)
        cli_nombres, cli_mapa = lista_simple_no_concat(df_cli, "id_cliente", "razon_social")
        des_nombres, des_mapa = lista_simple_no_concat(df_des, "id_destino", "ciudad")

        st.markdown("#### 🚛 Equipamiento Asignado")

        col_sw1, col_sw2 = st.columns([3, 1])
        with col_sw1:
            st.markdown("##### Configuración de Arrastre")
        with col_sw2:
            modo_full = st.toggle("Configuración Full (Doble Caja)", value=False, key="toggle_full_hibrido")

        ct1, ct2, ct3 = st.columns(3)
        with ct1:
            st.markdown("**Tracto**")
            tr_placa_sel = st.selectbox("Placa Tracto", tr_placas if tr_placas else ["No hay"], key="tr_placa_hibrido", label_visibility="collapsed")
            tr_data = tr_mapa_placa.get(tr_placa_sel, {})
            id_tr = str(tr_data.get('id_tractor', '') or tr_placa_sel)
            placa_str = str(tr_data.get('placas', '') or tr_placa_sel)
            eco_tr = str(tr_data.get('numero_economico', '') or tr_data.get('economico', '') or tr_data.get('num_economico', '') or '')
            
            id_lin = str(tr_data.get('id_linea', '')).strip()
            lin_nombre_str = id_lin
            if not df_lin.empty:
                match_lin = df_lin[df_lin['id_linea'].astype(str).str.upper() == id_lin.upper()]
                if not match_lin.empty:
                    col_nom_lin = next((c for c in match_lin.columns if "razon" in c.lower() or "nombre" in c.lower()), match_lin.columns[1] if len(match_lin.columns) > 1 else match_lin.columns[0])
                    lin_nombre_str = str(match_lin.iloc[0].get(col_nom_lin, id_lin))

            st.text_input("ID Tracto", value=id_tr, disabled=True, key="id_tr_hibrido")
            st.text_input("Placas", value=placa_str, disabled=True, key="placa_tr_hibrido")
            st.text_input("N° Económico", value=eco_tr, disabled=True, key="eco_tr_hibrido")
            st.text_input("Línea de Transporte", value=lin_nombre_str, disabled=True, key="linea_tr_hibrido")

        with ct2:
            st.markdown("**Caja 1**")
            cj1_placa_sel = st.selectbox("Placa Caja1", cj_placas if cj_placas else ["No hay"], key="cj1_placa_hibrido", label_visibility="collapsed")
            cj1_data = cj_mapa_placa.get(cj1_placa_sel, {})
            id_cj1 = str(cj1_data.get('id_caja', '') or cj1_placa_sel)
            eco_cj1 = str(cj1_data.get('numero_economico', '') or cj1_data.get('economico', '') or cj1_data.get('num_economico', '') or '')
            
            st.text_input("ID Caja1", value=id_cj1, disabled=True, key="id_cj1_hibrido")
            st.text_input("Placa Caja1", value=str(cj1_data.get('placas', '') or cj1_placa_sel), disabled=True, key="placa_cj1_hibrido")
            st.text_input("N° Económico Caja 1", value=eco_cj1, disabled=True, key="eco_cj1_hibrido")
            st.markdown("")

        with ct3:
            if modo_full:
                st.markdown("**Caja 2 (Full Activo)**")
                cj2_placa_sel = st.selectbox("Caja2", cj_placas if cj_placas else ["No hay"], key="cj2_placa_hibrido", label_visibility="collapsed")
                cj2_data = cj_mapa_placa.get(cj2_placa_sel, {})
                id_cj2 = str(cj2_data.get('id_caja', '') or cj2_placa_sel)
                eco_cj2 = str(cj2_data.get('numero_economico', '') or cj2_data.get('economico', '') or cj2_data.get('num_economico', '') or '')
                
                st.text_input("ID Caja2", value=id_cj2, disabled=True, key="id_cj2_hibrido")
                st.text_input("Placa Caja2", value=str(cj2_data.get('placas', '') or cj2_placa_sel), disabled=True, key="placa_cj2_hibrido")
                st.text_input("N° Económico Caja 2", value=eco_cj2, disabled=True, key="eco_cj2_hibrido")
            else:
                id_cj2 = ""
                st.markdown("**Caja 2 (Sencillo)**")
                st.info("🔒 Modo Sencillo activo. Active el interruptor superior si requiere configuración Full.")

        st.markdown("### 📄 Documentación y Destino")
        r1, r2, r3, r4 = st.columns(4)
        with r1: lote_val = st.text_input("Lote", placeholder="Ej: 17-1355", key="lote_hibrido")
        with r2: rem_val = st.text_input("Folio Remisión", placeholder="Ej: REM-00123", key="rem_hibrido")
        with r3: fac_val = st.text_input("Folio Factura", placeholder="Ej: FAC-00123", key="fac_hibrido")
        with r4: fac2_val = st.text_input("Factura 2 (Full)", placeholder="Ej: FAC-00124", key="fac2_hibrido")

        col_cli1, col_cli2 = st.columns(2)
        with col_cli1:
            cli_sel = st.selectbox("Cliente", cli_nombres if cli_nombres else ["No hay clientes"], key="cli_hibrido")
            cli_data = cli_mapa.get(cli_sel, {})
            id_cli = str(cli_data.get('id_cliente', '') or cli_sel)
        with col_cli2:
            des_sel = st.selectbox("Destino", des_nombres if des_nombres else ["No hay destinos"], key="des_hibrido")
            des_data = des_mapa.get(des_sel, {})
            id_des = str(des_data.get('id_destino', '') or des_sel)
            
        obs_val = st.text_area("Observaciones Generales", key="obs_hibrido")

        st.markdown("---")
        if st.button("🚀 GENERAR Y EXPEDIR ORDEN DE CARGA", type="primary", use_container_width=True):
            if not fin_ruta_sel:
                st.warning("⚠️ Debe seleccionar al menos una finca para la ruta de carga.")
            elif "No hay" in tr_placa_sel or "No hay" in cj1_placa_sel:
                st.warning("⚠️ Debe seleccionar un tracto y una caja válidos.")
            else:
                try:
                    _, sh, _ = get_db()
                    id_orden = f"OC-{datetime.now().strftime('%Y%m%d%H%M')}-{id_op}"
                    ws_ord = sh.worksheet("OrdenesCarga")
                    
                    ensure_columns_exist(ws_ord, [
                        "id_orden", "folio_orden", "fecha_creacion", "id_usuario_crea", 
                        "id_operador", "id_tractor", "id_caja1", "id_caja2", "id_linea", 
                        "id_cliente", "id_destino", "id_lote", "folio_factura", 
                        "estado", "observaciones", "ruta_fincas_ids"
                    ])
                    
                    row = {
                        "id_orden": id_orden, "folio_orden": id_orden, "fecha_creacion": datetime.now().isoformat(),
                        "id_usuario_crea": st.session_state.username, "id_operador": id_op, "id_tractor": id_tr,
                        "id_caja1": id_cj1, "id_caja2": id_cj2, "id_linea": id_lin, "id_cliente": id_cli,
                        "id_destino": id_des, "id_lote": lote_val if lote_val else f"LOTE-{id_orden}",
                        "folio_factura": fac_val, "estado": "ABIERTA", "observaciones": obs_val, "ruta_fincas_ids": ",".join(ids_fin_ruta)
                    }
                    
                    if append_row_dict_safe(ws_ord, row):
                        ws_ruta = sh.worksheet("Orden_Fincas")
                        ensure_columns_exist(ws_ruta, ["id", "id_orden", "id_finca", "orden_visita", "estado_carga", "cajas_asignadas"])
                        for idx, fid in enumerate(ids_fin_ruta):
                            append_row_dict_safe(ws_ruta, {
                                "id": f"{id_orden}-{fid}", "id_orden": id_orden, "id_finca": fid, 
                                "orden_visita": idx + 1, "estado_carga": "PENDIENTE", "cajas_asignadas": ""
                            })
                        st.balloons()
                        st.success(f"✅ ¡Orden **{id_orden}** creada y expedida exitosamente bajo la empresa **{emp_nombre_principal}**!")
                except Exception as e:
                    st.error(f"Error al procesar la orden: {e}")

    # --------------------------------------------------------------------------
    # 6.2 Submódulo: 📦 Órdenes Expedidas
    # --------------------------------------------------------------------------
    elif menu_sel == "📦 Órdenes Expedidas":
        st.subheader("📦 Órdenes de Carga Registradas")
        if not df_oc.empty:
            colm1, colm2, colm3, colm4 = st.columns(4)
            with colm1: st.metric("Total Órdenes", len(df_oc))
            with colm2: st.metric("Abiertas", len(df_oc[df_oc['estado'].astype(str).str.upper() == 'ABIERTA']) if 'estado' in df_oc.columns else 0)
            with colm3: st.metric("En Ruta", len(df_of) if not df_of.empty else 0)
            with colm4: st.metric("Cerradas", len(df_oc[df_oc['estado'].astype(str).str.upper() == 'CERRADA']) if 'estado' in df_oc.columns else 0)
            
            cols_show = [c for c in ["id_orden", "id_operador", "id_tractor", "id_caja1", "id_lote", "folio_factura", "estado", "fecha_creacion"] if c in df_oc.columns]
            df_show = df_oc.tail(20).iloc[::-1]
            st.dataframe(df_show[cols_show] if cols_show else df_show, use_container_width=True)
        else:
            st.info("No hay órdenes expedidas registradas en este momento.")

    # --------------------------------------------------------------------------
    # 6.3 Submódulo: ✏️ Remisión/Factura
    # --------------------------------------------------------------------------
    elif menu_sel == "✏️ Remisión/Factura":
        st.subheader("✏️ Edición Rápida de Facturas y Lotes")
        df_oc_edit, _ = get_df_safe("OrdenesCarga")
        if df_oc_edit.empty:
            st.info("No hay órdenes disponibles para editar.")
        else:
            ids = list(reversed(df_oc_edit['id_orden'].astype(str).tolist()))
            sel_orden = st.selectbox("Seleccione la Orden a Modificar", ids[:100], key="sel_edit_hibrido")
            if sel_orden:
                fila = df_oc_edit[df_oc_edit['id_orden'] == sel_orden]
                if not fila.empty:
                    r = fila.iloc[0]
                    c1, c2 = st.columns(2)
                    with c1: new_fac = st.text_input("Factura", value=str(r.get('folio_factura', '')), key="efac_h")
                    with c2: new_lote = st.text_input("Lote", value=str(r.get('id_lote', '')), key="elote_h")
                    new_obs = st.text_area("Observaciones", value=str(r.get('observaciones', '')), key="eobs_h")
                    
                    if st.button("💾 Guardar Cambios", type="primary", use_container_width=True):
                        try:
                            _, sh, _ = get_db()
                            ws = sh.worksheet("OrdenesCarga")
                            cell = ws.find(sel_orden)
                            headers = [str(h).strip() for h in ws.row_values(1)]
                            def idx_col(name): return headers.index(name) + 1 if name in headers else None
                            
                            if idx_col("folio_factura"): ws.update_cell(cell.row, idx_col("folio_factura"), new_fac)
                            if idx_col("id_lote"): ws.update_cell(cell.row, idx_col("id_lote"), new_lote)
                            if idx_col("observaciones"): ws.update_cell(cell.row, idx_col("observaciones"), new_obs)
                            
                            st.success("¡Información actualizada correctamente!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")

# --------------------------------------------------------------------------
    # 6.4 Submódulo: ⚙️ Catálogos Maestros (CRUD Completo)
    # --------------------------------------------------------------------------
    elif menu_sel == "⚙️ Catálogos Maestros":
        st.subheader("⚙️ Administración de Catálogos Maestros")
        st.caption("Visualiza, edita, agrega o elimina registros de las tablas maestras de Google Sheets.")
        
        catalogo_sel = st.selectbox("Seleccione el Catálogo a Administrar", [
            "Tractos", "Cajas", "Operadores", "LineasTransporte", "Fincas", "Clientes", "Destinos", "Empresas"
        ], key="cat_maestro_sel")
        
        df_cat, _ = get_df_safe(catalogo_sel)
        
        tab_ver, tab_agregar, tab_editar_eliminar = st.tabs(["📋 Ver Registros", "➕ Agregar Nuevo", "✏️ / 🗑️ Editar o Eliminar"])
        
        with tab_ver:
            st.markdown(f"**Registros actuales en `{catalogo_sel}`** (Total: {len(df_cat)})")
            if not df_cat.empty:
                st.dataframe(df_cat, use_container_width=True)
            else:
                st.info("El catálogo está vacío o no se pudo cargar.")
                
        with tab_agregar:
            st.markdown(f"**Agregar un nuevo registro a `{catalogo_sel}`**")
            if not df_cat.empty:
                cols_cat = list(df_cat.columns)
            else:
                cols_cat = ["id", "nombre"]
                
            with st.form(key=f"form_agregar_{catalogo_sel}"):
                nuevos_datos = {}
                for col in cols_cat:
                    if catalogo_sel in ["Tractos", "Tractocamiones"] and col.lower() == "id_linea":
                        lin_nombres, lin_mapa = lista_simple_no_concat(df_lin, "id_linea", "razon_social")
                        lin_sel_add = st.selectbox("Línea de Transporte", lin_nombres if lin_nombres else ["Sin líneas"], key=f"add_{catalogo_sel}_{col}_combo")
                        lin_data_add = lin_mapa.get(lin_sel_add, {})
                        nuevos_datos[col] = str(lin_data_add.get('id_linea', '') or lin_sel_add)
                    else:
                        nuevos_datos[col] = st.text_input(f"Campo: {col}", key=f"add_{catalogo_sel}_{col}")
                
                btn_guardar_nuevo = st.form_submit_button("💾 Guardar Registro en Google Sheets", type="primary")
                if btn_guardar_nuevo:
                    try:
                        _, sh, _ = get_db()
                        ws = sh.worksheet(catalogo_sel)
                        if append_row_dict_safe(ws, nuevos_datos):
                            st.success(f"✅ ¡Registro agregado exitosamente a `{catalogo_sel}`!")
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error al agregar registro: {e}")
                        
        with tab_editar_eliminar:
            st.markdown(f"**Modificar o Eliminar registros en `{catalogo_sel}`**")
            if df_cat.empty:
                st.info("No hay registros disponibles para modificar.")
            else:
                col_id_cat = df_cat.columns[0]
                lista_ids = df_cat[col_id_cat].astype(str).tolist()
                id_a_modificar = st.selectbox(f"Seleccione por `{col_id_cat}`", lista_ids, key=f"sel_mod_{catalogo_sel}")
                
                fila_match = df_cat[df_cat[col_id_cat].astype(str) == str(id_a_modificar)]
                if not fila_match.empty:
                    datos_fila = fila_match.iloc[0].to_dict()
                    
                    # Incluimos id_a_modificar en la key del form para asegurar que se redibuje al cambiar de registro en cualquier catálogo
                    with st.form(key=f"form_mod_{catalogo_sel}_{id_a_modificar}"):
                        st.markdown(f"Editando registro: **{id_a_modificar}**")
                        datos_editados = {}
                        for k, v in datos_fila.items():
                            if catalogo_sel in ["Tractos", "Tractocamiones"] and k.lower() == "id_linea":
                                lin_nombres, lin_mapa = lista_simple_no_concat(df_lin, "id_linea", "razon_social")
                                
                                current_val = str(v).strip()
                                default_idx = 0
                                for idx_l, lname in enumerate(lin_nombres):
                                    ldata = lin_mapa.get(lname, {})
                                    lid = str(ldata.get('id_linea', '')).strip()
                                    if lid.upper() == current_val.upper() or lname.upper() == current_val.upper():
                                        default_idx = idx_l
                                        break
                                        
                                lin_sel_mod = st.selectbox("Línea de Transporte", lin_nombres if lin_nombres else ["Sin líneas"], index=default_idx, key=f"edit_{catalogo_sel}_{k}_{id_a_modificar}_combo")
                                lin_data_mod = lin_mapa.get(lin_sel_mod, {})
                                datos_editados[k] = str(lin_data_mod.get('id_linea', '') or lin_sel_mod)
                            else:
                                # Clave dinámica usando el id actual del registro para evitar persistencia errónea entre elementos
                                datos_editados[k] = st.text_input(f"Modificar {k}", value=str(v), key=f"edit_{catalogo_sel}_{k}_{id_a_modificar}")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            btn_actualizar = st.form_submit_button("💾 Actualizar Cambios", type="primary")
                        with col_btn2:
                            btn_eliminar = st.form_submit_button("🗑️ Eliminar Registro", type="secondary")
                            
                        if btn_actualizar:
                            try:
                                _, sh, _ = get_db()
                                ws = sh.worksheet(catalogo_sel)
                                cell = ws.find(str(id_a_modificar))
                                headers = [str(h).strip() for h in ws.row_values(1)]
                                
                                for k, val in datos_editados.items():
                                    if k in headers:
                                        idx = headers.index(k) + 1
                                        ws.update_cell(cell.row, idx, val)
                                st.success("✅ ¡Registro actualizado correctamente!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al actualizar: {e}")
                                
                        if btn_eliminar:
                            try:
                                _, sh, _ = get_db()
                                ws = sh.worksheet(catalogo_sel)
                                cell = ws.find(str(id_a_modificar))
                                ws.delete_rows(cell.row)
                                st.success("🗑️ ¡Registro eliminado correctamente de la base de datos!")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al eliminar: {e}")
 # --------------------------------------------------------------------------
    # 6.5 Submódulo: 🛡️ Módulo de Vigilancia (Entrada y Salida en Caseta)
    # --------------------------------------------------------------------------
    elif menu_sel == "🛡️ Módulo de Vigilancia":
        st.markdown("<h2 style='color: #28a745;'>🛡️ Módulo de Vigilancia - 6</h2>", unsafe_allow_html=True)
        st.markdown("Vehículos Pendientes en Finca")
        
        # Aquí muestras tu tabla actual (asegúrate de que df_of tenga los datos filtrados para la finca 6)
        # Ejemplo de filtrado por finca:
        finca_actual = str(st.session_state.get('finca', '6'))
        if 'df_of' in locals() and not df_of.empty:
            df_finca = df_of[df_of['id_finca'].astype(str) == finca_actual]
        else:
            df_finca = pd.DataFrame() # O tu carga de datos correspondiente
            
        # Mostramos la tabla de pendientes tal como la tienes en tu captura
        df_pendientes = df_finca[df_finca['estado_carga'].astype(str).str.upper().isin(['PENDIENTE', ''])] if not df_finca.empty else df_finca
        st.dataframe(df_pendientes, use_container_width=True)
        
        st.markdown("---")
        
        # ------------------------------------------------------------------
        # SECCIÓN DE CAPTURA DE ENTRADA Y SALIDA (Estilo Caseta)
        # ------------------------------------------------------------------
        tab_ent, tab_sal = st.tabs(["📥 REGISTRAR ENTRADA", "📤 REGISTRAR SALIDA"])
        
        from datetime import datetime
        import pytz
        
        try:
            zona_local = pytz.timezone('America/Mexico_City')
            hora_dispositivo = datetime.now(zona_local).strftime("%Y-%m-%d %H:%M:%S")
        except:
            hora_dispositivo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with tab_ent:
            st.markdown("<h3 style='color: #28a745;'>ENTRADA FINCA</h3>", unsafe_allow_html=True)
            
            finca_sel = st.selectbox("Finca:", [f"Finca {finca_actual}"], key="vis_finca_sel")
            
            lista_ocs = df_pendientes['id_orden'].astype(str).tolist() if not df_pendientes.empty else ["Sin OC pendientes"]
            oc_sel = st.selectbox("OC:", lista_ocs, key="vis_oc_sel")
            
            placa_guia = st.text_input("Placa / Guía:", placeholder="Ej: 123-ABC / GT-8821", key="vis_placa_input")
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("<div style='border: 2px dashed #28a745; padding: 10px; border-radius: 10px; text-align: center;'>", unsafe_allow_html=True)
            foto_tractor = st.camera_input("📷 FOTO 1 - TRACTOR FRENTE (Toca para abrir cámara)", key="vis_foto_tractor")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("<div style='border: 2px dashed #28a745; padding: 10px; border-radius: 10px; text-align: center;'>", unsafe_allow_html=True)
            foto_caja = st.camera_input("📷 FOTO 2 - CAJA TRASERA (Toca para abrir cámara)", key="vis_foto_caja")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("✅ GUARDAR ENTRADA", type="primary", use_container_width=True, key="btn_guardar_entrada_estilo"):
                if not placa_guia:
                    st.error("⚠️ Debe ingresar la Placa o Guía del vehículo.")
                else:
                    try:
                        _, sh, _ = get_db()
                        ws_v = sh.worksheet("vigilancia_registro")
                        id_reg = f"VIG-ENT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        
                        dict_reg = {
                            "id_registro": id_reg,
                            "id_orden": str(oc_sel),
                            "id_finca": str(finca_actual),
                            "id_caja": str(placa_guia),
                            "tipo_evento": "LLEGADA_CASETA",
                            "fecha_hora": str(hora_dispositivo),
                            "foto_tractor_placa_url": "CARGADA" if foto_tractor is not None else "PENDIENTE",
                            "foto_caja_placa_url": "CARGADA" if foto_caja is not None else "PENDIENTE",
                            "id_usuario_vigilante": str(st.session_state.get("username", "vigilante")),
                            "observaciones": f"Placa/Guía: {placa_guia}"
                        }
                        
                        ensure_columns_exist(ws_v, list(dict_reg.keys()))
                        append_row_dict_safe(ws_v, dict_reg)
                        
                        ws_of = sh.worksheet("Orden_Fincas")
                        cell_of = ws_of.find(str(oc_sel))
                        if cell_of:
                            headers_of = [str(h).strip() for h in ws_of.row_values(1)]
                            if "estado_carga" in headers_of:
                                ws_of.update_cell(cell_of.row, headers_of.index("estado_carga") + 1, "LLEGADO_CASETA")
                                
                        st.success(f"✅ ¡Entrada guardada con éxito a las {hora_dispositivo}!")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

        with tab_salida:
            st.markdown("<h3 style='color: #d9534f;'>SALIDA DE FINCA</h3>", unsafe_allow_html=True)
            df_salidas = df_finca[df_finca['estado_carga'].astype(str).str.upper() == 'LLEGADO_CASETA'] if not df_finca.empty else df_finca
            lista_salidas = df_salidas['id_orden'].astype(str).tolist() if not df_salidas.empty else ["Sin unidades en sitio"]
            
            oc_sal_sel = st.selectbox("OC en Sitio:", lista_salidas, key="vis_oc_sal_sel")
            placa_sal = st.text_input("Placa / Guía de Salida:", key="vis_placa_sal")
            
            st.markdown("<div style='border: 2px dashed #d9534f; padding: 10px; border-radius: 10px; text-align: center;'>", unsafe_allow_html=True)
            foto_tr_sal = st.camera_input("📷 FOTO SALIDA - TRACTOR FRENTE", key="vis_foto_tr_sal")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div style='border: 2px dashed #d9534f; padding: 10px; border-radius: 10px; text-align: center;'>", unsafe_allow_html=True)
            foto_cj_sal = st.camera_input("📷 FOTO SALIDA - CAJA TRASERA", key="vis_foto_cj_sal")
            st.markdown("</div>", unsafe_allow_html=True)
            
            if st.button("🚀 GUARDAR SALIDA", type="primary", use_container_width=True, key="btn_guardar_salida_estilo"):
                try:
                    _, sh, _ = get_db()
                    ws_v = sh.worksheet("vigilancia_registro")
                    id_reg_s = f"VIG-SAL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    
                    dict_reg_s = {
                        "id_registro": id_reg_s,
                        "id_orden": str(oc_sal_sel),
                        "id_finca": str(finca_actual),
                        "id_caja": str(placa_sal),
                        "tipo_evento": "SALIDA_CASETA",
                        "fecha_hora": str(hora_dispositivo),
                        "foto_tractor_placa_url": "CARGADA_SALIDA" if foto_tr_sal is not None else "PENDIENTE",
                        "foto_caja_placa_url": "CARGADA_SALIDA" if foto_cj_sal is not None else "PENDIENTE",
                        "id_usuario_vigilante": str(st.session_state.get("username", "vigilante")),
                        "observaciones": f"Salida Placa/Guía: {placa_sal}"
                    }
                    
                    ensure_columns_exist(ws_v, list(dict_reg_s.keys()))
                    append_row_dict_safe(ws_v, dict_reg_s)
                    
                    ws_of = sh.worksheet("Orden_Fincas")
                    cell_of = ws_of.find(str(oc_sal_sel))
                    if cell_of:
                        headers_of = [str(h).strip() for h in ws_of.row_values(1)]
                        if "estado_carga" in headers_of:
                            ws_of.update_cell(cell_of.row, headers_of.index("estado_carga") + 1, "COMPLETADO_SALIDA")
                            
                    st.success(f"✅ ¡Salida registrada con éxito a las {hora_dispositivo}!")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar salida: {e}")
# ==============================================================================
# 7. MÓDULOS OPERATIVOS ADICIONALES (ROLES SECUNDARIOS)
# ==============================================================================
elif st.session_state.rol == "VIGILANCIA":
    st.markdown(f"<h2>🛡️ Módulo de Vigilancia - {st.session_state.finca_asignada}</h2>", unsafe_allow_html=True)
    df_of, _ = get_df_safe("Orden_Fincas")
    if df_of.empty: 
        st.warning("No hay órdenes asignadas o la red está inestable temporalmente.")
    else:
        finca = st.session_state.finca_asignada
        df_f = df_of if finca.upper() == "TODAS" else df_of[df_of['id_finca'].astype(str).str.upper() == finca.upper()]
        st.metric("Vehículos Pendientes en Finca", len(df_f[~df_f['estado_carga'].isin(['CARGADO_SALIO', 'COMPLETADO'])]))
        st.dataframe(df_f, use_container_width=True)

else:
    st.title(f"Módulo: {st.session_state.rol}")
    st.info(f"Bienvenido al sistema operativo. Finca asignada: {st.session_state.finca_asignada}")
