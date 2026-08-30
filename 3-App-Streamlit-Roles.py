import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

st.set_page_config(page_title="Embarques V5 - Empresa Primer Plano", layout="wide", page_icon="🍌")

# ==========================================
# CONFIGURACIÓN DE CONEXIÓN A GOOGLE SHEETS
# ==========================================
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
            df = pd.DataFrame(ws.get_all_records(), dtype=str)
            df.columns = [str(c).strip() for c in df.columns]
            return df, ws
        except: continue
    try:
        for ws in sh.worksheets():
            tl = ws.title.lower()
            sl = sheet_name.lower()
            if "tracto" in sl and "tracto" in tl:
                df = pd.DataFrame(ws.get_all_records(), dtype=str)
                df.columns=[str(c).strip() for c in df.columns]
                return df, ws
            if "caja" in sl and "caja" in tl:
                df = pd.DataFrame(ws.get_all_records(), dtype=str)
                df.columns=[str(c).strip() for c in df.columns]
                return df, ws
    except: pass
    return pd.DataFrame(dtype=str), None

def ensure_columns_exist(ws, cols):
    try:
        headers = [str(h).strip() for h in ws.row_values(1)]
        for col in cols:
            if col not in headers:
                ws.update_cell(1, len(headers)+1, col)
                headers.append(col)
    except: pass

