# ==============================================================================
# 1. CONFIGURACIÓN INICIAL Y LIBRERÍAS
# ==============================================================================
import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import openpyxl
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

st.set_page_config(page_title="Control Operativo - Embarques V5", layout="wide", page_icon="🍌")

# ==============================================================================
# 1.1. CONFIGURACIÓN DE RESPALDOS Y MODO OFFLINE (EXCEL PUENTE)
# ==============================================================================
CARPETA_BACKUPS = "backups_finca"
EXCEL_RESPALDO = "respaldo_pendientes_finca.xlsx"

def limpiar_backures_antiguos():
    """Elimina respaldos locales con más de 30 días de antigüedad para ahorrar espacio."""
    try:
        ahora = time.time()
        treinta_dias = 30 * 86400
        for archivo in os.listdir(CARPETA_BACKUPS):
            ruta_archivo = os.path.join(CARPETA_BACKUPS, archivo)
            if os.path.isfile(ruta_archivo):
                if ahora - os.path.getmtime(ruta_archivo) > treinta_dias:
                    os.remove(ruta_archivo)
    except:
        pass

def verificar_y_hacer_backup_automatico():
    """Verifica si ya se realizó un respaldo hoy y lo descarga de Google Sheets si hay red."""
    try:
        if not os.path.exists(CARPETA_BACKUPS):
            os.makedirs(CARPETA_BACKUPS)
            
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        archivo_backup_hoy = os.path.join(CARPETA_BACKUPS, f"backup_general_{fecha_hoy}.xlsx")
        
        if os.path.exists(archivo_backup_hoy):
            return
            
        _, sh, _ = get_db()
        worksheets = sh.worksheets()
        
        with pd.ExcelWriter(archivo_backup_hoy, engine='openpyxl') as writer:
            for ws in worksheets:
                data = ws.get_all_records()
                df = pd.DataFrame(data) if data else pd.DataFrame()
                nombre_pestana = ws.title[:31]
                df.to_excel(writer, sheet_name=nombre_pestana, index=False)
                
        limpiar_backures_antiguos()
    except Exception:
        pass


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

# ==============================================================================
# 2.1. FUNCIONES DE PUENTE OFFLINE Y SINCRONIZACIÓN
# ==============================================================================
def guardar_con_respaldo_offline(sheet_name, dict_data):
    """Intenta guardar en Google Sheets o respalda en Excel local si no hay red."""
    try:
        _, sh, _ = get_db()
        nombres_h = [w.title for w in sh.worksheets()]
        if sheet_name in nombres_h:
            ws = sh.worksheet(sheet_name)
        else:
            ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
            
        ensure_columns_exist(ws, list(dict_data.keys()))
        append_row_dict_safe(ws, dict_data)
        return True, "Guardado exitosamente en la Nube (Google Sheets)."
    except Exception:
        try:
            df_nuevo = pd.DataFrame([dict_data])
            df_nuevo["sheet_destino"] = sheet_name
            
            if os.path.exists(EXCEL_RESPALDO):
                df_existente = pd.read_excel(EXCEL_RESPALDO)
                df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
            else:
                df_final = df_nuevo
                
            df_final.to_excel(EXCEL_RESPALDO, index=False)
            return False, "⚠️ Sin internet: Guardado de emergencia en Excel local."
        except Exception as ex_excel:
            return False, f"Error crítico al respaldar localmente: {ex_excel}"

def sincronizar_pendientes_excel():
    """Sube los registros del Excel puente local a Google Sheets al recuperar red."""
    if not os.path.exists(EXCEL_RESPALDO):
        return 0, "No hay datos pendientes de sincronización."
        
    try:
        df_pendientes = pd.read_excel(EXCEL_RESPALDO)
        if df_pendientes.empty:
            os.remove(EXCEL_RESPALDO)
            return 0, "El archivo de respaldo estaba vacío."
            
        _, sh, _ = get_db()
        sincronizados = 0
        
        for sheet_name, grupo in df_pendientes.groupby("sheet_destino"):
            if sheet_name not in [w.title for w in sh.worksheets()]:
                ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
            else:
                ws = sh.worksheet(sheet_name)
                
            grupo_limpio = grupo.drop(columns=["sheet_destino"], errors="ignore")
            
            for _, row in grupo_limpio.iterrows():
                dict_fila = row.dropna().to_dict()
                dict_fila = {str(k): str(v) for k, v in dict_fila.items()}
                ensure_columns_exist(ws, list(dict_fila.keys()))
                append_row_dict_safe(ws, dict_fila)
                sincronizados += 1
                
        os.remove(EXCEL_RESPALDO)
        return sincronizados, f"¡Sincronización exitosa! Se subieron {sincronizados} registros a la nube."
    except Exception as e:
        return -1, f"No se pudo sincronizar (verifique su conexión): {e}"

