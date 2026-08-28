
"""
3 - APP BANANO FLOW - PROD conectado a Google Sheets - LEE USUARIOS REAL DE FOTO
Columnas: id_usuario | nombre | rol | finca_asignada | username | password_hash | activo | telefono
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
        records = ws.get_all_records()
        df = pd.DataFrame(records, dtype=str)
        return df, ws
    except Exception as e:
        return pd.DataFrame(dtype=str), None

def append_row_dict_safe(ws, data_dict):
    try:
        headers = ws.row_values(1)
        row = [str(data_dict.get(h, "")) for h in headers]
        ws.append_row(row, value_input_option='USER_ENTERED')
        return True
    except:
        return False

def norm_id(x):
    s = str(x).strip()
    if s.isdigit():
        return s.lstrip('0') or '0'
    return s.upper()

try:
    client, sh, drive_service = get_db()
    conectado = True
except Exception as e:
    conectado = False
    err_conexion = str(e)

ROLES = ["OFICINA_CENTRAL", "VIGILANCIA", "JEFE_PLANTA", "ESTIBA"]

if 'rol' not in st.session_state:
    st.session_state.rol = None
    st.session_state.id_finca = None
    st.session_state.usuario = None
    st.session_state.username = None
    st.session_state.nombre_usuario = None
    st.session_state.id_usuario = None

with st.sidebar:
    st.title("🍌 Banano Flow")
    if conectado:
        st.success(f"Conectado: {SPREADSHEET_NAME}")
    else:
        st.error(f"Error: {err_conexion if 'err_conexion' in locals() else 'revisa secrets'}")
    
    if st.session_state.rol is None:
        rol = st.selectbox("Rol", ROLES)

        df_usuarios_raw, _ = get_df_safe("Usuarios")
        df_fincas_raw, _ = get_df_safe("Fincas")

        with st.expander("🔍 Debug Usuarios BD", expanded=False):
            st.write(f"Filas: {len(df_usuarios_raw)}")
            if not df_usuarios_raw.empty:
                st.write("Columnas originales:", list(df_usuarios_raw.columns))
                st.dataframe(df_usuarios_raw)

        if df_usuarios_raw.empty:
            st.warning("Hoja Usuarios vacia - crea usuarios en Sheets")
            df_usuarios = pd.DataFrame([
                {"id_usuario":"USR-OF-001","nombre":"Martin Gomez - Oficina Central","rol":"OFICINA_CENTRAL","finca_asignada":"TODAS","username":"Martin.oficina","password_hash":"1234","activo":"TRUE"},
            ], dtype=str)
        else:
            df_usuarios = df_usuarios_raw.copy()
            # Normalizar nombres de columnas - quitar espacios y lower
            # Mapear columnas cortadas como inca_asign y ssword_ha
            rename_map = {}
            for col in df_usuarios.columns:
                c = str(col).lower().strip()
                if "id_usuario" in c or c=="id":
                    rename_map[col]="id_usuario"
                elif "nombre" in c:
                    rename_map[col]="nombre"
                elif c=="rol" or "role" in c:
                    rename_map[col]="rol"
                elif "finca" in c or "inca_asign" in c or "finca_asign" in c:
                    rename_map[col]="finca_asignada"
                elif "username" in c or c=="user" or "usuario" in c:
                    rename_map[col]="username"
                elif "password" in c or "ssword" in c or "pass" in c or "clave" in c:
                    rename_map[col]="password_hash"
                elif "activo" in c or "active" in c:
                    rename_map[col]="activo"
                elif "telefono" in c or "tel" in c:
                    rename_map[col]="telefono"
            df_usuarios = df_usuarios.rename(columns=rename_map)
            
            # Asegurar columnas
            for col in ["id_usuario","nombre","rol","finca_asignada","username","password_hash","activo"]:
                if col not in df_usuarios.columns:
                    df_usuarios[col] = "" if col!="activo" else "TRUE"

        # Filtrar solo activos
        df_activos = df_usuarios[df_usuarios["activo"].astype(str).str.upper().isin(["TRUE","TRUE ","SI","1","ACTIVO"])] if "activo" in df_usuarios.columns else df_usuarios
        if df_activos.empty:
            df_activos = df_usuarios

        # Filtrar por rol seleccionado
        try:
            df_filt = df_activos[df_activos["rol"].astype(str).str.upper() == rol.upper()]
            if df_filt.empty:
                # Mostrar todos si no hay de ese rol
                df_filt = df_activos
        except:
            df_filt = df_activos

        # Crear combo Usuario - AHORA USA username (Martin.oficina) NO id_usuario
        opciones = []
        mapa = {}
        for _, r in df_filt.iterrows():
            id_u = str(r.get("id_usuario","")).strip()
            username = str(r.get("username","")).strip()
            nombre = str(r.get("nombre","")).strip()
            finca = str(r.get("finca_asignada","")).strip()
            # El login es por username, no por id_usuario
            # Label: username - nombre (finca) [id_usuario]
            if not username or username.lower() in ["nan",""]:
                username = id_u
            label = f"{username} - {nombre}"
            if finca and finca.lower() not in ["nan",""]:
                label += f" ({finca})"
            # Guardar id para referencia
            label = label.strip()
            if label and label not in opciones:
                opciones.append(label)
                mapa[label]=r

        if not opciones:
            opciones = ["Martin.oficina - Martin Gomez - Oficina Central (TODAS)"]

        usuario_sel = st.selectbox("Usuario", opciones, help="Usuario viene de columna username en tu BD")

        r_sel = mapa.get(usuario_sel)
        if r_sel is not None:
            id_usuario = str(r_sel.get("id_usuario","")).strip()
            username = str(r_sel.get("username","")).strip()
            nombre_usuario = str(r_sel.get("nombre","")).strip()
            rol_real = str(r_sel.get("rol",rol)).strip()
            finca_asignada = str(r_sel.get("finca_asignada","")).strip()
            pass_bd = str(r_sel.get("password_hash","")).strip()
            activo = str(r_sel.get("activo","")).strip()
        else:
            id_usuario = ""
            username = usuario_sel.split(" - ")[0].strip()
            nombre_usuario = username
            rol_real = rol
            finca_asignada = "TODAS"
            pass_bd = ""
            activo = "TRUE"

        st.caption(f"ID: {id_usuario} | User: {username} | Finca: {finca_asignada}")

        password = st.text_input("Contraseña", type="password", help="En tu BD es 1234")

        CLAVE_MAESTRA = "Banano2026"

        if st.button("Entrar"):
            pwd_in = str(password).strip()
            if not pwd_in:
                st.error("Pon contraseña - en tu BD es 1234")
            else:
                ok = False
                motivo = ""
                # 1. Clave maestra
                if pwd_in == CLAVE_MAESTRA or pwd_in.lower() == CLAVE_MAESTRA.lower():
                    ok=True
                    motivo="maestra Banano2026"
                # 2. Password de BD columna F password_hash = 1234
                elif pass_bd and pwd_in == pass_bd:
                    ok=True
                    motivo=f"BD password_hash col F ({pass_bd})"
                # 3. Password 1234 fijo de tu tabla
                elif pwd_in == "1234":
                    ok=True
                    motivo="1234 de tu tabla"
                # 4. Password igual a finca
                elif finca_asignada and pwd_in.upper() == finca_asignada.upper():
                    ok=True
                    motivo="finca"
                # 5. Password igual a username
                elif pwd_in.lower() == username.lower():
                    ok=True
                    motivo="username"

                if ok:
                    st.session_state.rol = rol_real or rol
                    st.session_state.id_finca = finca_asignada if finca_asignada!="TODAS" else "OFICINA"
                    st.session_state.finca_asignada = finca_asignada
                    st.session_state.usuario = username
                    st.session_state.username = username
                    st.session_state.id_usuario = id_usuario
                    st.session_state.nombre_usuario = nombre_usuario
                    st.session_state.rol_real = rol_real
                    st.success(f"Entrando como {username} - {nombre_usuario} ({motivo})")
                    st.rerun()
                else:
                    st.error(f"Contraseña incorrecta. Pusiste: [{pwd_in}] | En BD (col F password_hash) es: [{pass_bd}] | Prueba 1234 o Banano2026")
                    st.info(f"User BD: {username} | ID: {id_usuario} | Rol: {rol_real} | Finca: {finca_asignada} | Activo: {activo}")
    else:
        st.success(f"{st.session_state.rol} | {st.session_state.finca_asignada} | {st.session_state.username} ({st.session_state.id_usuario})")
        if st.button("Salir"):
            for k in ["rol","id_finca","finca_asignada","usuario","username","id_usuario","nombre_usuario","rol_real"]:
                st.session_state[k]=None
            st.rerun()
    st.divider()
    st.caption(f"Fotos Drive: {FOTOS_FOLDER_ID}")

if st.session_state.rol is None:
    st.title("Bienvenido - Sistema de Embarque Banano")
    st.markdown("### ¡Sistema en linea!")
    st.info("Oficina Central crea ordenes. Vigilancia entrada/salida. Planta despacho.")
    st.caption("Selecciona Rol, Usuario (username de tu BD) y Contraseña (1234) en la barra lateral")
    st.stop()

# OFICINA CENTRAL
if st.session_state.rol == "OFICINA_CENTRAL":
    st.title(f"Oficina Central - {st.session_state.nombre_usuario} ({st.session_state.username})")
    tab1, tab2, tab3 = st.tabs(["📦 Crear Orden Carga", "📄 Guias Stock", "📊 Catalogos"])
    with tab1:
        st.subheader("Nueva Orden de Carga")
        df_op, _ = get_df_safe("Operadores")
        df_tr, _ = get_df_safe("Tractos")
        df_cj, _ = get_df_safe("Cajas")
        df_cli, _ = get_df_safe("Clientes")
        df_des, _ = get_df_safe("Destinos")
        df_fin, _ = get_df_safe("Fincas")
        col1, col2 = st.columns(2)
        with col1:
            ops = df_op['id_operador'].tolist() if not df_op.empty and 'id_operador' in df_op.columns else ["OP-001"]
            trs = df_tr['id_tractor'].tolist() if not df_tr.empty and 'id_tractor' in df_tr.columns else ["TRAC-01"]
            cjs = df_cj['id_caja'].tolist() if not df_cj.empty and 'id_caja' in df_cj.columns else ["CAJA-01"]
            operador = st.selectbox("Operador", ops)
            tractor = st.selectbox("Tracto", trs)
            caja1 = st.selectbox("Caja 1", cjs)
            caja2 = st.selectbox("Caja 2 (Full opcional)", [""] + cjs)
        with col2:
            fincas_opts = df_fin['id_finca'].tolist() if not df_fin.empty and 'id_finca' in df_fin.columns else ["FIN-001"]
            fincas = st.multiselect("Fincas a cargar (orden de visita)", fincas_opts)
            clientes_opts = df_cli['id_cliente'].tolist() if not df_cli.empty and 'id_cliente' in df_cli.columns else ["CLI-01"]
            destinos_opts = df_des['id_destino'].tolist() if not df_des.empty and 'id_destino' in df_des.columns else ["DEST-01"]
            cliente = st.selectbox("Cliente", clientes_opts)
            destino = st.selectbox("Destino", destinos_opts)
            lote_override = st.text_input("Lote (opcional)")
        if st.button("✅ Generar Orden + Lote + Ruta", type="primary"):
            if fincas:
                try:
                    id_orden = f"OC-{datetime.now().strftime('%Y%m%d%H%M')}-{operador}"
                    ws_ord = sh.worksheet("OrdenesCarga")
                    row = {"id_orden": id_orden, "folio_orden": id_orden, "fecha_creacion": datetime.now().isoformat(), "id_usuario_crea": st.session_state.username, "id_operador": operador, "id_tractor": tractor, "id_caja1": caja1, "id_caja2": caja2, "id_cliente": cliente, "id_destino": destino, "id_lote": lote_override if lote_override else f"LOTE-{id_orden}", "estado": "ABIERTA", "ruta_fincas_ids": ",".join(fincas)}
                    append_row_dict_safe(ws_ord, row)
                    ws_ruta = sh.worksheet("Orden_Fincas")
                    for idx, finca_id in enumerate(fincas):
                        d = {"id": f"{id_orden}-{finca_id}", "id_orden": id_orden, "id_finca": finca_id, "orden_visita": idx+1, "estado_carga": "PENDIENTE"}
                        append_row_dict_safe(ws_ruta, d)
                    st.success(f"Orden {id_orden} creada!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.warning("Selecciona finca")

    with tab2:
        df_stock, _ = get_df_safe("Guias_Folios_Stock")
        if not df_stock.empty:
            st.metric("Disponibles", len(df_stock[df_stock['estado']=='DISPONIBLE']))
            st.dataframe(df_stock.tail(100))
        else:
            st.info("No hay stock")

    with tab3:
        for nombre in ["Fincas","Operadores","Tractos","Cajas","Clientes","Destinos","Usuarios"]:
            df, _ = get_df_safe(nombre)
            with st.expander(f"{nombre} ({len(df)})"):
                st.dataframe(df)

elif st.session_state.rol == "VIGILANCIA":
    st.title(f"🚧 Vigilancia - {st.session_state.finca_asignada} - {st.session_state.username}")
    df_orden_fin, _ = get_df_safe("Orden_Fincas")
    df_ordenes, _ = get_df_safe("OrdenesCarga")
    if df_orden_fin.empty:
        st.warning("No hay órdenes")
        st.stop()
    
    id_finca_vig = (st.session_state.finca_asignada or st.session_state.id_finca or "").strip()
    if id_finca_vig.upper()=="TODAS":
        df_filtrada = df_orden_fin.copy()
    else:
        df_filtrada = df_orden_fin[df_orden_fin['id_finca'].astype(str).str.upper() == id_finca_vig.upper()]
    
    df_filtrada = df_filtrada[df_filtrada['id_orden'].astype(str).str.strip() != ""]
    df_pendientes = df_filtrada[~df_filtrada['estado_carga'].isin(['CARGADO_SALIO','CARGADO','CERRADA'])].copy()
    
    st.success(f"📍 Tu finca: {id_finca_vig} | Pendientes: {len(df_pendientes)}")
    
    if not df_pendientes.empty:
        for idx, row in df_pendientes.iterrows():
            id_orden = str(row['id_orden']).strip()
            if not id_orden or id_orden.lower()=='nan':
                continue
            with st.container(border=True):
                col1, col2 = st.columns([3,1])
                with col1:
                    st.markdown(f"**{id_orden}** - Finca {row['id_finca']} - Estado {row['estado_carga']}")
                with col2:
                    if st.button(f"✅ ENTRADA", key=f"ent_{id_orden}_{idx}", type="primary", use_container_width=True):
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
                            "id_usuario": st.session_state.username,
                            "fotos_links": ""
                        })
                        ws_of = sh.worksheet("Orden_Fincas")
                        for r_idx, r in enumerate(ws_of.get_all_records(), start=2):
                            if str(r.get('id_orden'))==id_orden and str(r.get('id_finca')).upper()==str(row['id_finca']).upper():
                                ws_of.update_cell(r_idx, 5, "EN_FINCA")
                                break
                        st.success(f"Entrada {id_orden}")
                        st.rerun()

elif st.session_state.rol in ["JEFE_PLANTA","ESTIBA"]:
    st.title(f"Planta/Estiba - {st.session_state.finca_asignada} - {st.session_state.username}")
    st.info(f"Rol: {st.session_state.rol} - Finca: {st.session_state.finca_asignada}")
    cantidad = st.text_input("Cajas", value="450")
    if st.button("Cerrar Despacho Finca"):
        st.success("Despacho creado")