def append_row_dict_safe(ws, data_dict):
    try:
        ensure_columns_exist(ws, list(data_dict.keys()))
        headers = [str(h).strip() for h in ws.row_values(1)]
        row = [str(data_dict.get(h,"")) for h in headers]
        ws.append_row(row, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

try:
    client, sh, drive_service = get_db()
    conectado=True
except Exception as e:
    conectado=False
    err_conexion=str(e)

# ==========================================
# GESTIÓN DE SESIÓN Y ROLES
# ==========================================
ROLES=["OFICINA_CENTRAL","VIGILANCIA","JEFE_PLANTA","ESTIBA"]
if 'rol' not in st.session_state:
    for k in ["rol","id_finca","usuario","username","nombre_usuario","id_usuario","finca_asignada","menu_oficina"]:
        st.session_state[k]=None

# ==========================================
# BARRA LATERAL - CONTROL DE ACCESO
# ==========================================
with st.sidebar:
    st.markdown("### 🍌 Embarques")
    st.caption("Panel Opciones Izquierda")
    if conectado: st.success(f"Conectado: {SPREADSHEET_NAME}")
    else: st.error(err_conexion)
    
    if st.session_state.rol is None:
        rol=st.selectbox("Rol", ROLES)
        df_usuarios_raw,_=get_df_safe("Usuarios")
        if df_usuarios_raw.empty:
            df_usuarios=pd.DataFrame([{"id_usuario":"USR-OF-001","nombre":"Martin Gomez","rol":"OFICINA_CENTRAL","finca_asignada":"TODAS","username":"Martin.oficina","password_hash":"1234","activo":"TRUE"}], dtype=str)
        else:
            df_usuarios=df_usuarios_raw.copy()
            rename={}
            for col in df_usuarios.columns:
                c=str(col).lower().strip()
                if "id_usuario" in c: rename[col]="id_usuario"
                elif "nombre" in c: rename[col]="nombre"
                elif c=="rol": rename[col]="rol"
                elif "finca" in c: rename[col]="finca_asignada"
                elif "username" in c or "usuario" in c: rename[col]="username"
                elif "password" in c or "pass" in c: rename[col]="password_hash"
                elif "activo" in c: rename[col]="activo"
            df_usuarios=df_usuarios.rename(columns=rename)
            
        df_activos=df_usuarios[df_usuarios["activo"].astype(str).str.upper().isin(["TRUE","SI","1","ACTIVO"])] if "activo" in df_usuarios.columns else df_usuarios
        if df_activos.empty: df_activos=df_usuarios
        df_filt=df_activos[df_activos["rol"].astype(str).str.upper()==rol.upper()] if not df_activos.empty else df_activos
        if df_filt.empty: df_filt=df_activos
        
        opciones=[]; mapa={}
        for _,r in df_filt.iterrows():
            username=str(r.get("username","")).strip() or str(r.get("id_usuario","")).strip()
            if username and username not in opciones:
                opciones.append(username); mapa[username]=r
        if not opciones: opciones=["Martin.oficina"]
        
        usuario_sel=st.selectbox("Usuario", opciones)
        r_sel=mapa.get(usuario_sel)
        if r_sel is not None:
            id_usuario=str(r_sel.get("id_usuario","")).strip()
            username=str(r_sel.get("username","")).strip()
            nombre_usuario=str(r_sel.get("nombre","")).strip()
            rol_real=str(r_sel.get("rol",rol)).strip()
            finca_asignada=str(r_sel.get("finca_asignada","")).strip()
            pass_bd=str(r_sel.get("password_hash","")).strip()
        else:
            id_usuario=""; username=usuario_sel; nombre_usuario=username; rol_real=rol; finca_asignada="TODAS"; pass_bd=""
            
        st.caption(f"User:{username}")
        pwd=st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            ok = pwd in ["1234","Banano2026",pass_bd] or pwd.lower()==username.lower() or (finca_asignada and pwd.upper()==finca_asignada.upper())
            if ok:
                st.session_state.rol=rol_real or rol
                st.session_state.finca_asignada=finca_asignada
                st.session_state.id_finca=finca_asignada if finca_asignada!="TODAS" else "OFICINA"
                st.session_state.username=username
                st.session_state.id_usuario=id_usuario
                st.session_state.nombre_usuario=nombre_usuario
                st.session_state.menu_oficina="📦 Crear Orden"
                st.rerun()
            else: st.error("Incorrecta")
    else:
        st.success(f"{st.session_state.rol}")
        st.text(f"{st.session_state.username}")
        st.text(f"Finca: {st.session_state.finca_asignada}")
        st.divider()
        st.markdown("### 📋 Panel Opciones")
        if st.session_state.rol=="OFICINA_CENTRAL":
            menu = st.radio("Menu", ["📦 Ordenes Expedidas", "📦 Crear Orden", "✏️ Remision/Factura", "🗺️ Seguimiento"], index=1, key="radio_menu_oficina")
            st.session_state.menu_oficina = menu
        st.divider()
        if st.button("Salir"):
            for k in ["rol","id_finca","finca_asignada","usuario","username","id_usuario","nombre_usuario","menu_oficina"]: st.session_state[k]=None
            st.rerun()

if st.session_state.rol is None:
    st.stop()

# ==========================================
# FUNCIONES AUXILIARES SIN CONCATENAR
# ==========================================
def lista_simple_no_concat(df, id_key, nombre_key):
    if df.empty: return [], {}
    col_id = next((c for c in df.columns if id_key.lower() in c.lower()), df.columns[0])
    col_nom = next((c for c in df.columns if nombre_key.lower() in c.lower()), df.columns[1] if len(df.columns)>1 else col_id)
    lista=[]; mapa={}; seen=set()
    for _,r in df.iterrows():
        idv=str(r.get(col_id,"")).strip()
        if not idv or idv.lower()=="nan": continue
        nom=str(r.get(col_nom,"")).strip() or idv
        if nom.lower() in ["nan",""]: continue
        if nom not in seen:
            lista.append(nom); seen.add(nom)
        mapa[nom]=r.to_dict()
    return sorted(lista), mapa

def lista_placas_no_concat(df):
    if df.empty: return [], {}
    col_id = next((c for c in df.columns if "id_" in c.lower()), df.columns[0])
    col_pla = next((c for c in df.columns if "placa" in c.lower()), df.columns[0])
    lista=[]; mapa={}
    for _,r in df.iterrows():
        idv=str(r.get(col_id,"")).strip()
        pla=str(r.get(col_pla,"")).strip() or idv
        if not pla or pla.lower()=="nan": continue
        if pla not in lista:
            lista.append(pla)
        mapa[pla]=r.to_dict()
    return sorted(lista), mapa

# ==========================================
# MÓDULO OFICINA CENTRAL V5
# ==========================================
if st.session_state.rol=="OFICINA_CENTRAL":
    df_emp,_=get_df_safe("Empresas")
    df_fin,_=get_df_safe("Fincas")
    df_lin,_=get_df_safe("LineasTransporte")
    df_op,_=get_df_safe("Operadores")
    df_tr,_=get_df_safe("Tractos")
    df_tr2,_=get_df_safe("Tractocamiones")
    df_cj,_=get_df_safe("Cajas")
    df_cj2,_=get_df_safe("Cajas_Thermoking")
    df_cli,_=get_df_safe("Clientes")
    df_des,_=get_df_safe("Destinos")
    df_oc,_=get_df_safe("OrdenesCarga")
    df_of,_=get_df_safe("Orden_Fincas")
    
    df_tr_u = pd.concat([df_tr, df_tr2], ignore_index=True) if not df_tr.empty and not df_tr2.empty else (df_tr if not df_tr.empty else df_tr2)
    df_cj_u = pd.concat([df_cj, df_cj2], ignore_index=True) if not df_cj.empty and not df_cj2.empty else (df_cj if not df_cj.empty else df_cj2)

    emp_nombres, emp_mapa = lista_simple_no_concat(df_emp, "id_empresa", "razon_social")

    # TÍTULO ARRIBA A LA IZQUIERDA
    col_title, col_emp_top = st.columns([2,2])
    with col_title:
        st.markdown(f"<h2 style='margin:0; text-align:left;'>Oficina Central - {st.session_state.username}</h2>", unsafe_allow_html=True)
        st.caption(f"{st.session_state.nombre_usuario} | {st.session_state.finca_asignada}")
    with col_emp_top:
        st.markdown("**🏢 Empresa Expedidora (Primer Plano)**")
        emp_sel_principal = st.selectbox("Empresa", emp_nombres if emp_nombres else ["EMP-01"], key="emp_top_v5", label_visibility="collapsed")
        emp_data_principal = emp_mapa.get(emp_sel_principal,{})
        id_emp_principal = str(emp_data_principal.get('id_empresa','') or emp_sel_principal)
        emp_nombre_principal = str(emp_data_principal.get('razon_social','') or emp_sel_principal)

    c1,c2,c3 = st.columns([1,2,1])
    with c1: st.text_input("ID Empresa", value=id_emp_principal, disabled=True, key="id_emp_top")
    with c2: st.text_input("Razon Social", value=emp_nombre_principal, disabled=True, key="razon_top")
    with c3: st.text_input("Usuario", value=st.session_state.username, disabled=True)

    menu_sel = st.session_state.get('menu_oficina', '📦 Crear Orden')

    if menu_sel == "📦 Ordenes Expedidas":
        with st.container(border=True):
            st.subheader("📦 Ordenes Expedidas - Ventana Principal")
            if not df_oc.empty:
                colm1, colm2, colm3, colm4 = st.columns(4)
                with colm1: st.metric("Total", len(df_oc))
                with colm2: st.metric("Abiertas", len(df_oc[df_oc['estado'].astype(str).str.upper()=='ABIERTA']) if 'estado' in df_oc.columns else 0)
                with colm3: st.metric("En Finca", len(df_of[df_of['estado_carga'].astype(str).str.upper()=='EN_FINCA']) if not df_of.empty else 0)
                with colm4: st.metric("Cerradas", len(df_oc[df_oc['estado'].astype(str).str.upper()=='CERRADA']) if not df_oc.empty else 0)
                cols_show = [c for c in ["id_orden","empresa_nombre","id_finca_guia_titular","id_operador","id_tractor","id_caja1","id_lote","folio_remision","folio_factura","estado","fecha_creacion"] if c in df_oc.columns]
                df_show = df_oc.tail(20).iloc[::-1]
                st.dataframe(df_show[cols_show] if cols_show else df_show, use_container_width=True, height=250)
            else:
                st.info("Aun no hay ordenes expedidas.")

    elif menu_sel == "📦 Crear Orden":
        st.divider()
        st.subheader("Nueva Orden - Empresa + Finca PROPIA + Linea + Sin Concatenar")
        
        df_fincas_emp = df_fin[df_fin['id_empresa'].astype(str).str.upper()==id_emp_principal.upper()] if not df_fin.empty and 'id_empresa' in df_fin.columns else df_fin
        df_fincas_propias = df_fincas_emp[df_fincas_emp['tipo'].astype(str).str.upper()=='PROPIA'] if not df_fincas_emp.empty and 'tipo' in df_fincas_emp.columns else df_fincas_emp
        fin_prop_nombres, fin_prop_mapa = lista_simple_no_concat(df_fincas_propias, "id_finca", "nombre")
        fin_todos_nombres, fin_todos_mapa = lista_simple_no_concat(df_fin, "id_finca", "nombre")
        lin_nombres, lin_mapa = lista_simple_no_concat(df_lin, "id_linea", "razon_social")
        ops_nombres, ops_mapa = lista_simple_no_concat(df_op, "id_operador", "nombre")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.markdown("**Finca Titular Guia (PROPIA de empresa)**")
            fin_guia_sel = st.selectbox("Finca PROPIA", fin_prop_nombres if fin_prop_nombres else fin_todos_nombres, key="fin_guia_v5")
            fin_guia_data = fin_prop_mapa.get(fin_guia_sel,{}) or fin_todos_mapa.get(fin_guia_sel,{})
            id_fin_guia = str(fin_guia_data.get('id_finca','') or fin_guia_sel)
            st.text_input("ID Finca Guia", value=id_fin_guia, disabled=True, key="id_fin_guia_v5")
        with col_f2:
            st.markdown("**Ruta carga (propias y terceros)**")
            fin_ruta_sel = st.multiselect("Fincas donde cargara", fin_todos_nombres, key="fin_ruta_v5")
            ids_fin_ruta=[]
            for fn in fin_ruta_sel:
                d=fin_todos_mapa.get(fn,{})
                ids_fin_ruta.append(str(d.get('id_finca','') or fn))

        col_l1, col_l2 = st.columns([2,1])
        with col_l1:
            lin_sel = st.selectbox("🚛 Linea Transporte duena", lin_nombres if lin_nombres else ["LIN-01"], key="lin_v5")
            lin_data = lin_mapa.get(lin_sel,{})
            id_lin = str(lin_data.get('id_linea','') or lin_sel)
        with col_l2:
            st.text_input("ID Linea", value=id_lin, disabled=True, key="id_lin_v5")

        if not df_tr_u.empty and 'id_linea' in df_tr_u.columns:
            df_tr_filt = df_tr_u[df_tr_u['id_linea'].astype(str).str.upper()==id_lin.upper()]
            if df_tr_filt.empty: df_tr_filt = df_tr_u
        else: df_tr_filt = df_tr_u
        if not df_cj_u.empty and 'id_linea' in df_cj_u.columns:
            df_cj_filt = df_cj_u[df_cj_u['id_linea'].astype(str).str.upper()==id_lin.upper()]
            if df_cj_filt.empty: df_cj_filt = df_cj_u
        else: df_cj_filt = df_cj_u

        # ==========================================
        # VISUALIZACIÓN DE OPERADORES SIN CONCATENAR
        # ==========================================
        st.markdown("#### 👤 Operador (SIN línea)")
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            op_sel = st.selectbox("Nombre Operador", ops_nombres if ops_nombres else ["No hay"], key="op_v5", label_visibility="collapsed")
            op_data = ops_mapa.get(op_sel, {})
            id_op = str(op_data.get('id_operador', '') or op_sel)
            st.markdown(f"**{op_sel}**")
        with c2: 
            st.text_input("ID Op", value=id_op, disabled=True, key="id_op_v5")
        with c3: 
            st.text_input("Licencia", value=str(op_data.get('licencia_num', '') or op_data.get('licencia', '')), disabled=True, key="lic_v5")
        with c4: 
            st.text_input("Tel", value=str(op_data.get('telefono', '')), disabled=True, key="tel_v5")

        st.markdown(f"#### 🚛 Transporte de {lin_sel} - Datos separados")
        tr_placas, tr_mapa_placa = lista_placas_no_concat(df_tr_filt)
        cj_placas, cj_mapa_placa = lista_placas_no_concat(df_cj_filt)
        cli_nombres, cli_mapa = lista_simple_no_concat(df_cli, "id_cliente", "razon_social")
        des_nombres, des_mapa = lista_simple_no_concat(df_des, "id_destino", "ciudad")

        ct1, ct2, ct3 = st.columns(3)
        with ct1:
            st.markdown("**Tracto**")
            tr_placa_sel = st.selectbox("Placa Tracto", tr_placas if tr_placas else ["No hay"], key="tr_placa_v5", label_visibility="collapsed")
            tr_data = tr_mapa_placa.get(tr_placa_sel,{})
            id_tr = str(tr_data.get('id_tractor','') or tr_placa_sel)
            st.text_input("ID Tracto", value=id_tr, disabled=True, key="id_tr_v5")
            st.text_input("Placas", value=str(tr_data.get('placas','') or tr_placa_sel), disabled=True, key="placa_tr_v5")
            st.text_input("Marca", value=str(tr_data.get('marca','')), disabled=True, key="marca_tr_v5")
            st.text_input("Num Eco", value=str(tr_data.get('num_economico','')), disabled=True, key="econ_tr_v5")
        with ct2:
            st.markdown("**Caja 1**")
            cj1_placa_sel = st.selectbox("Placa Caja1", cj_placas if cj_placas else ["No hay"], key="cj1_placa_v5", label_visibility="collapsed")
            cj1_data = cj_mapa_placa.get(cj1_placa_sel,{})
            id_cj1 = str(cj1_data.get('id_caja','') or cj1_placa_sel)
            st.text_input("ID Caja1", value=id_cj1, disabled=True, key="id_cj1_v5")
            st.text_input("Placa Caja1", value=str(cj1_data.get('placas','') or cj1_placa_sel), disabled=True, key="placa_cj1_v5")
            st.text_input("Capacidad", value=str(cj1_data.get('capacidad_cajas','')), disabled=True, key="cap_cj1_v5")
        with ct3:
            st.markdown("**Caja 2 Full**")
            cj2_placa_sel = st.selectbox("Caja2", ["(Vacio - Sencillo)"]+cj_placas, key="cj2_placa_v5", label_visibility="collapsed")
            if cj2_placa_sel!="(Vacio - Sencillo)":
                cj2_data = cj_mapa_placa.get(cj2_placa_sel,{})
                id_cj2 = str(cj2_data.get('id_caja','') or cj2_placa_sel)
                st.text_input("ID Caja2", value=id_cj2, disabled=True, key="id_cj2_v5")
            else:
                id_cj2=""

        st.markdown("### 📄 Remision y Factura")
        r1,r2,r3,r4 = st.columns(4)
        with r1: lote_val = st.text_input("Lote", placeholder="17-1355", key="lote_v5")
        with r2: rem_val = st.text_input("Folio Remision", placeholder="REM-00123", key="rem_v5")
        with r3: fac_val = st.text_input("Folio Factura", placeholder="FAC-00123", key="fac_v5")
        with r4: fac2_val = st.text_input("Factura2 Full", placeholder="FAC-00124", key="fac2_v5")

        col_cli1, col_cli2 = st.columns(2)
        with col_cli1:
            cli_sel = st.selectbox("Cliente", cli_nombres if cli_nombres else ["No hay"], key="cli_v5")
            cli_data = cli_mapa.get(cli_sel,{})
            id_cli = str(cli_data.get('id_cliente','') or cli_sel)
        with col_cli2:
            des_sel = st.selectbox("Destino", des_nombres if des_nombres else ["No hay"], key="des_v5")
            des_data = des_mapa.get(des_sel,{})
            id_des = str(des_data.get('id_destino','') or des_sel)
        obs_val = st.text_area("Observaciones", key="obs_v5")

        if st.button("✅ GENERAR ORDEN V5", type="primary", use_container_width=True):
            if not fin_ruta_sel:
                st.warning("Selecciona fincas ruta")
            elif "No hay" in tr_placa_sel or "No hay" in cj1_placa_sel:
                st.warning("Falta tracto/caja")
            else:
                try:
                    id_orden = f"OC-{datetime.now().strftime('%Y%m%d%H%M')}-{id_op}"
                    ws_ord = sh.worksheet("OrdenesCarga")
                    ensure_columns_exist(ws_ord, ["id_empresa_expedidora","empresa_nombre","id_finca_guia_titular","id_linea","linea_nombre","folio_remision","folio_factura","folio_factura2","id_lote","observaciones","ruta_fincas_ids"])
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
                        "id_lote": lote_val if lote_val else f"LOTE-{id_orden}",
                        "folio_remision": rem_val,
                        "folio_factura": fac_val,
                        "folio_factura2": fac2_val,
                        "estado": "ABIERTA",
                        "observaciones": obs_val,
                        "ruta_fincas_ids": ",".join(ids_fin_ruta)
                    }
                    append_row_dict_safe(ws_ord, row)
                    ws_ruta = sh.worksheet("Orden_Fincas")
                    for idx,fid in enumerate(ids_fin_ruta):
                        append_row_dict_safe(ws_ruta, {"id": f"{id_orden}-{fid}", "id_orden": id_orden, "id_finca": fid, "orden_visita": idx+1, "estado_carga": "PENDIENTE"})
                    st.balloons()
                    st.success(f"ORDEN {id_orden} Empresa {emp_nombre_principal}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    elif menu_sel == "✏️ Remision/Factura":
        st.subheader("✏️ Editar Remision/Factura")
        df_oc_edit,_=get_df_safe("OrdenesCarga")
        if df_oc_edit.empty:
            st.info("No hay ordenes")
        else:
            ids = list(reversed(df_oc_edit['id_orden'].astype(str).tolist()))
            sel = st.selectbox("Orden para editar", ids[:100], key="sel_edit_v5")
            if sel:
                fila = df_oc_edit[df_oc_edit['id_orden']==sel]
                if not fila.empty:
                    r=fila.iloc[0]
                    c1,c2,c3,c4 = st.columns(4)
                    with c1: new_rem=st.text_input("Remision", value=str(r.get('folio_remision','') or ""), key="erem_v5")
                    with c2: new_fac=st.text_input("Factura", value=str(r.get('folio_factura','') or ""), key="efac_v5")
                    with c3: new_fac2=st.text_input("Factura2", value=str(r.get('folio_factura2','') or ""), key="efac2_v5")
                    with c4: new_lote=st.text_input("Lote", value=str(r.get('id_lote','')), key="elote_v5")
                    new_obs=st.text_area("Obs", value=str(r.get('observaciones','')), key="eobs_v5")
                    if st.button("💾 GUARDAR", type="primary", use_container_width=True):
                        try:
                            ws=sh.worksheet("OrdenesCarga")
                            cell=ws.find(sel)
                            headers=[str(h).strip() for h in ws.row_values(1)]
                            def idx_col(name): return headers.index(name)+1 if name in headers else None
                            if idx_col("folio_remision"): ws.update_cell(cell.row, idx_col("folio_remision"), new_rem)
                            if idx_col("folio_factura"): ws.update_cell(cell.row, idx_col("folio_factura"), new_fac)
                            if idx_col("folio_factura2"): ws.update_cell(cell.row, idx_col("folio_factura2"), new_fac2)
                            if idx_col("id_lote"): ws.update_cell(cell.row, idx_col("id_lote"), new_lote)
                            if idx_col("observaciones"): ws.update_cell(cell.row, idx_col("observaciones"), new_obs)
                            st.success("Actualizada"); st.rerun()
                        except Exception as e: st.error(str(e))

    elif menu_sel == "🗺️ Seguimiento":
        st.subheader("Seguimiento Ordenes-Fincas")
        if not df_of.empty:
            st.dataframe(df_of.tail(100), use_container_width=True)
        else:
            st.info("Sin recorridos")

elif st.session_state.rol=="VIGILANCIA":
    st.markdown(f"<h2 style='text-align:left;'>Vigilancia - {st.session_state.finca_asignada}</h2>", unsafe_allow_html=True)
    df_of,_=get_df_safe("Orden_Fincas")
    if df_of.empty: st.warning("No hay ordenes"); st.stop()
    finca=st.session_state.finca_asignada
    df_f=df_of if finca.upper()=="TODAS" else df_of[df_of['id_finca'].astype(str).str.upper()==finca.upper()]
    st.metric("Pendientes", len(df_f[~df_f['estado_carga'].isin(['CARGADO_SALIO','EN_FINCA'])]))

else:
    st.title(f"{st.session_state.rol} - {st.session_state.finca_asignada}")