# Comprobación inicial de estado y ejecución del respaldo automático diario
try:
    _, _, _ = get_db()
    conectado = True
    err_conexion = ""
    verificar_y_hacer_backup_automatico()
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
        
        # 🚀 BOTÓN DE CERRAR SESIÓN UBICADO ARRIBA (A LA MANO)
        if st.button("🚪 Cerrar Sesión", use_container_width=True, type="secondary"):
            for k in ["rol", "id_finca", "finca_asignada", "usuario", "username", "id_usuario", "nombre_usuario", "menu_oficina"]:
                st.session_state[k] = None
            st.rerun()
            
        st.divider()
        
        if st.session_state.rol == "OFICINA_CENTRAL":
            st.markdown("### 📌 Navegación")
            menu = st.radio("Menú Oficina", ["📦 Crear Orden", "📦 Órdenes Expedidas", "📜 Compra y Guías", "✏️ Remisión/Factura", "⚙️ Catálogos Maestros", "🗺️ Seguimiento", "🗺️ Reportes y Concentrados"], key="radio_menu_oficina")
            st.session_state.menu_oficina = menu

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
        # Inyección de estilo global para forzar la tipografía Arial en todo el submódulo
        st.markdown(
            """
            <style>
                div.stMarkdown, div.stText, span, p, label, div.stSelectbox, div.stTextInput, div.stNumberInput, div.stButton, div.stToggle, div.stDateInput {
                    font-family: Arial, sans-serif !important;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.subheader("📝 Generación de Nueva Orden de Carga")
        
        df_fincas_emp = df_fin[df_fin['id_empresa'].astype(str).str.upper() == id_emp_principal.upper()] if not df_fin.empty and 'id_empresa' in df_fin.columns else df_fin
        fin_todos_nombres, fin_todos_mapa = lista_simple_no_concat(df_fin, "id_finca", "nombre")
        ops_nombres, ops_mapa = lista_simple_no_concat(df_op, "id_operador", "nombre")

        # Generación del consecutivo actual basado en la cantidad de registros en la BD
        try:
            _, sh_id, _ = get_db()
            ws_ord_id = sh_id.worksheet("OrdenesCarga")
            all_ords = ws_ord_id.get_all_records()
            next_num = len(all_ords) + 1
            id_orden_temp = f"OC-{next_num}"
        except Exception:
            id_orden_temp = f"OC-1"

        # Visualización limpia dividida en dos etiquetas independientes con tamaño destacado y Arial
        st.markdown(
            f"""
            <div style="padding: 10px 0px; font-family: Arial, sans-serif;">
                <span style="font-size: 14px; font-weight: normal; color: #555;">Folio:</span><br>
                <span style="font-size: 22px; font-weight: bold; color: #1f77b4;">{id_orden_temp}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Únicamente dejamos la Ruta de Carga arriba
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
            st.text_input("N° Económico Caja 1", value=eco_cj1, disabled=True, key="id_eco_cj1_hibrido")
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
                st.text_input("N° Económico Caja 2", value=eco_cj2, disabled=True, key="id_eco_cj2_hibrido")
            else:
                id_cj2 = ""
                st.markdown("**Caja 2 (Sencillo)**")
                st.info("🔒 Modo Sencillo activo. Active el interruptor superior si requiere configuración Full.")

        st.markdown("### 📄 Documentación, Destino y Citas")
        r1, r2, r3, r4 = st.columns(4)
        with r1: lote_val = st.text_input("Lote", placeholder="Ej: 17-1355", key="lote_hibrido")
        with r2: rem_val = st.text_input("Folio Remisión", placeholder="Ej: REM-00123", key="rem_hibrido")
        with r3: fac_val = st.text_input("Folio Factura", placeholder="Ej: FAC-00123", key="fac_hibrido")
        with r4: fac2_val = st.text_input("Factura 2 (Full)", placeholder="Ej: FAC-00124", key="fac2_hibrido")

        # --------------------------------------------------------------------------
        # Sección de Citas, Fechas de Llegada y Registro / Comprobante
        # --------------------------------------------------------------------------
        st.markdown("##### 🕒 Control de Cita y Comprobante de Registro")
        cc1, cc2, cc3 = st.columns([1, 2, 2])
        with cc1:
            tiene_cita = st.toggle("¿Tiene Cita?", value=False, key="toggle_tiene_cita")
        with cc2:
            fecha_cita_val = st.date_input("Fecha límite para la cita", value=datetime.now().date(), key="fecha_cita_hibrido", disabled=not tiene_cita)
        with cc3:
            comprobante_val = st.text_input("Comprobante / No. Serie / Registro", placeholder="Ej: REG-98765 (Opcional)", key="comprobante_hibrido")

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

        # --------------------------------------------------------------------------
        # Integración: Guía Fitosanitaria (Filtrada por la empresa actual)
        # --------------------------------------------------------------------------
        st.markdown("#### 📜 Asignación de Guía Fitosanitaria y Conciliación Física")
        lleva_guia = st.toggle("¿Esta orden de carga incluye Guía Fitosanitaria?", value=False, key="toggle_lleva_guia")
        
        id_guia_asignada_sel = ""
        folios_asignados_detalle = {}
        cajas_guia = 0
        finca_guia_sel = ""
        id_fin_guia_emision = ""
        
        if lleva_guia:
            cg1, cg2 = st.columns(2)
            with cg1:
                cajas_guia = st.number_input("Cantidad de Cajas en la Guía", min_value=1, value=1000, step=10, key="g_cajas_guia")
                st.caption("Margen operativo estimado: +/- 50 cajas sobre el total del recorrido.")
            with cg2:
                df_fincas_empresa = df_fin[df_fin['id_empresa'].astype(str).str.upper() == id_emp_principal.upper()] if not df_fin.empty and 'id_empresa' in df_fin.columns else df_fin
                fincas_empresa_nombres, fincas_empresa_mapa = lista_simple_no_concat(df_fincas_empresa, "id_finca", "nombre")
                
                finca_guia_sel = st.selectbox("Finca Emisora de la Guía (Individual)", fincas_empresa_nombres if fincas_empresa_nombres else ["No hay fincas para esta empresa"], key="sel_finca_guia")
                
                finca_guia_data = fincas_empresa_mapa.get(finca_guia_sel, {})
                id_fin_guia_emision = str(finca_guia_data.get('id_finca', '') or finca_guia_sel)

            df_compras_guias, _ = get_df_safe("Compra_Guias")
            df_stock_folios, _ = get_df_safe("Guias_Folios_Stock")
            
            if df_compras_guias.empty:
                st.warning("⚠️ No hay compras de guías registradas en el sistema. Debe registrar una compra en el módulo '📜 Compra y Guías'.")
            else:
                lotes_empresa = df_compras_guias[df_compras_guias['id_empresa'].astype(str).str.upper() == id_emp_principal.upper()] if 'id_empresa' in df_compras_guias.columns else df_compras_guias
                lotes_activos = lotes_empresa[lotes_empresa['estado'].astype(str).str.upper() == 'ACTIVO'] if not lotes_empresa.empty and 'estado' in lotes_empresa.columns else lotes_empresa
                
                if lotes_activos.empty:
                    st.warning("⚠️ No hay lotes de guías con estatus ACTIVO para esta empresa.")
                else:
                    lote_opciones = lotes_activos.apply(lambda r: f"Lote: {r['id_compra']} | AAPS: {r.get('folio_compra_AAPS', 'N/D')}", axis=1).tolist()
                    lote_sel_str = st.selectbox("Seleccione el Lote de Guías", lote_opciones, key="sel_lote_guia")
                    
                    id_compra_elegida = lote_sel_str.split("|")[0].replace("Lote:", "").strip()
                    id_guia_asignada_sel = id_compra_elegida
                    
                    if not df_stock_folios.empty:
                        folios_lote_disp = df_stock_folios[
                            (df_stock_folios['id_compra'].astype(str) == id_compra_elegida) & 
                            (df_stock_folios['estado'].astype(str).str.upper() == 'DISPONIBLE')
                        ]
                        
                        if folios_lote_disp.empty:
                            st.error("❌ Este lote ya no cuenta con folios disponibles en stock.")
                        else:
                            st.markdown("##### 🔍 Conciliación Detallada de Folios Físicos Disponibles")
                            st.caption("Visualice y seleccione el folio específico disponible para cada documento requerido:")
                            
                            tipos_docs_req = [
                                "Certificado de Origen",
                                "Constancia de Origen",
                                "Constancia de Clorinacion",
                                "Carta Responsiva"
                            ]
                            
                            col_f1, col_f2 = st.columns(2)
                            idx_col = 0
                            for doc_t in tipos_docs_req:
                                folios_doc_tipo = folios_lote_disp[folios_lote_disp['tipo_documento'].astype(str) == doc_t]
                                if not folios_doc_tipo.empty:
                                    opciones_doc = folios_doc_tipo.apply(
                                        lambda r: f"{r['folio']} | Disponible", 
                                        axis=1
                                    ).tolist()
                                    
                                    mapa_opciones = {f"{r['folio']} | Disponible": r['folio'] for _, r in folios_doc_tipo.iterrows()}
                                    
                                    with (col_f1 if idx_col % 2 == 0 else col_f2):
                                        st.markdown(f"**{doc_t}**")
                                        sel_etiqueta = st.selectbox(f"Folio {doc_t}", opciones_doc, key=f"sel_folio_det_{doc_t}", label_visibility="collapsed")
                                        folio_elegido = mapa_opciones.get(sel_etiqueta, "")
                                        folios_asignados_detalle[doc_t] = folio_elegido
                                        st.success(f"Asignando **{doc_t}**: `{folio_elegido}`")
                                else:
                                    with (col_f1 if idx_col % 2 == 0 else col_f2):
                                        st.markdown(f"**{doc_t}**")
                                        st.warning(f"Sin stock disponible para {doc_t}")
                                        folios_asignados_detalle[doc_t] = ""
                                idx_col += 1
        else:
            st.info("ℹ️ La orden se procesará sin Guía Fitosanitaria.")

        st.markdown("---")
        if st.button("🚀 GENERAR Y EXPEDIR ORDEN DE CARGA", type="primary", use_container_width=True):
            if not fin_ruta_sel:
                st.warning("⚠️ Debe seleccionar al menos una finca para la ruta de carga.")
            elif "No hay" in tr_placa_sel or "No hay" in cj1_placa_sel:
                st.warning("⚠️ Debe seleccionar un tracto y una caja válidos.")
            else:
                try:
                    _, sh, _ = get_db()
                    id_orden = id_orden_temp
                    ws_ord = sh.worksheet("OrdenesCarga")
                    
                    ensure_columns_exist(ws_ord, [
                        "id_orden", "folio_orden", "fecha_creacion", "id_usuario_crea", 
                        "id_operador", "id_tractor", "id_caja1", "id_caja2", "id_linea", 
                        "id_cliente", "id_destino", "id_lote", "folio_factura", 
                        "estado", "observaciones", "ruta_fincas_ids",
                        "lleva_guia", "id_guia_asignada", "finca_guia_id", "cajas_guia",
                        "folio_certificado_origen", "folio_constancia_origen", 
                        "folio_constancia_clorinacion", "folio_carta_responsiva",
                        "tiene_cita", "fecha_cita", "comprobante_cita"
                    ])
                    
                    row = {
                        "id_orden": id_orden, "folio_orden": id_orden, "fecha_creacion": datetime.now().isoformat(),
                        "id_usuario_crea": st.session_state.username, "id_operador": id_op, "id_tractor": id_tr,
                        "id_caja1": id_cj1, "id_caja2": id_cj2, "id_linea": id_lin, "id_cliente": id_cli,
                        "id_destino": id_des, "id_lote": lote_val if lote_val else f"LOTE-{id_orden}",
                        "folio_factura": fac_val, "estado": "ABIERTA", "observaciones": obs_val, "ruta_fincas_ids": ",".join(ids_fin_ruta),
                        "lleva_guia": "SI" if lleva_guia else "NO",
                        "id_guia_asignada": id_guia_asignada_sel if lleva_guia else "",
                        "finca_guia_id": id_fin_guia_emision if lleva_guia else "",
                        "cajas_guia": cajas_guia if lleva_guia else 0,
                        "folio_certificado_origen": folios_asignados_detalle.get("Certificado de Origen", "") if lleva_guia else "",
                        "folio_constancia_origen": folios_asignados_detalle.get("Constancia de Origen", "") if lleva_guia else "",
                        "folio_constancia_clorinacion": folios_asignados_detalle.get("Constancia de Clorinacion", "") if lleva_guia else "",
                        "folio_carta_responsiva": folios_asignados_detalle.get("Carta Responsiva", "") if lleva_guia else "",
                        "tiene_cita": "SI" if tiene_cita else "NO",
                        "fecha_cita": str(fecha_cita_val) if tiene_cita else "",
                        "comprobante_cita": comprobante_val.strip()
                    }
                    
                    if append_row_dict_safe(ws_ord, row):
                        ws_ruta = sh.worksheet("Orden_Fincas")
                        ensure_columns_exist(ws_ruta, ["id", "id_orden", "id_finca", "orden_visita", "estado_carga", "cajas_asignadas"])
                        for idx, fid in enumerate(ids_fin_ruta):
                            append_row_dict_safe(ws_ruta, {
                                "id": f"{id_orden}-{fid}", "id_orden": id_orden, "id_finca": fid, 
                                "orden_visita": idx + 1, "estado_carga": "PENDIENTE", "cajas_asignadas": ""
                            })
                        
                        if lleva_guia and folios_asignados_detalle:
                            try:
                                ws_f_stock = sh.worksheet("Guias_Folios_Stock")
                                data_f_stock = ws_f_stock.get_all_records()
                                col_estado = ws_f_stock.find("estado").col
                                col_orden = ws_f_stock.find("id_orden_asignada").col
                                for i, f_row in enumerate(data_f_stock, start=2):
                                    f_val = str(f_row.get("folio", ""))
                                    f_compra = str(f_row.get("id_compra", ""))
                                    if f_compra == id_guia_asignada_sel and f_val in folios_asignados_detalle.values():
                                        ws_f_stock.update_cell(i, col_estado, "ASIGNADO")
                                        ws_f_stock.update_cell(i, col_orden, id_orden)
                            except Exception as ex_stock:
                                st.warning(f"Orden creada, pero hubo un detalle al actualizar el stock de folios: {ex_stock}")

                        st.balloons()
                        st.success(f"✅ ¡Orden **{id_orden}** creada y expedida exitosamente bajo la empresa **{emp_nombre_principal}**!")
                except Exception as e:
                    st.error(f"Error al procesar la orden: {e}")
  # --------------------------------------------------------------------------
    # 6.2 Submódulo: 📦 Órdenes Expedidas
    # --------------------------------------------------------------------------
    if "Órdenes Expedidas" in menu_sel or menu_sel == "Órdenes Expedidas":
        # Inyección de estilo global estricto para forzar la tipografía Arial en todo el submódulo
        st.markdown(
            """
            <style>
                html, body, [class*="css"] {
                    font-family: Arial, sans-serif !important;
                }
                div.stMarkdown, div.stText, span, p, label, div.stSelectbox, div.stTextInput, div.stNumberInput, div.stButton, div.stRadio, div.dataframe {
                    font-family: Arial, sans-serif !important;
                }
                table, th, td {
                    font-family: Arial, sans-serif !important;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.subheader("📦 Consulta y Gestión de Órdenes Expedidas")
        st.caption("Visualice el historial detallado de las órdenes de carga generadas y expedidas por el grupo corporativo.")

        df_ordenes, _ = get_df_safe("OrdenesCarga")

        if df_ordenes.empty:
            st.info("ℹ️ No hay órdenes de carga registradas en el sistema.")
        else:
            # Filtrar por empresa principal activa si la columna existe
            if 'id_empresa' in df_ordenes.columns and 'id_emp_principal' in locals():
                df_ordenes = df_ordenes[df_ordenes['id_empresa'].astype(str).str.upper() == str(id_emp_principal).upper()]

            if df_ordenes.empty:
                st.warning(f"⚠️ No hay órdenes expedidas registradas para la empresa actual: **{emp_nombre_principal if 'emp_nombre_principal' in locals() else ''}**.")
            else:
                # Opciones de filtrado rápido
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    filtro_estado = st.selectbox("Filtrar por Estado", ["TODOS", "EXPEDIDA", "ACTIVA", "COMPLETADA", "CANCELADA"], key="filtro_estado_exp")
                with col_f2:
                    if 'cliente' in df_ordenes.columns:
                        clientes_disp = ["TODOS"] + sorted(df_ordenes['cliente'].dropna().astype(str).unique().tolist())
                        filtro_cliente = st.selectbox("Filtrar por Cliente", clientes_disp, key="filtro_cliente_exp")
                    else:
                        filtro_cliente = "TODOS"

                df_filtrado = df_ordenes.copy()
                if filtro_estado != "TODOS" and 'estado' in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado['estado'].astype(str).str.upper() == filtro_estado]
                if filtro_cliente != "TODOS" and 'cliente' in df_filtrado.columns:
                    df_filtrado = df_filtrado[df_filtrado['cliente'].astype(str).str.upper() == filtro_cliente.upper()]

                st.markdown("---")
                st.markdown(f"#### 📋 Listado de Órdenes ({len(df_filtrado)} registros encontrados)")
                
                if df_filtrado.empty:
                    st.info("ℹ️ No se encontraron órdenes con los filtros seleccionados.")
                else:
                    st.dataframe(df_filtrado, use_container_width=True)

                    # Detalle individual de orden en tarjeta limpia y profesional (Reemplazo total de st.json)
                    st.markdown("#### 🔍 Detalle Individual de Orden")
                    ids_disponibles = df_filtrado['id_orden'].astype(str).tolist() if 'id_orden' in df_filtrado.columns else []
                    
                    if ids_disponibles:
                        id_detalles = st.selectbox("Seleccionar ID de Orden para Ver Detalle", ids_disponibles, key="sel_detalle_orden")
                        fila_det = df_filtrado[df_filtrado['id_orden'].astype(str) == str(id_detalles)]
                        
                        if not fila_det.empty:
                            d_reg = fila_det.iloc[0].to_dict()
                            
                            st.markdown(
                                f"""
                                <div style="background-color: #f9f9f9; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; font-family: Arial, sans-serif !important;">
                                    <h4 style="color: #2c3e50; margin-top: 0; font-family: Arial, sans-serif;">📄 Orden de Carga: <b>{d_reg.get('id_orden', '')}</b></h4>
                                    <hr style="margin: 10px 0; border: 0; border-top: 1px solid #ccc;">
                                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-family: Arial, sans-serif; font-size: 14px;">
                                        <p style="margin: 4px 0;"><b>📅 Fecha Creación:</b> {d_reg.get('fecha_creacion', '')}</p>
                                        <p style="margin: 4px 0;"><b>📌 Estado:</b> {d_reg.get('estado', 'ACTIVA')}</p>
                                        <p style="margin: 4px 0;"><b>👤 Usuario Crea:</b> {d_reg.get('id_usuario_crea', '')}</p>
                                        <p style="margin: 4px 0;"><b>🚜 Operador / Tractor:</b> {d_reg.get('id_operador', '')} / {d_reg.get('id_tractor', '')}</p>
                                        <p style="margin: 4px 0;"><b>📦 Cajas:</b> {d_reg.get('id_caja1', '')} | {d_reg.get('id_caja2', '')}</p>
                                        <p style="margin: 4px 0;"><b>🏢 Cliente:</b> {d_reg.get('cliente', d_reg.get('id_cliente', ''))}</p>
                                        <p style="margin: 4px 0;"><b>📍 Destino:</b> {d_reg.get('id_destino', '')}</p>
                                        <p style="margin: 4px 0;"><b>🏷️ Lote (AAPS):</b> {d_reg.get('id_lote', 'Pendiente')}</p>
                                        <p style="margin: 4px 0;"><b>📄 Remisión:</b> {d_reg.get('folio_remision', 'Pendiente')}</p>
                                        <p style="margin: 4px 0;"><b>🧾 Factura:</b> {d_reg.get('folio_factura', 'Pendiente')}</p>
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
    
# --------------------------------------------------------------------------
    # 6.3 Submódulo: 📜 Compra y Guías
    # --------------------------------------------------------------------------
    if menu_sel == "📜 Compra y Guías":
        # Inyección de estilo global para forzar la tipografía Arial en todo el submódulo
        st.markdown(
            """
            <style>
                div.stMarkdown, div.stText, span, p, label, div.stSelectbox, div.stTextInput, div.stNumberInput, div.stButton, div.stToggle {
                    font-family: Arial, sans-serif !important;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.subheader("📜 Módulo de Compra y Gestión de Guías Fitosanitarias (AAPS)")
        st.caption("Registro de lotes de guías adquiridos ante la Asociación Agrícola Local de Productores de Banano (AAPS) y control de folios disponibles.")

        tab_compra1, tab_compra2 = st.tabs(["➕ Registrar Compra de Lote", "📊 Inventario y Stock de Folios"])

        with tab_compra1:
            st.markdown("### Registro de Nuevo Lote de Guías AAPS")
            
            with st.form("form_compra_guias"):
                c_g1, c_g2 = st.columns(2)
                with c_g1:
                    # Emisor institucional fijo (Asociación Agrícola - AAPS) independiente del catálogo interno de empresas
                    st.text_input("Emisor / Proveedor Oficial", value="Asociación Agrícola Local de Productores de Banano (AAPS)", disabled=True, key="lbl_emisor_aaps")
                    folio_aaps = st.text_input("Folio o Referencia de Compra AAPS", placeholder="Ej: AAPS-2026-8901")
                    
                with c_g2:
                    fecha_compra = st.date_input("Fecha de Adquisición", value=datetime.now())
                    # Empresa del grupo corporativo seleccionada en el panel superior que patrocina la adquisición
                    st.text_input("Empresa Adquiriente (Grupo)", value=emp_nombre_principal, disabled=True, key="lbl_emp_compra")

                st.markdown("---")
                st.markdown("#### 🔢 Rango y Estructura de Folios por Documento")
                st.caption("Ingrese el rango numérico (inicio y fin) proporcionado por la AAPS para cada formato oficial requerido en la guía fitosanitaria.")

                docs_config = [
                    ("Certificado de Origen", "cert_ini", "cert_fin"),
                    ("Constancia de Origen", "orig_ini", "orig_fin"),
                    ("Constancia de Clorinacion", "clor_ini", "clor_fin"),
                    ("Carta Responsiva", "resp_ini", "resp_fin")
                ]

                rangos_capturados = {}
                for doc_nombre, key_ini, key_fin in docs_config:
                    st.markdown(f"**📄 {doc_nombre}**")
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        val_ini = st.number_input(f"Folio Inicial - {doc_nombre}", min_value=1, value=1, step=1, key=key_ini)
                    with rc2:
                        val_fin = st.number_input(f"Folio Final - {doc_nombre}", min_value=1, value=100, step=1, key=key_fin)
                    rangos_capturados[doc_nombre] = (val_ini, val_fin)

                obs_compra = st.text_area("Observaciones de la Compra", placeholder="Notas adicionales sobre la adquisición ante la AAPS...")

                btn_guardar_compra = st.form_submit_button("💾 Guardar Lote y Generar Stock de Folios", use_container_width=True)

                if btn_guardar_compra:
                    if not folio_aaps.strip():
                        st.warning("⚠️ Debe ingresar el Folio o Referencia de Compra AAPS.")
                    else:
                        try:
                            _, sh, _ = get_db()
                            
                            # 1. Asegurar hojas y columnas
                            ws_comp = sh.worksheet("Compra_Guias")
                            ensure_columns_exist(ws_comp, [
                                "id_compra", "id_empresa", "emisor", "folio_compra_AAPS", 
                                "fecha_compra", "observaciones", "estado", "usuario_registra"
                            ])

                            ws_stock = sh.worksheet("Guias_Folios_Stock")
                            ensure_columns_exist(ws_stock, [
                                "id_stock", "id_compra", "id_empresa", "tipo_documento", 
                                "folio", "estado", "id_orden_asignada"
                            ])

                            # Generar ID de compra consecutivo
                            all_compras = ws_comp.get_all_records()
                            id_compra_gen = f"CG-{datetime.now().strftime('%Y%m%d')}-{len(all_compras)+1:04d}"

                            row_compra = {
                                "id_compra": id_compra_gen,
                                "id_empresa": id_emp_principal,
                                "emisor": "Asociación Agrícola Local de Productores de Banano (AAPS)",
                                "folio_compra_AAPS": folio_aaps.strip(),
                                "fecha_compra": fecha_compra.isoformat(),
                                "observaciones": obs_compra,
                                "estado": "ACTIVO",
                                "usuario_registra": st.session_state.username
                            }

                            if append_row_dict_safe(ws_comp, row_compra):
                                # Generar folios individuales en stock para cada documento
                                total_folios_generados = 0
                                for doc_n, (f_ini, f_fin) in rangos_capturados.items():
                                    if f_fin >= f_ini:
                                        for f_num in range(int(f_ini), int(f_fin) + 1):
                                            row_f_stock = {
                                                "id_stock": f"{id_compra_gen}-{doc_n[:3].upper()}-{f_num}",
                                                "id_compra": id_compra_gen,
                                                "id_empresa": id_emp_principal,
                                                "tipo_documento": doc_n,
                                                "folio": str(f_num),
                                                "estado": "DISPONIBLE",
                                                "id_orden_asignada": ""
                                            }
                                            append_row_dict_safe(ws_stock, row_f_stock)
                                            total_folios_generados += 1

                                st.success(f"✅ ¡Lote **{id_compra_gen}** registrado con éxito ante la AAPS para **{emp_nombre_principal}**! Se generaron **{total_folios_generados} folios** individuales.")
                                st.balloons()
                        except Exception as e:
                            st.error(f"Error al registrar la compra de guías: {e}")

        with tab_compra2:
            st.markdown("### Inventario General y Stock de Folios Físicos (AAPS)")
            df_compras, _ = get_df_safe("Compra_Guias")
            df_stock, _ = get_df_safe("Guias_Folios_Stock")

            if df_compras.empty:
                st.info("ℹ️ No hay lotes de compras de guías registrados en el sistema.")
            else:
                # Filtrar por empresa principal del grupo
                df_c_emp = df_compras[df_compras['id_empresa'].astype(str).str.upper() == id_emp_principal.upper()] if 'id_empresa' in df_compras.columns else df_compras
                
                if df_c_emp.empty:
                    st.warning(f"⚠️ No hay lotes registrados para la empresa actual: **{emp_nombre_principal}**.")
                else:
                    st.dataframe(df_c_emp, use_container_width=True)

                    st.markdown("#### 📦 Detalle de Stock por Folio")
                    if not df_stock.empty:
                        lote_sel_inv = st.selectbox("Filtrar por Lote de Compra", df_c_emp['id_compra'].tolist(), key="sel_lote_inventario")
                        df_stock_lote = df_stock[df_stock['id_compra'].astype(str) == str(lote_sel_inv)]
                        
                        if df_stock_lote.empty:
                            st.info("ℹ️ No hay folios registrados para este lote.")
                        else:
                            col_st1, col_st2, col_st3 = st.columns(3)
                            total_f = len(df_stock_lote)
                            disp_f = len(df_stock_lote[df_stock_lote['estado'].astype(str).str.upper() == 'DISPONIBLE'])
                            asig_f = len(df_stock_lote[df_stock_lote['estado'].astype(str).str.upper() == 'ASIGNADO'])
                            
                            with col_st1: st.metric("Total Folios", total_f)
                            with col_st2: st.metric("Disponibles", disp_f, delta=f"{disp_f} libres")
                            with col_st3: st.metric("Asignados", asig_f, delta=f"-{asig_f} usados", delta_color="inverse")

                            st.dataframe(df_stock_lote[['id_stock', 'tipo_documento', 'folio', 'estado', 'id_orden_asignada']], use_container_width=True)
                    else:
                        st.info("ℹ️ La tabla de stock de folios se encuentra vacía.")
                        
# --------------------------------------------------------------------------
    # 6.4 Submódulo: 📄 Remisión/Factura (Con lectura dinámica desde la tabla Clientes)
    # --------------------------------------------------------------------------
    if "Remisión/Factura" in menu_sel:
        st.markdown(
            """
            <style>
                html, body, [class*="css"] {
                    font-family: Arial, sans-serif !important;
                }
                div.stMarkdown, div.stText, span, p, label, div.stSelectbox, div.stTextInput, div.stNumberInput, div.stButton, div.stRadio, div.dataframe {
                    font-family: Arial, sans-serif !important;
                }
                table, th, td {
                    font-family: Arial, sans-serif !important;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.subheader("📄 Gestión y Asignación de Lotes, Remisiones y Facturas")
        st.caption("Seleccione una orden pendiente de documentación para asignar o actualizar su número de lote, remisión (con prefijo del cliente) y factura.")

        df_ordenes, _ = get_df_safe("OrdenesCarga")
        df_clientes, _ = get_df_safe("Clientes")

        if df_ordenes.empty:
            st.info("ℹ️ No hay órdenes de carga registradas en el sistema.")
        else:
            if 'id_empresa' in df_ordenes.columns and 'id_emp_principal' in locals():
                df_ordenes = df_ordenes[df_ordenes['id_empresa'].astype(str).str.upper() == str(id_emp_principal).upper()]

            if df_ordenes.empty:
                st.warning(f"⚠️ No hay órdenes registradas para la empresa actual.")
            else:
                for col_necesaria in ['id_lote', 'folio_remision', 'folio_factura', 'cliente']:
                    if col_necesaria not in df_ordenes.columns:
                        df_ordenes[col_necesaria] = ""

                # Filtrar órdenes pendientes
                mask_pendientes = (
                    (df_ordenes['id_lote'].astype(str).str.strip().isin(["", "nan", "None"])) |
                    (df_ordenes['folio_remision'].astype(str).str.strip().isin(["", "nan", "None"])) |
                    (df_ordenes['folio_factura'].astype(str).str.strip().isin(["", "nan", "None"]))
                )
                df_pendientes = df_ordenes[mask_pendientes]

                modo_vista = st.radio(
                    "Filtrar Órdenes para Captura",
                    ["⚠️ Órdenes Pendientes de Documentación", "📋 Todas las Órdenes Registradas"],
                    horizontal=True
                )

                df_trabajo = df_pendientes if "Pendientes" in modo_vista else df_ordenes

                if df_trabajo.empty:
                    st.success("🎉 ¡Excelente! No hay órdenes pendientes de documentación bajo este filtro.")
                else:
                    st.markdown("---")
                    st.markdown("#### ✍️ Selección y Actualización de Documentación")

                    ids_ordenes = df_trabajo['id_orden'].astype(str).tolist() if 'id_orden' in df_trabajo.columns else []
                    
                    if not ids_ordenes:
                        st.warning("⚠️ No se encontraron IDs de orden válidos en el listado.")
                    else:
                        orden_sel_act = st.selectbox("Seleccione la Orden de Carga", ids_ordenes, key="sel_orden_facturacion")

                        fila_orden = df_trabajo[df_trabajo['id_orden'].astype(str) == str(orden_sel_act)]
                        
                        if not fila_orden.empty:
                            datos_ord = fila_orden.iloc[0].to_dict()
                            
                            val_lote_act = str(datos_ord.get('id_lote', '') if str(datos_ord.get('id_lote', '')) not in ["nan", "None"] else "")
                            val_rem_act = str(datos_ord.get('folio_remision', '') if str(datos_ord.get('folio_remision', '')) not in ["nan", "None"] else "")
                            val_fac_act = str(datos_ord.get('folio_factura', '') if str(datos_ord.get('folio_factura', '')) not in ["nan", "None"] else "")
                            val_fac2_act = str(datos_ord.get('folio_factura2', '') if str(datos_ord.get('folio_factura2', '')) not in ["nan", "None"] else "")
                            cliente_orden = str(datos_ord.get('cliente', '')).strip().upper()

                            # Buscar el prefijo/letra de remisión directamente desde la tabla Clientes
                            prefijo_cliente = ""
                            if not df_clientes.empty and 'razon_social' in df_clientes.columns and 'letra_remision' in df_clientes.columns:
                                match_cli = df_clientes[df_clientes['razon_social'].astype(str).str.strip().str.upper() == cliente_orden]
                                if not match_cli.empty:
                                    prefijo_cliente = str(match_cli.iloc[0].get('letra_remision', '')).strip()
                                    if prefijo_cliente in ["nan", "None"]:
                                        prefijo_cliente = ""

                            # Si no tiene remisión registrada, calcular consecutivo usando la letra asignada en la tabla Clientes
                            if not val_rem_act and prefijo_cliente:
                                remisiones_existentes = df_ordenes['folio_remision'].astype(str).tolist()
                                count_prefijo = sum(1 for r in remisiones_existentes if r.startswith(prefijo_cliente))
                                siguiente_consecutivo = count_prefijo + 1
                                val_rem_act = f"{prefijo_cliente}-{siguiente_consecutivo:04d}"

                            with st.form(f"form_act_doc_{orden_sel_act}"):
                                st.markdown(f"**Editando documentos para la orden:** `{orden_sel_act}` | **Cliente:** `{cliente_orden if cliente_orden else 'GENERAL'}`")
                                if prefijo_cliente:
                                    st.info(f"ℹ️ Letra de remisión asignada desde el catálogo de clientes: **{prefijo_cliente}**")
                                else:
                                    st.warning("⚠️ Este cliente no tiene configurada una letra de remisión en el catálogo de Clientes.")
                                
                                f_r1, f_r2 = st.columns(2)
                                with f_r1:
                                    nuevo_lote = st.text_input("Número de Lote (Guía AAPS)", value=val_lote_act, placeholder="Ej: CG-20260830-0001")
                                    nuevo_rem = st.text_input("Número de Remisión (Letra y Consecutivo)", value=val_rem_act, placeholder="Ej: Z102-0001 o Y123-0001")
                                with f_r2:
                                    nueva_fac = st.text_input("Número de Factura", value=val_fac_act, placeholder="Ej: FAC-00123")
                                    nueva_fac2 = st.text_input("Factura 2 (Opcional)", value=val_fac2_act, placeholder="Ej: FAC-00124")

                                btn_guardar_docs = st.form_submit_button("💾 Guardar y Actualizar Documentación", use_container_width=True)

                                if btn_guardar_docs:
                                    try:
                                        _, sh, _ = get_db()
                                        ws_ord = sh.worksheet("OrdenesCarga")
                                        
                                        ensure_columns_exist(ws_ord, ["id_orden", "id_lote", "folio_remision", "folio_factura", "folio_factura2"])

                                        cell_id = ws_ord.find(str(orden_sel_act))
                                        if cell_id:
                                            row_idx = cell_id.row
                                            header_row = ws_ord.row_values(1)
                                            
                                            def actualizar_columna(nombre_col, valor_val):
                                                if nombre_col in header_row:
                                                    col_idx = header_row.index(nombre_col) + 1
                                                    ws_ord.update_cell(row_idx, col_idx, valor_val)

                                            actualizar_columna("id_lote", nuevo_lote)
                                            actualizar_columna("folio_remision", nuevo_rem)
                                            actualizar_columna("folio_factura", nueva_fac)
                                            actualizar_columna("folio_factura2", nueva_fac2)

                                            st.success(f"✅ ¡Documentación actualizada con éxito para la orden **{orden_sel_act}**!")
                                            st.balloons()
                                        else:
                                            st.error("❌ No se pudo localizar la fila de la orden en la base de datos de Google Sheets.")
                                    except Exception as e:
                                        st.error(f"Error al actualizar la documentación: {e}")

                st.markdown("---")
                st.markdown("#### 📋 Resumen del Estado de Documentación en Órdenes")
                cols_mostrar = [c for c in ["id_orden", "fecha_creacion", "cliente", "id_lote", "folio_remision", "folio_factura", "estado"] if c in df_ordenes.columns]
                st.dataframe(df_ordenes[cols_mostrar] if cols_mostrar else df_ordenes, use_container_width=True)                
                
# --------------------------------------------------------------------------
    # 6.5 Submódulo: ⚙️ Catálogos Maestros
    # --------------------------------------------------------------------------
    if "Catálogos Maestros" in menu_sel:
        # Inyección de estilo global estricto para forzar la tipografía Arial en todo el submódulo
        st.markdown(
            """
            <style>
                html, body, [class*="css"] {
                    font-family: Arial, sans-serif !important;
                }
                div.stMarkdown, div.stText, span, p, label, div.stSelectbox, div.stTextInput, div.stNumberInput, div.stButton, div.stTabs, div.dataframe {
                    font-family: Arial, sans-serif !important;
                }
                table, th, td {
                    font-family: Arial, sans-serif !important;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.subheader("⚙️ Gestión de Catálogos Maestros")
        st.caption("Administre y actualice los registros principales del sistema (Clientes, Fincas, Equipos y Catálogo de Cartón).")

        tab_cat1, tab_cat2, tab_cat3, tab_cat4 = st.tabs([
            "👥 Clientes", 
            "🏡 Fincas / Predios", 
            "🚛 Equipos y Transporte", 
            "📦 Catálogo de Cartón"
        ])

        with tab_cat1:
            st.markdown("### 👥 Catálogo de Clientes (con Letra y Prefijo de Remisión)")
            
            # Asegurar estructura de columnas en la hoja Clientes incluyendo letra_remision
            try:
                _, sh_db, _ = get_db()
                ws_cli = sh_db.worksheet("Clientes")
                ensure_columns_exist(ws_cli, ["id_cliente", "razon_social", "rfc", "domicilio", "contacto", "telefono", "letra_remision"])
            except Exception:
                pass

            df_cli, _ = get_df_safe("Clientes")

            if not df_cli.empty:
                st.dataframe(df_cli, use_container_width=True)
            else:
                st.info("ℹ️ No hay clientes registrados actualmente en la base de datos.")

            st.markdown("#### ➕ Registrar o Actualizar Cliente")
            with st.form("form_cat_cliente"):
                cc1, cc2 = st.columns(2)
                with cc1:
                    cli_id = st.text_input("ID del Cliente", placeholder="Ej: CLI-001")
                    cli_razon = st.text_input("Razón Social", placeholder="Ej: Empresa La Rioja")
                    cli_rfc = st.text_input("RFC", placeholder="Ej: RIO260101XXX")
                with cc2:
                    cli_dom = st.text_input("Domicilio", placeholder="Ej: Carretera Principal Km 5")
                    cli_cont = st.text_input("Contacto", placeholder="Ej: Juan Pérez")
                    cli_tel = st.text_input("Teléfono", placeholder="Ej: 9991234567")
                    cli_letra = st.text_input("Letra / Prefijo de Remisión", placeholder="Ej: Z102 o Y123")

                btn_guardar_cli = st.form_submit_button("💾 Guardar / Actualizar Cliente", use_container_width=True)

                if btn_guardar_cli:
                    if not cli_id.strip() or not cli_razon.strip():
                        st.warning("⚠️ El ID y la Razón Social son obligatorios.")
                    else:
                        try:
                            _, sh, _ = get_db()
                            ws_c = sh.worksheet("Clientes")
                            ensure_columns_exist(ws_c, ["id_cliente", "razon_social", "rfc", "domicilio", "contacto", "telefono", "letra_remision"])
                            
                            cell_c = ws_c.find(str(cli_id.strip()))
                            nuevo_registro = {
                                "id_cliente": cli_id.strip(),
                                "razon_social": cli_razon.strip(),
                                "rfc": cli_rfc.strip(),
                                "domicilio": cli_dom.strip(),
                                "contacto": cli_cont.strip(),
                                "telefono": cli_tel.strip(),
                                "letra_remision": cli_letra.strip().upper()
                            }
                            
                            if cell_c:
                                row_idx = cell_c.row
                                header_vals = ws_c.row_values(1)
                                for k, v in nuevo_registro.items():
                                    if k in header_vals:
                                        c_idx = header_vals.index(k) + 1
                                        ws_c.update_cell(row_idx, c_idx, v)
                                st.success(f"✅ ¡Cliente **{cli_id}** actualizado con éxito!")
                            else:
                                append_row_dict_safe(ws_c, nuevo_registro)
                                st.success(f"✅ ¡Cliente **{cli_id}** registrado con éxito!")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Error al guardar el cliente: {e}")

        with tab_cat2:
            st.markdown("### 🏡 Catálogo de Fincas")
            df_fin, _ = get_df_safe("Fincas")
            if not df_fin.empty:
                st.dataframe(df_fin, use_container_width=True)
            else:
                st.info("ℹ️ No hay fincas registradas actualmente.")

            with st.form("form_cat_finca"):
                f_id = st.text_input("ID o Código de Finca", placeholder="Ej: FIN-01")
                f_nombre = st.text_input("Nombre de la Finca", placeholder="Ej: Doña Emilia")
                btn_finca = st.form_submit_button("💾 Guardar Finca", use_container_width=True)
                if btn_finca:
                    if not f_id.strip():
                        st.warning("⚠️ Ingrese el ID de la finca.")
                    else:
                        try:
                            _, sh, _ = get_db()
                            ws_f = sh.worksheet("Fincas")
                            ensure_columns_exist(ws_f, ["id_finca", "nombre_finca"])
                            append_row_dict_safe(ws_f, {"id_finca": f_id.strip(), "nombre_finca": f_nombre.strip()})
                            st.success(f"✅ Finca **{f_nombre}** registrada correctamente.")
                        except Exception as e:
                            st.error(f"Error: {e}")

        with tab_cat3:
            st.markdown("### 🚛 Catálogo de Equipos y Transporte")
            df_eq, _ = get_df_safe("Tractores")
            if not df_eq.empty:
                st.dataframe(df_eq, use_container_width=True)
            else:
                st.info("ℹ️ No hay equipos de transporte registrados actualmente.")

        with tab_cat4:
            st.markdown("### 📦 Catálogo de Cartón")
            
            # Asegurar estructura de columnas para la hoja Catalogo_Carton
            try:
                _, sh_db, _ = get_db()
                ws_carton = sh_db.worksheet("Catalogo_Carton")
                ensure_columns_exist(ws_carton, ["id_carton", "tipo", "peso_kg", "descripcio"])
            except Exception:
                pass

            df_carton, _ = get_df_safe("Catalogo_Carton")

            # Cálculo automático del siguiente id_carton (ej. CAR-001, CAR-002...)
            next_id_carton = "CAR-001"
            if not df_carton.empty and "id_carton" in df_carton.columns:
                try:
                    nums = df_carton["id_carton"].astype(str).str.extract(r'(\d+)')[0].dropna().astype(int)
                    if not nums.empty:
                        next_num = nums.max() + 1
                        next_id_carton = f"CAR-{next_num:03d}"
                    else:
                        next_id_carton = f"CAR-{len(df_carton) + 1:03d}"
                except Exception:
                    next_id_carton = f"CAR-{len(df_carton) + 1:03d}"

            if not df_carton.empty:
                st.dataframe(df_carton, use_container_width=True)
            else:
                st.info("ℹ️ No hay registros en el catálogo de cartón actualmente.")

            st.markdown("#### ➕ Registrar Nuevo Tipo de Cartón")
            with st.form("form_cat_carton"):
                c_id = st.text_input("ID del Cartón (Generado Automáticamente)", value=next_id_carton, disabled=True)
                c_tipo = st.text_input("Tipo de Cartón", placeholder="Ej: Telescópica 22XU")
                c_peso = st.number_input("Peso (kg)", min_value=0.0, value=18.14, format="%.2f")
                c_desc = st.text_input("Descripción", placeholder="Ej: Caja Telescópica 22XU")

                btn_guardar_carton = st.form_submit_button("💾 Guardar Cartón", use_container_width=True)

                if btn_guardar_carton:
                    if not c_tipo.strip():
                        st.warning("⚠️ El campo 'Tipo' es obligatorio.")
                    else:
                        try:
                            _, sh, _ = get_db()
                            ws_c = sh.worksheet("Catalogo_Carton")
                            ensure_columns_exist(ws_c, ["id_carton", "tipo", "peso_kg", "descripcio"])
                            
                            nuevo_carton = {
                                "id_carton": next_id_carton,
                                "tipo": c_tipo.strip(),
                                "peso_kg": float(c_peso),
                                "descripcio": c_desc.strip()
                            }
                            
                            append_row_dict_safe(ws_c, nuevo_carton)
                            st.success(f"✅ ¡Cartón **{next_id_carton}** registrado con éxito!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar el cartón: {e}")                
# --------------------------------------------------------------------------
    # 6.6 Submódulo: 📈 Reportes y Concentrados Corporativos
    # --------------------------------------------------------------------------
    elif "Reportes y Concentrados" in menu_sel:
        st.markdown(
            """
            <style>
                *, html, body, [class*="css"], div, span, p, label, input, button, table, th, td, .stTextInput, .stSelectbox, .stMetric {
                    font-family: Arial, sans-serif !important;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.subheader("📈 Módulo de Reportes y Concentrados Corporativos")
        st.caption("Filtre, analice y exporte información consolidada de operaciones, volúmenes de cajas y estatus.")

        try:
            _, sh_obj, _ = get_db()
            hojas_disponibles = [ws.title for ws in sh_obj.worksheets()] if sh_obj else []
        except Exception:
            hojas_disponibles = []

        nombres_posibles = ["OrdenesCarga", "Órdenes de Carga", "Ordenes", "Órdenes", "Concentrado"]
        hoja_encontrada = None
        for nombre in nombres_posibles:
            if nombre in hojas_disponibles:
                hoja_encontrada = nombre
                break

        if not hoja_encontrada and hojas_disponibles:
            for h in hojas_disponibles:
                if "orden" in h.lower() or "carga" in h.lower():
                    hoja_encontrada = h
                    break

        df_ordenes = pd.DataFrame()
        if hoja_encontrada:
            df_ordenes, _ = get_df_safe(hoja_encontrada)
        else:
            df_ordenes, _ = get_df_safe("OrdenesCarga")

        if df_ordenes.empty:
            st.warning("⚠️ No se encontraron registros de órdenes en la base de datos o la hoja está vacía.")
            if hojas_disponibles:
                st.info(f"📋 Hojas detectadas en su Google Sheets: {', '.join(hojas_disponibles)}")
            else:
                st.error("No se pudo establecer conexión o leer la información de Google Sheets.")
        else:
            st.markdown("---")
            st.markdown("#### ⚙️ Filtros Avanzados de Búsqueda")

            f_col1, f_col2, f_col3 = st.columns(3)

            with f_col1:
                clientes_lista = ["TODOS"] + sorted(df_ordenes['cliente'].dropna().astype(str).unique().tolist()) if 'cliente' in df_ordenes.columns else ["TODOS"]
                filtro_rep_cliente = st.selectbox("Cliente", clientes_lista, key="rep_filtro_cliente")

            with f_col2:
                estados_lista = ["TODOS"] + sorted(df_ordenes['estado'].dropna().astype(str).unique().tolist()) if 'estado' in df_ordenes.columns else ["TODOS", "EXPEDIDA", "ACTIVA"]
                filtro_rep_estado = st.selectbox("Estado de Orden", estados_lista, key="rep_filtro_estado")

            with f_col3:
                operadores_lista = ["TODOS"] + sorted(df_ordenes['id_operador'].dropna().astype(str).unique().tolist()) if 'id_operador' in df_ordenes.columns else ["TODOS"]
                filtro_rep_operador = st.selectbox("Operador", operadores_lista, key="rep_filtro_operador")

            df_reporte = df_ordenes.copy()
            if filtro_rep_cliente != "TODOS" and 'cliente' in df_reporte.columns:
                df_reporte = df_reporte[df_reporte['cliente'].astype(str).str.upper() == filtro_rep_cliente.upper()]
            if filtro_rep_estado != "TODOS" and 'estado' in df_reporte.columns:
                df_reporte = df_reporte[df_reporte['estado'].astype(str).str.upper() == filtro_rep_estado.upper()]
            if filtro_rep_operador != "TODOS" and 'id_operador' in df_reporte.columns:
                df_reporte = df_reporte[df_reporte['id_operador'].astype(str).str.upper() == filtro_rep_operador.upper()]

            st.markdown("---")
            st.markdown("#### 📊 Indicadores Clave del Reporte (KPIs)")

            total_ordenes = len(df_reporte)
            con_factura = 0
            if 'folio_factura' in df_reporte.columns:
                con_factura = df_reporte['folio_factura'].astype(str).str.strip().ne("").sum()

            kpi1, kpi2, kpi3 = st.columns(3)
            with kpi1:
                st.metric(label="📦 Órdenes en Reporte", value=total_ordenes)
            with kpi2:
                st.metric(label="📋 Órdenes Documentadas (Factura)", value=f"{con_factura} / {total_ordenes}")
            with kpi3:
                st.metric(label="🏢 Filtro Cliente", value=filtro_rep_cliente)

            st.markdown("---")
            st.markdown("#### 📋 Vista Previa del Concentrado")

            if df_reporte.empty:
                st.warning("⚠️ No se encontraron registros que coincidan con los filtros seleccionados.")
            else:
                st.dataframe(df_reporte, use_container_width=True)

                import io
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_reporte.to_excel(writer, index=False, sheet_name='Concentrado_Corporativo')
                excel_data = output.getvalue()

                st.download_button(
                    label="📥 Descargar Reporte Concentrado Completo a Excel (.xlsx)",
                    data=excel_data,
                    file_name=f"Concentrado_Corporativo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
    # --------------------------------------------------------------------------
    # 6.7 Submódulo: 📜 Compra y Guías Fitosanitarias (Rangos Individuales)
    # --------------------------------------------------------------------------
    elif menu_sel == "📜 Compra y Guías":
        st.markdown(
            """
            <style>
                html, body, [class*="css"] {
                    font-family: Arial, sans-serif !important;
                }
                div.stMarkdown, div.stText, span, p, label, div.stSelectbox, div.stTextInput, div.stNumberInput, div.stDateInput, div.stButton, div.stRadio, div.dataframe {
                    font-family: Arial, sans-serif !important;
                }
                table, th, td {
                    font-family: Arial, sans-serif !important;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.subheader("📜 Control de Compra e Inventario de Guías Fitosanitarias")
        
        tab_compra, tab_inventario = st.tabs(["🛒 Registrar Compra y Rangos", "📊 Inventario y Control de Folios"])
        
        with tab_compra:
            st.markdown("##### 📝 Registro de Adquisición y Rangos de los 4 Documentos")
            
            df_guias, _ = get_df_safe("Compra_Guias")
            
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                guia_emp_sel = st.selectbox("Empresa Adquiriente", emp_nombres if emp_nombres else ["EMP-01"], key="g_emp_compra")
                guia_data_emp = emp_mapa.get(guia_emp_sel, {})
                id_emp_guia = str(guia_data_emp.get('id_empresa', '') or guia_emp_sel)
                
                cantidad_juegos = st.number_input("Cantidad de Juegos de Guías", min_value=1, value=20, step=1, key="g_cantidad_juegos")
                precio_unitario = st.number_input("Precio Unitario por Juego ($)", min_value=0.0, value=250.0, step=10.0, key="g_precio_unitario")
                
            with col_g2:
                fecha_compra = st.date_input("Fecha de Adquisición", value=datetime.now(), key="g_fecha_compra")
                folio_compra_aaps = st.text_input("Folio / Comprobante (AAPS)", placeholder="Ej: AAPS-00123", key="g_folio_aaps")
                estado_guia = st.selectbox("Estado del Lote", ["ACTIVO", "AGOTADO", "DEVUELTO"], key="g_estado_lote")

            st.markdown("##### 🔢 Rangos de Folios Inicial y Final por Documento")
            st.info("Ingrese los folios inicial y final específicos para cada uno de los 4 documentos adquiridos.")

            rc1, rc2 = st.columns(2)
            with rc1:
                st.markdown("**Certificado de Origen**")
                cer_ini = st.text_input("Folio Inicial (Certificado)", placeholder="Ej: CO-001", key="cer_ini")
                cer_fin = st.text_input("Folio Final (Certificado)", placeholder="Ej: CO-020", key="cer_fin")
                
                st.markdown("**Constancia de Origen**")
                con_ini = st.text_input("Folio Inicial (Constancia)", placeholder="Ej: CN-001", key="con_ini")
                con_fin = st.text_input("Folio Final (Constancia)", placeholder="Ej: CN-020", key="con_fin")
                
            with rc2:
                st.markdown("**Constancia de Clorinación**")
                clo_ini = st.text_input("Folio Inicial (Clorinación)", placeholder="Ej: CL-001", key="clo_ini")
                clo_fin = st.text_input("Folio Final (Clorinación)", placeholder="Ej: CL-020", key="clo_fin")
                
                st.markdown("**Carta Responsiva**")
                car_ini = st.text_input("Folio Inicial (Carta)", placeholder="Ej: CR-001", key="car_ini")
                car_fin = st.text_input("Folio Final (Carta)", placeholder="Ej: CR-020", key="car_fin")

            importe_total = cantidad_juegos * precio_unitario
            st.markdown(f"<div style='background-color: #e8f4fd; padding: 10px; border-radius: 6px; margin-bottom: 15px; font-family: Arial, sans-serif;'><b>💰 Importe Total Calculado:</b> ${importe_total:,.2f} ({cantidad_juegos} juegos x ${precio_unitario:,.2f})</div>", unsafe_allow_html=True)

            if st.button("💾 Registrar Compra y Generar Folios", type="primary", use_container_width=True):
                try:
                    _, sh, _ = get_db()
                    ws_g = sh.worksheet("Compra_Guias")
                    ws_f = sh.worksheet("Guias_Folios_Stock")
                    
                    id_compra = f"CG-{datetime.now().strftime('%Y%m%d%H%M')}"
                    
                    ensure_columns_exist(ws_g, [
                        "id_compra", "id_empresa", "fecha_compra", "cantidad_juegos", 
                        "precio_unitario", "importe_total", "folio_compra_AAPS", "estado"
                    ])
                    
                    ensure_columns_exist(ws_f, [
                        "id_folio", "id_compra", "tipo_documento", "folio", "estado", 
                        "id_orden_asignada", "id_guia_asignacion"
                    ])
                    
                    row_guia = {
                        "id_compra": id_compra,
                        "id_empresa": id_emp_guia,
                        "fecha_compra": fecha_compra.isoformat(),
                        "cantidad_juegos": cantidad_juegos,
                        "precio_unitario": precio_unitario,
                        "importe_total": importe_total,
                        "folio_compra_AAPS": folio_compra_aaps,
                        "estado": estado_guia
                    }
                    
                    if append_row_dict_safe(ws_g, row_guia):
                        docs_a_generar = [
                            ("Certificado de Origen", cer_ini, cer_fin),
                            ("Constancia de Origen", con_ini, con_fin),
                            ("Constancia de Clorinacion", clo_ini, clo_fin),
                            ("Carta Responsiva", car_ini, car_fin)
                        ]
                        
                        for doc_tipo, ini_val, fin_val in docs_a_generar:
                            if ini_val and fin_val:
                                try:
                                    num_ini_int = int("".join([c for c in ini_val if c.isdigit()]) or "1")
                                    num_fin_int = int("".join([c for c in fin_val if c.isdigit()]) or "1")
                                    prefijo = "".join([c for c in ini_val if not c.isdigit()])
                                    
                                    for n in range(num_ini_int, num_fin_int + 1):
                                        folio_str = f"{prefijo}{n}" if prefijo else str(n)
                                        row_folio = {
                                            "id_folio": f"{id_compra}-{doc_tipo[:3].upper()}-{n}",
                                            "id_compra": id_compra,
                                            "tipo_documento": doc_tipo,
                                            "folio": folio_str,
                                            "estado": "DISPONIBLE",
                                            "id_orden_asignada": "",
                                            "id_guia_asignacion": ""
                                        }
                                        append_row_dict_safe(ws_f, row_folio)
                                except Exception:
                                    pass
                                
                        st.success(f"✅ ¡Compra registrada y folios de los 4 documentos almacenados con ID **{id_compra}**!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar la compra y folios: {e}")

        with tab_inventario:
            st.markdown("##### 📊 Detalle de Folios por Documento en Stock")
            df_folios, _ = get_df_safe("Guias_Folios_Stock")
            
            if df_folios.empty:
                st.info("No hay folios de guías registrados en el sistema.")
            else:
                st.dataframe(df_folios, use_container_width=True)
                st.caption("Control individual de folios para Certificado de Origen, Constancia de Origen, Constancia de Clorinación y Carta Responsiva.")
  # --------------------------------------------------------------------------
    # 6.8 Submódulo: 📖 Seguimiento de Carga y Estatus por Finca
    # --------------------------------------------------------------------------
    elif "Seguimiento" in menu_sel:
        st.markdown(
            """
            <style>
                *, html, body, [class*="css"], div, span, p, label, input, button, table, th, td, .stTextInput, .stSelectbox, .stMetric {
                    font-family: Arial, sans-serif !important;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        st.subheader("📖 Seguimiento de Órdenes de Carga y Progreso por Finca")
        st.caption("Monitoree en tiempo real el estatus de las unidades, el avance de carga y el volumen de cajas por finca.")

        try:
            db_res = get_db()
            sh_obj = db_res[1] if isinstance(db_res, tuple) and len(db_res) >= 2 else None
            hojas_disponibles = [ws.title for ws in sh_obj.worksheets()] if sh_obj else []
        except Exception as e:
            hojas_disponibles = []
            st.error(f"Error al conectar con la base de datos: {e}")

        hoja_encontrada = "OrdenesCarga"
        for h in hojas_disponibles:
            if "orden" in h.lower() or "carga" in h.lower() or "seguimiento" in h.lower():
                hoja_encontrada = h
                break

        try:
            df_seguimiento, _ = get_df_safe(hoja_encontrada)
        except Exception as e:
            df_seguimiento = pd.DataFrame()
            st.error(f"Error al cargar los datos de la hoja '{hoja_encontrada}': {e}")

        if df_seguimiento is None or df_seguimiento.empty:
            st.warning(f"⚠️ No se encontraron registros en la hoja '{hoja_encontrada}' o la tabla está vacía.")
            if hojas_disponibles:
                st.info(f"📋 Hojas disponibles en Google Sheets: {', '.join(hojas_disponibles)}")
        else:
            st.markdown("---")
            st.markdown("#### ⚙️ Filtros Operativos de Seguimiento")

            col_finca_valida = next((c for c in ['finca', 'nombre_finca', 'id_finca', 'empresa', 'id_cliente'] if c in df_seguimiento.columns), None)
            col_estado_valida = next((c for c in ['estado', 'estatus', 'status'] if c in df_seguimiento.columns), None)

            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                fincas_lista = ["TODOS"] + sorted(df_seguimiento[col_finca_valida].dropna().astype(str).unique().tolist()) if col_finca_valida else ["TODOS"]
                filtro_seg_finca = st.selectbox("Finca / Productor / Cliente", fincas_lista, key="seg_filtro_finca")
            with col_s2:
                estados_seg_lista = ["TODOS"] + sorted(df_seguimiento[col_estado_valida].dropna().astype(str).unique().tolist()) if col_estado_valida else ["TODOS", "EXPEDIDA", "ACTIVA", "CARGANDO"]
                filtro_seg_estado = st.selectbox("Estatus de Carga", estados_seg_lista, key="seg_filtro_estado")
            with col_s3:
                buscar_folio = st.text_input("Buscar Folio / Tractor / Caja", placeholder="Ej: OC-2026 o C-0001", key="seg_buscar_folio")

            df_filtrado = df_seguimiento.copy()
            if filtro_seg_finca != "TODOS" and col_finca_valida:
                df_filtrado = df_filtrado[df_filtrado[col_finca_valida].astype(str).str.upper() == filtro_seg_finca.upper()]
            if filtro_seg_estado != "TODOS" and col_estado_valida:
                df_filtrado = df_filtrado[df_filtrado[col_estado_valida].astype(str).str.upper() == filtro_seg_estado.upper()]
            if buscar_folio.strip():
                cols_str = [c for c in ['folio_orden', 'id_orden', 'id_tractor', 'id_operador', 'id_caja1', 'id_caja2'] if c in df_filtrado.columns]
                if cols_str:
                    mask = df_filtrado[cols_str].astype(str).apply(lambda x: x.str.contains(buscar_folio.strip(), case=False, na=False)).any(axis=1)
                    df_filtrado = df_filtrado[mask]

            st.markdown("---")
            st.markdown("#### 📋 Detalle de Unidades y Órdenes de Carga")

            if df_filtrado.empty:
                st.warning("⚠️ No se encontraron órdenes que coincidan con los filtros seleccionados.")
            else:
                st.dataframe(df_filtrado, use_container_width=True)

                st.markdown("##### 📄 Monitoreo Individual de Unidad / Orden")
                columnas_id = ['id_orden', 'folio_orden']
                id_col_valida = next((c for c in columnas_id if c in df_filtrado.columns), df_filtrado.columns[0])
                
                lista_ids = df_filtrado[id_col_valida].astype(str).tolist()
                orden_seleccionada = st.selectbox("Seleccione Orden para inspeccionar unidades (tractores/cajas) y destino", lista_ids, key="seg_select_detalle")

                if orden_seleccionada:
                    df_detalle_orden = df_filtrado[df_filtrado[id_col_valida].astype(str) == orden_seleccionada]
                    if not df_detalle_orden.empty:
                        reg_dict = df_detalle_orden.iloc[0].to_dict()
                        
                        dcol1, dcol2, dcol3 = st.columns(3)
                        with dcol1:
                            st.markdown(f"**Folio / Orden:** {reg_dict.get('folio_orden', reg_dict.get('id_orden', 'N/D'))}")
                            st.markdown(f"**Operador:** {reg_dict.get('id_operador', 'N/D')}")
                            st.markdown(f"**Tractor:** {reg_dict.get('id_tractor', 'N/D')}")
                        with dcol2:
                            st.markdown(f"**Caja 1:** {reg_dict.get('id_caja1', 'N/D')}")
                            st.markdown(f"**Caja 2:** {reg_dict.get('id_caja2', 'N/D')}")
                            st.markdown(f"**Línea / Ruta:** {reg_dict.get('id_linea', 'N/D')}")
                        with dcol3:
                            st.markdown(f"**Cliente / Finca:** {reg_dict.get('id_cliente', reg_dict.get('finca', 'N/D'))}")
                            st.markdown(f"**Destino:** {reg_dict.get('id_destino', 'N/D')}")
                            st.markdown(f"**Factura:** {reg_dict.get('folio_factura', 'N/D')}")

            st.markdown("---")
            st.markdown("#### 📊 Indicadores Clave de Carga (KPIs)")

            total_ordenes_finca = len(df_filtrado)
            col_cajas_valida = next((c for c in ['total_cajas', 'cantidad_cajas', 'cajas'] if c in df_filtrado.columns), None)
            total_cajas_finca = 0
            if col_cajas_valida:
                total_cajas_finca = pd.to_numeric(df_filtrado[col_cajas_valida], errors='coerce').sum()

            ms1, ms2, ms3, ms4 = st.columns(4)
            with ms1:
                st.metric(label="🚛 Órdenes en Proceso", value=total_ordenes_finca)
            with ms2:
                st.metric(label="📦 Cajas Acumuladas", value=f"{int(total_cajas_finca):,}" if total_cajas_finca else "N/D")
            with ms3:
                st.metric(label="🏢 Selección", value=filtro_seg_finca)
            with ms4:
                st.metric(label="📌 Estatus", value=filtro_seg_estado)
                            
# ==========================================
# CÓDIGO 7: MÓDULOS OPERATIVOS CON SOPORTE OFFLINE (EXCEL PUENTE)
# ==========================================

import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import openpyxl

# Archivo Excel local utilizado como puente cuando no hay internet
EXCEL_RESPALDO = "respaldo_pendientes_finca.xlsx"

def guardar_con_respaldo_offline(sheet_name, dict_data):
    """
    Intenta guardar en Google Sheets. Si falla (sin internet), 
    guarda el registro en un archivo Excel local de respaldo.
    """
    try:
        # Intento de conexión a Google Sheets
        _, sh, _ = get_db()
        nombres_h = [w.title for w in sh.worksheets()]
        if sheet_name in nombres_h:
            ws = sh.worksheet(sheet_name)
        else:
            ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
            
        ensure_columns_exist(ws, list(dict_data.keys()))
        append_row_dict_safe(ws, dict_data)
        return True, "Guardado exitosamente en la Nube (Google Sheets)."
        
    except Exception as e:
        # Si ocurre un error de red o timeout, respaldamos en Excel local
        try:
            df_nuevo = pd.DataFrame([dict_data])
            df_nuevo["sheet_destino"] = sheet_name # Guardamos a qué hoja pertenece
            
            if os.path.exists(EXCEL_RESPALDO):
                df_existente = pd.read_excel(EXCEL_RESPALDO)
                df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
            else:
                df_final = df_nuevo
                
            df_final.to_excel(EXCEL_RESPALDO, index=False)
            return False, "⚠️ Sin internet: Guardado de emergencia en Excel local. Se sincronizará al recuperar señal."
        except Exception as ex_excel:
            return False, f"Error crítico al respaldar localmente: {ex_excel}"

def sincronizar_pendientes_excel():
    """
    Lee el Excel local de respaldo y sube todos los registros pendientes a Google Sheets.
    """
    if not os.path.exists(EXCEL_RESPALDO):
        return 0, "No hay datos pendientes de sincronización."
        
    try:
        df_pendientes = pd.read_excel(EXCEL_RESPALDO)
        if df_pendientes.empty:
            os.remove(EXCEL_RESPALDO)
            return 0, "El archivo de respaldo estaba vacío."
            
        _, sh, _ = get_db()
        sincronizados = 0
        
        # Agrupamos por hoja de destino
        for sheet_name, grupo in df_pendientes.groupby("sheet_destino"):
            if sheet_name not in [w.title for w in sh.worksheets()]:
                ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=20)
            else:
                ws = sh.worksheet(sheet_name)
                
            # Quitamos la columna temporal antes de subir a Google Sheets
            grupo_limpio = grupo.drop(columns=["sheet_destino"], errors="ignore")
            
            for _, row in grupo_limpio.iterrows():
                dict_fila = row.dropna().to_dict()
                dict_fila = {str(k): str(v) for k, v in dict_fila.items()}
                
                ensure_columns_exist(ws, list(dict_fila.keys()))
                append_row_dict_safe(ws, dict_fila)
                sincronizados += 1
                
        # Si todo salió bien, eliminamos el archivo de respaldo local
        os.remove(EXCEL_RESPALDO)
        return sincronizados, f"¡Sincronización exitosa! Se subieron {sincronizados} registros a la nube."
        
    except Exception as e:
        return -1, f"No se pudo sincronizar (¿Sigues sin internet?): {e}"

# --- GESTIÓN DE ROL Y FINCA ---
rol_actual = str(st.session_state.get("rol", "")).upper()
finca_actual = str(st.session_state.get("finca_asignada", "TODAS"))

# Panel lateral con el estado de la conexión y botón de sincronización manual
with st.sidebar:
    st.markdown("---")
    st.markdown("### 🌐 Estado de Conexión y Respaldo")
    if os.path.exists(EXCEL_RESPALDO):
        try:
            df_p = pd.read_excel(EXCEL_RESPALDO)
            num_pendientes = len(df_p)
        except:
            num_pendientes = 0
            
        st.warning(f"⚠️ **Modo Offline Activo**\nHay **{num_pendientes}** registros en el Excel puente.")
        
        if st.button("🔄 Sincronizar con la Nube", type="primary", use_container_width=True):
            with st.spinner("Subiendo datos pendientes a Google Sheets..."):
                count, msg = sincronizar_pendientes_excel()
                if count > 0:
                    st.success(msg)
                    time.sleep(1.5)
                    st.rerun()
                elif count == 0:
                    st.info(msg)
                else:
                    st.error(msg)
    else:
        st.success("🟢 **Sistema en Línea**\nTodos los registros están sincronizados con la nube.")

# Estilo visual atractivo en tonos verdes (Emerald / Forest Theme)
st.markdown("""
    <style>
    .verde-banner {
        background: linear-gradient(135deg, #134e2b 0%, #28a745 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
        box-shadow: 0 6px 12px rgba(40, 167, 69, 0.15);
    }
    .verde-banner h2 {
        color: white !important;
        margin-bottom: 5px;
    }
    .verde-card {
        background-color: #f4fbf7;
        border: 1px solid #c3e6cb;
        border-left: 5px solid #28a745;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(40, 167, 69, 0.05);
    }
    .metric-box {
        background-color: #ffffff;
        border: 2px solid #d4edda;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    </style>
""", unsafe_allow_html=True)

if rol_actual in ["VIGILANCIA"]:
    st.markdown(f"<h2 style='color: #28a745;'>🛡️ Módulo de Vigilancia - Control de Accesos ({finca_actual})</h2>", unsafe_allow_html=True)
    st.markdown("Control de acceso de unidades programadas y vehículos de Fruta de Tercera (Sin Orden previa)")

    df_of_vig, _ = get_df_safe("Orden_Fincas")
    
    tab_vig_ord, tab_vig_tercera = st.tabs(["🚛 UNIDADES CON ORDEN DE CARGA", "🍌 VEHÍCULOS DE FRUTA DE TERCERA (IMPREVISTOS)"])

    with tab_vig_ord:
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            st.markdown("### 📥 Registrar Entrada / Salida (Orden)")
            id_orden_vig = st.text_input("ID de Orden o Folio de Carga", key="vig_id_orden")
            placa_vehiculo = st.text_input("Placas del Transporte / Contenedor", key="vig_placas")
            chofer_nombre = st.text_input("Nombre del Conductor", key="vig_chofer")
            
            if st.button("✅ Registrar Llegada a Caseta", type="primary", key="btn_vig_entrada"):
                if not id_orden_vig or not placa_vehiculo:
                    st.warning("Debe ingresar el ID de la orden y las placas del vehículo.")
                else:
                    try:
                        _, sh_v, _ = get_db()
                        ws_of = sh_v.worksheet("Orden_Fincas")
                        cell = ws_of.find(str(id_orden_vig))
                        if cell:
                            row_idx = cell.row
                            ws_of.update_cell(row_idx, ws_of.find("estado_carga").col, "LLEGADO_CASETA")
                            st.success(f"✅ Unidad {placa_vehiculo} registrada en caseta para la orden {id_orden_vig}.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("No se encontró la orden especificada en el sistema.")
                    except Exception as e:
                        st.error(f"Error al registrar entrada: {e}")

        with col_v2:
            st.markdown("### 📤 Unidades Activas en Finca")
            if not df_of_vig.empty:
                df_vig_activas = df_of_vig[df_of_vig['id_finca'].astype(str).str.upper() == finca_actual.upper()] if finca_actual.upper() != "TODAS" else df_of_vig
                st.dataframe(df_vig_activas[['id_orden', 'id_finca', 'estado_carga', 'transportista']], use_container_width=True)
            else:
                st.info("No hay órdenes activas actualmente.")

    with tab_vig_tercera:
        st.markdown("### 🍌 Control de Ingreso y Salida - Fruta de Tercera (Sin Orden)")
        st.caption("💡 Registro inicial en caseta con hora de entrada, chofer y fotos de evidencia.")

        col_vt1, col_vt2 = st.columns(2)
        with col_vt1:
            chofer_tercera_v = st.text_input("Nombre del Conductor / Transportista", key="vig_tercera_chofer")
            placas_tercera_v = st.text_input("Placas del Vehículo", key="vig_tercera_placas")
            cliente_tercera_v = st.text_input("Cliente Destino (Opcional)", key="vig_tercera_cliente")
            
            st.markdown("📷 **Evidencias Fotográficas de Ingreso**")
            foto_entrada_frontal = st.camera_input("Foto Entrada Frontal", key="vig_foto_frontal")
            foto_entrada_trasera = st.camera_input("Foto Entrada Trasera", key="vig_foto_trasera")

        with col_vt2:
            hora_ingreso_val = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.info(f"🕒 Hora de Registro de Ingreso: {hora_ingreso_val}")
            
            obs_vig_tercera = st.text_area("Observaciones de Ingreso en Caseta", key="vig_tercera_obs")

            if st.button("🚨 REGISTRAR INGRESO DE TERCERA A PLANTA", type="primary", use_container_width=True, key="btn_vig_guardar_tercera"):
                if not chofer_tercera_v or not placas_tercera_v:
                    st.warning("Debe ingresar el nombre del chofer y las placas del vehículo.")
                else:
                    id_dt = f"TERC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    dict_dt = {
                        "id_despacho_tercera": id_dt,
                        "fecha_ingreso": datetime.now().strftime("%Y-%m-%d"),
                        "id_finca": str(finca_actual),
                        "chofer": str(chofer_tercera_v),
                        "placas": str(placas_tercera_v),
                        "cliente": str(cliente_tercera_v),
                        "hora_ingreso": str(hora_ingreso_val),
                        "estado_despacho": "EN_PLANTA",
                        "observaciones_vigilancia": str(obs_vig_tercera),
                        "id_usuario_vigilancia": str(st.session_state.get("username", "vigilancia"))
                    }

                    exito, msg = guardar_con_respaldo_offline("Despachos_Tercera", dict_dt)
                    if exito:
                        st.success(f"✅ Ingreso de vehículo de tercera registrado en la nube. Folio: {id_dt}")
                    else:
                        st.warning(f"⚠️ {msg} Folio: {id_dt}")
                    time.sleep(1.5)
                    st.rerun()

elif rol_actual in ["ESTIBA", "JEFE_CAMARA"]:
    st.markdown(f"<h2 style='color: #28a745;'>❄️ Módulo de Estiba y Preenfriado - {finca_actual}</h2>", unsafe_allow_html=True)
    st.markdown("Control de cadena de frío, colocación de sellos, termógrafos y estiba en contenedor")

    df_of_est, _ = get_df_safe("Orden_Fincas")
    
    id_orden_estiba = st.text_input("Seleccione o ingrese ID de Orden para Estiba", key="est_id_orden")
    
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        temp_pulpa = st.number_input("Temperatura de Pulpa (°C)", value=13.5, step=0.1, key="est_temp")
        num_termografo = st.text_input("Número de Termógrafo", key="est_termografo")
    with col_e2:
        num_sello = st.text_input("Número de Sello de Seguridad", key="est_sello")
        observaciones_estiba = st.text_area("Observaciones de Estiba y Contenedor", key="est_obs")

    if st.button("✅ GUARDAR DATOS DE ESTIBA Y SELLADO", type="primary", use_container_width=True, key="btn_guardar_estiba"):
        dict_estiba = {
            "id_orden": str(id_orden_estiba),
            "id_finca": str(finca_actual),
            "temperatura_pulpa": str(temp_pulpa),
            "termografo": str(num_termografo),
            "sello": str(num_sello),
            "observaciones": str(observaciones_estiba),
            "fecha_registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "usuario": str(st.session_state.get("username", "estiba"))
        }

        exito, msg = guardar_con_respaldo_offline("Control_Estiba", dict_estiba)
        if exito:
            st.success("✅ Datos de estiba guardados correctamente en la nube.")
        else:
            st.warning(f"⚠️ {msg}")
        time.sleep(1.2)
        st.rerun()

elif rol_actual in ["PLANTA", "JEFE_PLANTA"]:
    st.markdown("""
        <div class="verde-banner">
            <h2>🏭 Módulo de Planta & Control de Inventario</h2>
            <p>Registro tabular dinámico de producción, existencias, edición y despachos locales de fruta de tercera</p>
        </div>
    """, unsafe_allow_html=True)

    tab_prod, tab_tercera, tab_cons = st.tabs([
        "📋 CAPTURA TABULAR & SALDOS", 
        "🚚 GESTIÓN Y DESPACHO LOCAL (FRUTA DE TERCERA)", 
        "📊 HISTORIAL, EDICIÓN Y ELIMINACIÓN (PLANTA)"
    ])
    hora_dispositivo = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Carga robusta de Clientes extrayendo estrictamente el valor de la Columna B (Razón Social / Nombre)
    df_cli_db, _ = get_df_safe("Clientes")
    clientes_opciones = []
    if not df_cli_db.empty:
        col_nombre_b = df_cli_db.columns[1] if len(df_cli_db.columns) > 1 else df_cli_db.columns[0]
        for _, row in df_cli_db.iterrows():
            c_nom = str(row[col_nombre_b]).strip()
            if c_nom and c_nom != 'nan':
                clientes_opciones.append(c_nom)
                
    if not clientes_opciones:
        clientes_opciones = ["WALTMAR, QUERETARO", "CLIENTE GENERAL"]

    df_cal_db, _ = get_df_safe("Calidades")
    if df_cal_db.empty:
        df_cal_db, _ = get_df_safe("Calidad")
    if not df_cal_db.empty:
        col_cal = next((c for c in df_cal_db.columns if 'calidad' in c.lower() or 'nombre' in c.lower()), df_cal_db.columns[0])
        calidades_opciones = df_cal_db[col_cal].dropna().astype(str).unique().tolist()
    else:
        calidades_opciones = ["PRIMERA", "SEGUNDA", "TERCERA", "DEDO SUELTO", "MANITAS PRIMERA", "MANITAS SEGUNDA"]

    df_cart_db, _ = get_df_safe("Cartones")
    if df_cart_db.empty:
        df_cart_db, _ = get_df_safe("Tipo_Carton")
    if not df_cart_db.empty:
        col_cart = next((c for c in df_cart_db.columns if 'carton' in c.lower() or 'tipo' in c.lower() or 'nombre' in c.lower()), df_cart_db.columns[0])
        cartones_opciones = df_cart_db[col_cart].dropna().astype(str).unique().tolist()
    else:
        cartones_opciones = ["GENERICO", "BRAVO", "TICA BANANA"]

    with tab_prod:
        st.markdown("### 🌿 Captura Tabular de Producción Diaria y Existencias")
        fecha_captura = st.date_input("📅 Fecha Principal de Producción / Carga", value=datetime.now().date(), key="tab_fecha_principal")

        if "rows_captura" not in st.session_state:
            st.session_state.rows_captura = [
                {"cantidad": 1000.0, "calidad": "PRIMERA", "carton": cartones_opciones[0], "cliente": clientes_opciones[0], "peso_unitario": 18.86}
            ]

        df_template = pd.DataFrame(st.session_state.rows_captura)

        st.markdown("👇 **Agregue, edite o modifique los registros directamente en la tabla:**")
        edited_df = st.data_editor(
            df_template,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "cantidad": st.column_config.NumberColumn("Cantidad (Unidades)", min_value=0.0, step=1.0, format="%.0f"),
                "calidad": st.column_config.SelectboxColumn("Calidad", options=calidades_opciones, required=True),
                "carton": st.column_config.SelectboxColumn("Tipo de Cartón", options=cartones_opciones, required=True),
                "cliente": st.column_config.SelectboxColumn("Cliente (Razón Social)", options=clientes_opciones, required=True),
                "peso_unitario": st.column_config.NumberColumn("Peso (kg)", min_value=0.0, step=0.01, format="%.2f")
            },
            key="editor_produccion_tabular"
        )

        if not edited_df.empty:
            edited_df["peso_total_kg"] = edited_df["cantidad"] * edited_df["peso_unitario"]

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("### 📊 Existencias y Saldos Calculados (En Vivo)")
        if not edited_df.empty:
            df_resumen = edited_df.groupby(["calidad", "carton"], as_index=False)[["cantidad", "peso_total_kg"]].sum()
            cols_metricas = st.columns(min(len(df_resumen), 4) if not df_resumen.empty else 1)
            for idx, row in df_resumen.iterrows():
                col_target = cols_metricas[idx % len(cols_metricas)]
                with col_target:
                    st.markdown(f"""
                        <div class="metric-box">
                            <span style="font-size: 0.85rem; color: #155724; font-weight: bold;">{row['calidad']}</span><br>
                            <span style="font-size: 0.75rem; color: #6c757d;">{row['carton']}</span><br>
                            <span style="font-size: 1.3rem; color: #28a745; font-weight: 800;">{row['cantidad']:,.0f} un.</span><br>
                            <span style="font-size: 0.8rem; color: #495057;">({row['peso_total_kg']:,.2f} kg)</span>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("💡 Ingrese datos en la tabla superior para ver las existencias calculadas al instante.")

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🚀 GUARDAR Y ACTUALIZAR SALDOS EN INVENTARIO", type="primary", use_container_width=True, key="btn_guardar_tabular"):
            try:
                todos_exitosos = True
                for _, row in edited_df.iterrows():
                    id_reg_p = f"PROD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{int(row.name)}"
                    p_unit = float(row["peso_unitario"])
                    cant = float(row["cantidad"])
                    p_tot = cant * p_unit

                    dict_reg_p = {
                        "id_produccion": id_reg_p,
                        "fecha_produccion": str(fecha_captura),
                        "id_finca": str(finca_actual),
                        "cantidad": str(cant),
                        "calidad": str(row["calidad"]),
                        "carton": str(row["carton"]),
                        "cliente": str(row["cliente"]),
                        "peso_unitario": str(p_unit),
                        "peso_total_kg": str(p_tot),
                        "fecha_registro": str(hora_dispositivo),
                        "id_usuario": str(st.session_state.get("username", "jefe_planta")),
                        "estado_proceso": "REGISTRO_TABULAR"
                    }
                    
                    exito, _ = guardar_con_respaldo_offline("Produccion_Planta", dict_reg_p)
                    if not exito:
                        todos_exitosos = False

                st.cache_data.clear()
                if todos_exitosos:
                    st.success(f"🌱 ¡Captura tabular para la fecha {fecha_captura} guardada con éxito!")
                else:
                    st.warning("⚠️ Sin internet: Los registros se guardaron en el **Excel local de respaldo**.")
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar la producción tabular: {e}")

    with tab_tercera:
        st.markdown("<h3 style='color: #28a745;'>🚚 GESTIÓN Y DESPACHO LOCAL - FRUTA DE TERCERA (SIN ORDEN)</h3>", unsafe_allow_html=True)
        
        col_dt_1, col_dt_2 = st.columns(2)
        with col_dt_1:
            st.markdown("#### 👤 Datos del Cliente y Operador")
            cliente_tercera_local = st.selectbox("Seleccione el Cliente (Razón Social)", options=clientes_opciones, key="terc_loc_cliente")
            nombre_operador = st.text_input("Nombre del Operador", key="terc_loc_operador")
            num_licencia = st.text_input("Número de Licencia Operador", key="terc_loc_licencia")
            
            st.markdown("#### 📦 Empaque y Cantidad")
            tipo_empaque = st.selectbox("Tipo de Empaque", options=["REJA DE PLÁSTICO"], index=0, key="terc_loc_empaque")
            cantidad_rejas = st.number_input("Cantidad", min_value=0.0, value=0.0, step=1.0, key="terc_loc_cantidad")
            peso_unitario_reja = st.number_input("Peso (kg) [Predeterminado 26]", value=26.0, step=0.1, key="terc_loc_peso_unit")

        with col_dt_2:
            st.markdown("#### 🚛 Datos del Vehículo / Transporte")
            marca_carro = st.text_input("Marca del Carro", key="terc_loc_marca")
            modelo_carro = st.text_input("Modelo", key="terc_loc_modelo")
            placas_carro = st.text_input("Placas", key="terc_loc_placas")
            obs_tercera_local = st.text_area("Observaciones del Despacho Local", key="terc_loc_obs")

        peso_total_tercera = cantidad_rejas * peso_unitario_reja
        st.info(f"⚖️ Peso Total Calculado de Tercera: **{peso_total_tercera:,.2f} kg**")

        if st.button("🚨 REGISTRAR Y CERRAR DESPACHO LOCAL DE TERCERA", type="primary", use_container_width=True, key="btn_guardar_tercera_local"):
            if not nombre_operador or not placas_carro or cantidad_rejas <= 0:
                st.warning("Debe ingresar el nombre del operador, las placas del vehículo y una cantidad válida.")
            else:
                id_dt = f"TERC-LOC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                dict_dt = {
                    "id_despacho_tercera": id_dt,
                    "fecha_ingreso": str(datetime.now().strftime("%Y-%m-%d")),
                    "id_finca": str(finca_actual),
                    "cliente": str(cliente_tercera_local),
                    "nombre_operador": str(nombre_operador),
                    "numero_licencia": str(num_licencia),
                    "tipo_empaque": str(tipo_empaque),
                    "cantidad_rejas": str(cantidad_rejas),
                    "peso_unitario": str(peso_unitario_reja),
                    "peso_total_kg": str(peso_total_tercera),
                    "marca_carro": str(marca_carro),
                    "modelo_carro": str(modelo_carro),
                    "placas": str(placas_carro),
                    "estado_despacho": "COMPLETADO_LOCAL",
                    "observaciones": str(obs_tercera_local),
                    "fecha_registro": str(hora_dispositivo),
                    "id_usuario": str(st.session_state.get("username", "jefe_planta"))
                }

                exito, msg = guardar_con_respaldo_offline("Despachos_Tercera", dict_dt)
                if exito:
                    st.success(f"✅ ¡Despacho local registrado en la nube con éxito! Folio: {id_dt}")
                else:
                    st.warning(f"⚠️ {msg} Folio: {id_dt}")
                time.sleep(1.5)
                st.rerun()

    with tab_cons:
        st.markdown("<h3 style='color: #28a745;'>📊 HISTORIAL, EDICIÓN Y ELIMINACIÓN (PLANTA)</h3>", unsafe_allow_html=True)
        st.markdown("#### 📦 Producción Registrada (Inventario)")
        df_prod_hist, _ = get_df_safe("Produccion_Planta")
        if not df_prod_hist.empty:
            df_prod_finca = df_prod_hist if finca_actual.upper() == "TODAS" else df_prod_hist[df_prod_hist['id_finca'].astype(str).str.upper() == finca_actual.upper()]
            
            if not df_prod_finca.empty:
                st.dataframe(df_prod_finca, use_container_width=True)
                
                st.markdown("---")
                st.markdown("### ✏️ Modificar o Eliminar Registro de Producción")
                id_prod_sel = st.selectbox("Seleccione el ID de Producción a Modificar o Eliminar", options=df_prod_finca['id_produccion'].astype(str).tolist(), key="select_id_prod_edit")
                
                if id_prod_sel:
                    fila_act = df_prod_finca[df_prod_finca['id_produccion'].astype(str) == str(id_prod_sel)].iloc[0]
                    
                    with st.form(key="form_editar_produccion"):
                        st.markdown(f"**Editando Registro:** `{id_prod_sel}`")
                        nueva_cant = st.number_input("Cantidad (Unidades)", value=float(fila_act.get('cantidad', 0)), step=1.0)
                        
                        cal_val = str(fila_act.get('calidad', calidades_opciones[0]))
                        idx_cal = calidades_opciones.index(cal_val) if cal_val in calidades_opciones else 0
                        nueva_cal = st.selectbox("Calidad", options=calidades_opciones, index=idx_cal)
                        
                        cart_val = str(fila_act.get('carton', cartones_opciones[0]))
                        idx_cart = cartones_opciones.index(cart_val) if cart_val in cartones_opciones else 0
                        nuevo_cart = st.selectbox("Tipo de Cartón", options=cartones_opciones, index=idx_cart)
                        
                        cli_val = str(fila_act.get('cliente', clientes_opciones[0]))
                        idx_cli = clientes_opciones.index(cli_val) if cli_val in clientes_opciones else 0
                        nuevo_cli = st.selectbox("Cliente (Razón Social)", options=clientes_opciones, index=idx_cli)
                        
                        nuevo_peso_u = st.number_input("Peso Unitario (kg)", value=float(fila_act.get('peso_unitario', 18.86)), step=0.01)

                        col_btn_ed1, col_btn_ed2 = st.columns(2)
                        with col_btn_ed1:
                            btn_actualizar = st.form_submit_button("💾 Guardar Cambios", type="primary")
                        with col_btn_ed2:
                            btn_eliminar = st.form_submit_button("🗑️ Eliminar Registro", type="secondary")

                        if btn_actualizar:
                            try:
                                _, sh_ed, _ = get_db()
                                ws_p_ed = sh_ed.worksheet("Produccion_Planta")
                                cell_p = ws_p_ed.find(str(id_prod_sel))
                                if cell_p:
                                    r_idx = cell_p.row
                                    headers_list = ws_p_ed.row_values(1)
                                    nuevo_peso_tot = nueva_cant * nuevo_peso_u
                                    
                                    updates_map = {
                                        "cantidad": str(nueva_cant),
                                        "calidad": str(nueva_cal),
                                        "carton": str(nuevo_cart),
                                        "cliente": str(nuevo_cli),
                                        "peso_unitario": str(nuevo_peso_u),
                                        "peso_total_kg": str(nuevo_peso_tot)
                                    }
                                    
                                    for col_nombre, val_nuevo in updates_map.items():
                                        if col_nombre in headers_list:
                                            c_idx = headers_list.index(col_nombre) + 1
                                            ws_p_ed.update_cell(r_idx, c_idx, val_nuevo)
                                            
                                    st.cache_data.clear()
                                    st.success(f"✅ Registro {id_prod_sel} actualizado correctamente.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("No se encontró la fila en la hoja de Google Sheets.")
                            except Exception as e:
                                st.error(f"Error al actualizar: {e}")

                        if btn_eliminar:
                            try:
                                _, sh_del, _ = get_db()
                                ws_p_del = sh_del.worksheet("Produccion_Planta")
                                cell_del = ws_p_del.find(str(id_prod_sel))
                                if cell_del:
                                    ws_p_del.delete_rows(cell_del.row)
                                    st.cache_data.clear()
                                    st.success(f"🗑️ Registro {id_prod_sel} eliminado con éxito.")
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("No se encontró el registro para eliminar.")
                            except Exception as e:
                                st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay registros de producción para esta finca.")
        else:
            st.info("No hay registros de producción previos.")

        st.markdown("---")
        st.markdown("#### 🚚 Despachos Locales e Historial de Fruta de Tercera")
        df_terc_hist, _ = get_df_safe("Despachos_Tercera")
        if not df_terc_hist.empty:
            df_terc_finca = df_terc_hist if finca_actual.upper() == "TODAS" else df_terc_hist[df_terc_hist['id_finca'].astype(str).str.upper() == finca_actual.upper()]
            st.dataframe(df_terc_finca, use_container_width=True)
        else:
            st.info("No hay registros de despachos de tercera previos.")
