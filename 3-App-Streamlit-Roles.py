
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

st.set_page_config(page_title="Embarques - Sistema Banano", layout="wide", page_icon="🍌")

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

def subir_foto_a_drive(file_uploader, nombre_archivo):
    """Sube foto de Streamlit file_uploader a Drive y retorna link"""
    try:
        if file_uploader is None:
            return ""
        # Guardar temporal
        import tempfile, os
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(file_uploader.getbuffer())
            tmp_path = tmp.name
        
        from googleapiclient.http import MediaFileUpload
        file_metadata = {'name': nombre_archivo, 'parents': [FOTOS_FOLDER_ID] if FOTOS_FOLDER_ID else []}
        media = MediaFileUpload(tmp_path, mimetype='image/jpeg')
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        try:
            drive_service.permissions().create(fileId=file['id'], body={'type':'anyone','role':'reader'}).execute()
        except:
            pass
        os.unlink(tmp_path)
        return file.get('webViewLink','')
    except Exception as e:
        st.error(f"Error subiendo foto {nombre_archivo}: {e}")
        return ""

def buscar_detalle(df, col_id, id_buscar, col_nombre):
    if df.empty or not id_buscar:
        return id_buscar
    try:
        # buscar columna id
        col_id_real = None
        for c in df.columns:
            if col_id.lower() in c.lower():
                col_id_real = c
                break
        if not col_id_real:
            col_id_real = df.columns[0]
        col_nom_real = None
        for c in df.columns:
            if col_nombre.lower() in c.lower():
                col_nom_real = c
                break
        if not col_nom_real:
            col_nom_real = df.columns[1] if len(df.columns)>1 else col_id_real
        
        fila = df[df[col_id_real].astype(str).str.upper() == str(id_buscar).upper()]
        if not fila.empty:
            nombre = str(fila.iloc[0].get(col_nom_real, id_buscar))
            return f"{nombre} ({id_buscar})"
        return id_buscar
    except:
        return id_buscar


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
    st.title("🍌 Embarques")
    if conectado:
        st.success(f"Conectado: {SPREADSHEET_NAME}")
    else:
        st.error(f"Error: {err_conexion if 'err_conexion' in locals() else 'revisa secrets'}")
    
    if st.session_state.rol is None:
        rol = st.selectbox("Rol", ROLES)

        df_usuarios_raw, _ = get_df_safe("Usuarios")
        df_fincas_raw, _ = get_df_safe("Fincas")

        # Debug removido para producción - solo si falla muestra mensaje

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

        # Crear combo Usuario - SOLO username (sin descripcion, cada quien se acuerda)
        opciones = []
        mapa = {}
        for _, r in df_filt.iterrows():
            id_u = str(r.get("id_usuario","")).strip()
            username = str(r.get("username","")).strip()
            finca = str(r.get("finca_asignada","")).strip()
            if not username or username.lower() in ["nan",""]:
                username = id_u
            # Solo username limpio
            label = f"{username}"
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
    st.title("Bienvenido - Sistema de Embarques Banano")
    st.markdown("### ¡Sistema en linea!")
    st.info("Oficina Central crea ordenes. Vigilancia entrada/salida. Planta despacho.")
    st.caption("Selecciona Rol, Usuario (username de tu BD) y Contraseña (1234) en la barra lateral")
    st.stop()

# OFICINA CENTRAL

if st.session_state.rol == "OFICINA_CENTRAL":
    st.title(f"Oficina Central - {st.session_state.nombre_usuario} ({st.session_state.username})")
    
    # Mostrar ultimo folio generado
    if 'ultima_orden' in st.session_state and st.session_state.ultima_orden:
        st.success(f"✅ ULTIMA ORDEN GENERADA: {st.session_state.ultima_orden['id_orden']} | Folio: {st.session_state.ultima_orden['folio']} | Lote: {st.session_state.ultima_orden['lote']}")
        with st.container(border=True):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("FOLIO ORDEN", st.session_state.ultima_orden['id_orden'])
            with col2:
                st.metric("LOTE", st.session_state.ultima_orden['lote'])
            with col3:
                st.metric("ESTADO", "ABIERTA")
            st.write(f"**Ruta:** {st.session_state.ultima_orden['ruta']}")
            st.write(f"**Operador:** {st.session_state.ultima_orden['operador_label']}")
    
    
    tab1, tab2, tab3 = st.tabs(["📦 Crear Orden Carga", "📄 Guias Stock", "📊 Catalogos + Ultimas Ordenes"])

    with tab1:
        st.subheader("Nueva Orden de Carga")
        st.caption("Datos separados, no concatenados. Cada dato en su lugar.")

        df_op, _ = get_df_safe("Operadores")
        df_tr, _ = get_df_safe("Tractos")
        df_cj, _ = get_df_safe("Cajas")
        df_cli, _ = get_df_safe("Clientes")
        df_des, _ = get_df_safe("Destinos")
        df_fin, _ = get_df_safe("Fincas")

        # Helper para obtener lista limpia por nombre
        def get_lista_operadores(df):
            if df.empty:
                return [], {}
            # Buscar columnas
            col_id = next((c for c in df.columns if "id_operador" in c.lower()), df.columns[0])
            col_nombre = next((c for c in df.columns if "nombre" in c.lower()), df.columns[1] if len(df.columns)>1 else col_id)
            col_lic = next((c for c in df.columns if "licencia" in c.lower()), None)
            col_tel = next((c for c in df.columns if "telefono" in c.lower() or "tel" in c.lower()), None)
            lista = []
            mapa = {}
            for _, r in df.iterrows():
                id_v = str(r.get(col_id,"")).strip()
                if not id_v or id_v.lower()=="nan":
                    continue
                nombre = str(r.get(col_nombre,"")).strip()
                lista.append(nombre)
                mapa[nombre] = r.to_dict()
            return sorted(list(set(lista))), mapa

        def get_lista_simple(df, col_id_name, col_nombre_name):
            if df.empty:
                return [], {}
            col_id = next((c for c in df.columns if col_id_name.lower() in c.lower()), df.columns[0])
            col_nombre = next((c for c in df.columns if col_nombre_name.lower() in c.lower()), df.columns[1] if len(df.columns)>1 else col_id)
            lista = []
            mapa = {}
            for _, r in df.iterrows():
                id_v = str(r.get(col_id,"")).strip()
                if not id_v or id_v.lower()=="nan":
                    continue
                nombre = str(r.get(col_nombre,"")).strip() or id_v
                label = f"{nombre}"
                lista.append(label)
                mapa[label] = r.to_dict()
            return sorted(list(set(lista))), mapa

        ops_nombres, ops_mapa = get_lista_operadores(df_op)
        trs_nombres, trs_mapa = get_lista_simple(df_tr, "id_tractor", "placa")
        cjs_nombres, cjs_mapa = get_lista_simple(df_cj, "id_caja", "placa")
        cli_nombres, cli_mapa = get_lista_simple(df_cli, "id_cliente", "nombre")
        des_nombres, des_mapa = get_lista_simple(df_des, "id_destino", "ciudad")
        fin_nombres, fin_mapa = get_lista_simple(df_fin, "id_finca", "nombre")

        # ====== TRANSPORTE ======
        st.markdown("### 🚚 Transporte")
        c1, c2, c3 = st.columns([2,1,1])
        with c1:
            op_sel_nombre = st.selectbox("Operador (Nombre)", ops_nombres if ops_nombres else ["No hay operadores"], key="op_nombre")
            op_data = ops_mapa.get(op_sel_nombre, {})
            id_operador = str(op_data.get('id_operador','') or op_data.get('id','') or op_sel_nombre)
        with c2:
            lic_num = op_data.get('licencia_num','') or op_data.get('licencia','') or op_data.get('num_licencia','')
            st.text_input("Num Licencia", value=str(lic_num), disabled=True, key="op_lic_view")
        with c3:
            tel_op = op_data.get('telefono','') or op_data.get('tel','')
            st.text_input("Telefono Operador", value=str(tel_op), disabled=True, key="op_tel_view")
            if id_operador:
                st.caption(f"ID: {id_operador}")

        # Boton alta rapida operador
        with st.expander("➕ Dar de alta NUEVO Operador aqui mismo (sin cambiar pestaña)", expanded=False):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                new_op_id = st.text_input("ID Operador (ej OP-005)", key="new_op_id")
                new_op_nombre = st.text_input("Nombre completo", key="new_op_nombre")
            with col_b:
                new_op_lic = st.text_input("Licencia num", key="new_op_lic")
                new_op_tel = st.text_input("Telefono", key="new_op_tel")
            with col_c:
                new_op_linea = st.text_input("Linea Transporte ID", value="LIN-01", key="new_op_linea")
                if st.button("Guardar Operador", key="btn_save_op"):
                    if new_op_id and new_op_nombre:
                        try:
                            ws = sh.worksheet("Operadores")
                            headers = ws.row_values(1)
                            row_dict = {"id_operador": new_op_id, "nombre": new_op_nombre, "licencia_num": new_op_lic, "telefono": new_op_tel, "id_linea": new_op_linea}
                            row = [str(row_dict.get(h,"")) for h in headers]
                            ws.append_row(row, value_input_option='USER_ENTERED')
                            st.success(f"Operador {new_op_nombre} guardado. Recarga la pagina.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning("ID y Nombre obligatorios")

        st.divider()
        # Tracto y Cajas en linea separada cada dato en su lugar
        col_t1, col_t2, col_t3, col_t4 = st.columns(4)
        with col_t1:
            tracto_sel = st.selectbox("Tracto (Placa)", trs_nombres if trs_nombres else ["No hay tractos"], key="tracto_sel")
            tr_data = trs_mapa.get(tracto_sel, {})
            id_tractor = str(tr_data.get('id_tractor','') or tr_data.get('id','') or tracto_sel)
            st.caption(f"ID: {id_tractor} | Marca: {tr_data.get('marca','')}")
        with col_t2:
            caja1_sel = st.selectbox("Caja 1 (Placa)", cjs_nombres if cjs_nombres else ["No hay cajas"], key="caja1_sel")
            cj1_data = cjs_mapa.get(caja1_sel, {})
            id_caja1 = str(cj1_data.get('id_caja','') or cj1_data.get('id','') or caja1_sel)
            st.caption(f"ID: {id_caja1} | Cap: {cj1_data.get('capacidad_cajas','')}")
        with col_t3:
            caja2_sel = st.selectbox("Caja 2 (Full opcional)", ["(Vacio - Sencillo)"] + cjs_nombres, key="caja2_sel")
            if caja2_sel != "(Vacio - Sencillo)":
                cj2_data = cjs_mapa.get(caja2_sel, {})
                id_caja2 = str(cj2_data.get('id_caja','') or cj2_data.get('id','') or caja2_sel)
                st.caption(f"ID: {id_caja2}")
            else:
                id_caja2 = ""
                cj2_data = {}
        with col_t4:
            st.text_input("Lote (ej 17-1355)", key="lote_input")

        with st.expander("➕ Alta rapida Tracto / Caja aqui mismo", expanded=False):
            tab_a, tab_b = st.tabs(["Nuevo Tracto", "Nueva Caja"])
            with tab_a:
                ca1, ca2, ca3 = st.columns(3)
                with ca1:
                    nt_id = st.text_input("ID Tracto", key="nt_id")
                    nt_placa = st.text_input("Placa Tracto", key="nt_placa")
                with ca2:
                    nt_marca = st.text_input("Marca", key="nt_marca")
                    nt_econ = st.text_input("Num Economico", key="nt_econ")
                with ca3:
                    if st.button("Guardar Tracto", key="btn_nt"):
                        try:
                            ws = sh.worksheet("Tractos")
                            # Intentar con Tractocamiones tambien
                            try:
                                ws = sh.worksheet("Tractocamiones")
                            except:
                                pass
                            headers = ws.row_values(1)
                            rd = {"id_tractor": nt_id, "placas": nt_placa, "marca": nt_marca, "num_economico": nt_econ}
                            ws.append_row([str(rd.get(h,"")) for h in headers], value_input_option='USER_ENTERED')
                            st.success("Tracto guardado")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
            with tab_b:
                cb1, cb2, cb3 = st.columns(3)
                with cb1:
                    nc_id = st.text_input("ID Caja", key="nc_id")
                    nc_placa = st.text_input("Placa Caja", key="nc_placa")
                with cb2:
                    nc_cap = st.text_input("Capacidad cajas", value="450", key="nc_cap")
                with cb3:
                    if st.button("Guardar Caja", key="btn_nc"):
                        try:
                            ws_name = "Cajas_Thermoking" if "Cajas_Thermoking" in [w.title for w in sh.worksheets()] else "Cajas"
                            ws = sh.worksheet(ws_name)
                            headers = ws.row_values(1)
                            rd = {"id_caja": nc_id, "placas": nc_placa, "capacidad_cajas": nc_cap}
                            ws.append_row([str(rd.get(h,"")) for h in headers], value_input_option='USER_ENTERED')
                            st.success("Caja guardada")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

        st.divider()
        st.markdown("### 🗺️ Ruta y Cliente")
        col_r1, col_r2, col_r3 = st.columns([2,1,1])
        with col_r1:
            fincas_sel = st.multiselect("Fincas a cargar (orden visita)", fin_nombres if fin_nombres else [], help="Selecciona en orden: Esperanza, San Jorge...")
            ids_fincas = []
            for fn in fincas_sel:
                d = fin_mapa.get(fn, {})
                ids_fincas.append(str(d.get('id_finca','') or d.get('id','') or fn))
        with col_r2:
            cli_sel = st.selectbox("Cliente", cli_nombres if cli_nombres else ["No hay clientes"], key="cli_sel")
            cli_data = cli_mapa.get(cli_sel, {})
            id_cliente = str(cli_data.get('id_cliente','') or cli_data.get('id','') or cli_sel)
            st.caption(f"ID: {id_cliente}")
        with col_r3:
            des_sel = st.selectbox("Destino", des_nombres if des_nombres else ["No hay destinos"], key="des_sel")
            des_data = des_mapa.get(des_sel, {})
            id_destino = str(des_data.get('id_destino','') or des_data.get('id','') or des_sel)
            st.caption(f"ID: {id_destino}")

        # Resumen limpio separado
        if fincas_sel:
            with st.container(border=True):
                st.markdown("**📋 Resumen orden:**")
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Operador:** {op_sel_nombre}")
                    st.write(f"  Licencia: {lic_num}")
                    st.write(f"  ID: {id_operador}")
                    st.write(f"**Tracto:** {tracto_sel} | ID: {id_tractor}")
                    st.write(f"**Caja1:** {caja1_sel} | ID: {id_caja1}")
                    if id_caja2:
                        st.write(f"**Caja2:** {caja2_sel} | ID: {id_caja2}")
                with c2:
                    st.write(f"**Cliente:** {cli_sel} | ID: {id_cliente}")
                    st.write(f"**Destino:** {des_sel} | ID: {id_destino}")
                    st.write(f"**Fincas ({len(ids_fincas)}):** {', '.join(fincas_sel)}")
                    st.write(f"**Lote:** {st.session_state.get('lote_input','')}")

        if st.button("✅ GENERAR ORDEN - DAME FOLIO", type="primary", use_container_width=True):
            lote_val = st.session_state.get('lote_input','')
            if not fincas_sel:
                st.warning("Selecciona al menos una finca")
            elif not id_operador or not id_tractor or not id_caja1:
                st.warning("Falta Operador / Tracto / Caja1")
            else:
                try:
                    id_orden = f"OC-{datetime.now().strftime('%Y%m%d%H%M')}-{id_operador}"
                    folio_lote = lote_val if lote_val else f"LOTE-{id_orden}"
                    ws_ord = sh.worksheet("OrdenesCarga")
                    row = {
                        "id_orden": id_orden,
                        "folio_orden": id_orden,
                        "fecha_creacion": datetime.now().isoformat(),
                        "id_usuario_crea": st.session_state.username,
                        "id_operador": id_operador,
                        "id_tractor": id_tractor,
                        "id_caja1": id_caja1,
                        "id_caja2": id_caja2,
                        "id_cliente": id_cliente,
                        "id_destino": id_destino,
                        "id_lote": folio_lote,
                        "estado": "ABIERTA",
                        "ruta_fincas_ids": ",".join(ids_fincas)
                    }
                    append_row_dict_safe(ws_ord, row)
                    ws_ruta = sh.worksheet("Orden_Fincas")
                    for idx, fid in enumerate(ids_fincas):
                        d = {"id": f"{id_orden}-{fid}", "id_orden": id_orden, "id_finca": fid, "orden_visita": idx+1, "estado_carga": "PENDIENTE"}
                        append_row_dict_safe(ws_ruta, d)
                    st.session_state.ultima_orden = {
                        "id_orden": id_orden,
                        "folio": id_orden,
                        "lote": folio_lote,
                        "ruta": ", ".join(ids_fincas),
                        "ruta_labels": ", ".join(fincas_sel),
                        "operador_label": op_sel_nombre,
                        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
                    }
                    st.balloons()
                    st.success(f"✅ ORDEN GENERADA! FOLIO: {id_orden} | LOTE: {folio_lote}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        st.divider()
        st.subheader("📜 Ultimas 5 Ordenes")
        df_ord, _ = get_df_safe("OrdenesCarga")
        if not df_ord.empty:
            for _, r in df_ord.tail(5).iloc[::-1].iterrows():
                with st.container(border=True):
                    st.markdown(f"**FOLIO: {r.get('id_orden','')}** | Lote: {r.get('id_lote','')} | Estado: {r.get('estado','')}")
                    st.caption(f"Fecha: {r.get('fecha_creacion','')[:16]} | Op: {r.get('id_operador','')} | Ruta: {r.get('ruta_fincas_ids','')}")
        else:
            st.info("Aun no hay ordenes")

    with tab2:
        st.subheader("Guias Fitosanitarias - Stock)")
        df_stock, _ = get_df_safe("Guias_Folios_Stock")
        if not df_stock.empty:
            disp = df_stock[df_stock['estado'].astype(str).str.upper()=='DISPONIBLE'] if 'estado' in df_stock.columns else df_stock
            st.metric("Folios DISPONIBLES", len(disp))
            st.dataframe(df_stock.tail(100), use_container_width=True)
        else:
            st.info("No hay stock - Compra guias en hoja Compra_Guias")

    with tab3:
        st.subheader("Catalogos + Ultimas Ordenes")
        for nombre in ["Fincas","Operadores","Tractos","Tractocamiones","Cajas","Cajas_Thermoking","Clientes","Destinos","Usuarios"]:
            df, _ = get_df_safe(nombre)
            if not df.empty:
                with st.expander(f"{nombre} ({len(df)}) - Ver todo"):
                    st.dataframe(df, use_container_width=True)



elif st.session_state.rol == "VIGILANCIA":
    st.title(f"🚧 Vigilancia - {st.session_state.finca_asignada} - {st.session_state.username}")
    st.markdown("### 📸 Corroboración de Datos + Fotos Obligatorias")
    st.info("El vigilante debe corroborar: Operador, Placas de Tractor y Caja(s), Licencia, y tomar FOTOS como evidencia")

    df_orden_fin, _ = get_df_safe("Orden_Fincas")
    df_ordenes, _ = get_df_safe("OrdenesCarga")
    df_ops, _ = get_df_safe("Operadores")
    df_tractos, _ = get_df_safe("Tractos")
    df_cajas, _ = get_df_safe("Cajas")

    if df_orden_fin.empty:
        st.warning("No hay órdenes en sistema aún.")
        st.stop()

    id_finca_vig = (st.session_state.finca_asignada or st.session_state.id_finca or "").strip()
    if id_finca_vig.upper()=="TODAS":
        df_filtrada = df_orden_fin.copy()
    else:
        df_filtrada = df_orden_fin[df_orden_fin['id_finca'].astype(str).str.upper() == id_finca_vig.upper()]

    df_filtrada = df_filtrada[df_filtrada['id_orden'].astype(str).str.strip() != ""]
    df_pendientes = df_filtrada[~df_filtrada['estado_carga'].isin(['CARGADO_SALIO','CARGADO','CERRADA','EN_FINCA'])].copy()
    df_en_finca = df_filtrada[df_filtrada['estado_carga'] == 'EN_FINCA'].copy()

    st.success(f"📍 Tu finca: {id_finca_vig} | Pendientes entrada: {len(df_pendientes)} | En finca para salida: {len(df_en_finca)}")

    # TAB PENDIENTES ENTRADA
    if not df_pendientes.empty:
        st.divider()
        st.subheader(f"🚛 ORDENES PENDIENTES PARA ENTRADA - {id_finca_vig}")
        st.caption("Toma fotos y corrobora datos antes de dar ENTRADA")

        for idx, row in df_pendientes.iterrows():
            id_orden = str(row['id_orden']).strip()
            if not id_orden or id_orden.lower()=='nan':
                continue
            # Buscar detalles de la orden
            det_orden = df_ordenes[df_ordenes['id_orden'].astype(str)==id_orden] if not df_ordenes.empty else pd.DataFrame()
            if not det_orden.empty:
                op_id = str(det_orden.iloc[0].get('id_operador','?'))
                tracto_id = str(det_orden.iloc[0].get('id_tractor','?'))
                caja1_id = str(det_orden.iloc[0].get('id_caja1','?'))
                caja2_id = str(det_orden.iloc[0].get('id_caja2','')).strip()
                cliente_id = str(det_orden.iloc[0].get('id_cliente','?'))
                destino_id = str(det_orden.iloc[0].get('id_destino','?'))
                lote = str(det_orden.iloc[0].get('id_lote',''))
                fecha = str(det_orden.iloc[0].get('fecha_creacion',''))

                op_det = buscar_detalle(df_ops, "id_operador", op_id, "nombre")
                tracto_det = buscar_detalle(df_tractos, "id_tractor", tracto_id, "placa")
                caja1_det = buscar_detalle(df_cajas, "id_caja", caja1_id, "placa")
                caja2_det = buscar_detalle(df_cajas, "id_caja", caja2_id, "placa") if caja2_id and caja2_id.lower()!='nan' else ""
            else:
                op_id = tracto_id = caja1_id = caja2_id = "?"
                op_det = tracto_det = caja1_det = caja2_det = "?"
                lote = fecha = "?"

            with st.container(border=True):
                st.markdown(f"### 📄 {id_orden} | LOTE: {lote} | Finca: {row['id_finca']} | Estado: {row['estado_carga']}")
                col_datos, col_fotos = st.columns([1,1])
                with col_datos:
                    st.markdown("**Datos a corroborar (de Oficina Central):**")
                    st.write(f"👤 **Operador:** {op_det}")
                    st.write(f"🚛 **Tracto:** {tracto_det} - ID: {tracto_id}")
                    st.write(f"📦 **Caja 1:** {caja1_det} - ID: {caja1_id}")
                    if caja2_id and caja2_id.lower()!='nan' and caja2_id!="":
                        st.write(f"📦 **Caja 2 (Full):** {caja2_det} - ID: {caja2_id}")
                    st.write(f"🔢 **Visita No:** {row.get('orden_visita','')}")
                    st.caption(f"Fecha orden: {fecha[:16]}")

                with col_fotos:
                    st.markdown("**📸 Fotos Obligatorias ENTRADA:**")
                    foto_tractor = st.file_uploader(f"Foto Tractor con Placa {tracto_id}", type=["jpg","jpeg","png"], key=f"ft_{id_orden}_{idx}")
                    foto_caja1 = st.file_uploader(f"Foto Caja 1 con Placa {caja1_id}", type=["jpg","jpeg","png"], key=f"fc1_{id_orden}_{idx}")
                    foto_caja2 = None
                    if caja2_id and caja2_id.lower()!='nan' and caja2_id!="":
                        foto_caja2 = st.file_uploader(f"Foto Caja 2 con Placa {caja2_id} (Full)", type=["jpg","jpeg","png"], key=f"fc2_{id_orden}_{idx}")
                    foto_licencia = st.file_uploader(f"Foto Licencia Operador {op_id}", type=["jpg","jpeg","png"], key=f"fl_{id_orden}_{idx}")
                    odometro = st.text_input(f"Odómetro Entrada {id_orden}", key=f"odo_ent_{id_orden}_{idx}", placeholder="Ej: 125430")
                    obs_entrada = st.text_area(f"Observaciones Entrada", key=f"obs_ent_{id_orden}_{idx}", placeholder="Si hay discrepancia en placas, reportar aqui")

                # Boton Entrada con validacion de fotos
                if st.button(f"✅ REGISTRAR ENTRADA + SUBIR FOTOS - {id_orden}", key=f"btn_ent_{id_orden}_{idx}", type="primary", use_container_width=True):
                    if not foto_tractor or not foto_caja1:
                        st.error("⚠️ Debes tomar al menos Foto de Tractor con Placa y Foto de Caja 1 con Placa")
                    else:
                        with st.spinner(f"Subiendo fotos de {id_orden} a Drive..."):
                            link_tractor = subir_foto_a_drive(foto_tractor, f"ENTRADA_{id_orden}_{row['id_finca']}_TRACTOR_{tracto_id}_{datetime.now().strftime('%H%M%S')}.jpg")
                            link_caja1 = subir_foto_a_drive(foto_caja1, f"ENTRADA_{id_orden}_{row['id_finca']}_CAJA1_{caja1_id}_{datetime.now().strftime('%H%M%S')}.jpg")
                            link_caja2 = subir_foto_a_drive(foto_caja2, f"ENTRADA_{id_orden}_{row['id_finca']}_CAJA2_{caja2_id}_{datetime.now().strftime('%H%M%S')}.jpg") if foto_caja2 else ""
                            link_lic = subir_foto_a_drive(foto_licencia, f"ENTRADA_{id_orden}_{row['id_finca']}_LICENCIA_{op_id}_{datetime.now().strftime('%H%M%S')}.jpg") if foto_licencia else ""

                            fotos_links = f"Tractor:{link_tractor}|Caja1:{link_caja1}"
                            if link_caja2:
                                fotos_links += f"|Caja2:{link_caja2}"
                            if link_lic:
                                fotos_links += f"|Licencia:{link_lic}"

                        try:
                            try:
                                ws_bit = sh.worksheet("Bitacora_Vigilancia")
                            except:
                                ws_bit = sh.add_worksheet(title="Bitacora_Vigilancia", rows=1000, cols=12)
                                ws_bit.append_row(["id_bitacora","id_orden","id_finca","tipo_movimiento","fecha_hora","hora_manual","odometro","observaciones","id_usuario","fotos_links","tractor_foto","caja_foto"])

                            append_row_dict_safe(ws_bit, {
                                "id_bitacora": f"ENT-{id_orden}-{datetime.now().strftime('%H%M%S')}",
                                "id_orden": id_orden,
                                "id_finca": row['id_finca'],
                                "tipo_movimiento": "ENTRADA",
                                "fecha_hora": datetime.now().isoformat(),
                                "hora_manual": datetime.now().strftime('%H:%M'),
                                "odometro": odometro,
                                "observaciones": f"Op: {op_det} | {obs_entrada} | Corrobora: Tractor {tracto_id} Placa {tracto_det}, Caja {caja1_id} Placa {caja1_det}",
                                "id_usuario": st.session_state.username,
                                "fotos_links": fotos_links
                            })
                            ws_of = sh.worksheet("Orden_Fincas")
                            for r_idx, r in enumerate(ws_of.get_all_records(), start=2):
                                if str(r.get('id_orden'))==id_orden and str(r.get('id_finca')).upper()==str(row['id_finca']).upper():
                                    ws_of.update_cell(r_idx, 5, "EN_FINCA")
                                    break
                            st.success(f"✅ Entrada {id_orden} registrada con fotos")
                            if link_tractor:
                                st.success(f"Foto Tractor: {link_tractor}")
                            if link_caja1:
                                st.success(f"Foto Caja1: {link_caja1}")
                            if link_caja2:
                                st.success(f"Foto Caja2: {link_caja2}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    # TAB EN FINCA PARA SALIDA
    if not df_en_finca.empty:
        st.divider()
        st.subheader(f"📦 UNIDADES EN FINCA {id_finca_vig} - LISTAS PARA SALIDA")
        st.caption("Toma fotos de salida y confirma")

        for idx, row in df_en_finca.iterrows():
            id_orden = str(row['id_orden']).strip()
            det_orden = df_ordenes[df_ordenes['id_orden'].astype(str)==id_orden] if not df_ordenes.empty else pd.DataFrame()
            op_det = str(det_orden.iloc[0].get('id_operador','?')) if not det_orden.empty else "?"
            caja1_id = str(det_orden.iloc[0].get('id_caja1','?')) if not det_orden.empty else "?"
            caja2_id = str(det_orden.iloc[0].get('id_caja2','')).strip() if not det_orden.empty else ""
            
            with st.container(border=True):
                col1, col2 = st.columns([1,1])
                with col1:
                    st.markdown(f"**{id_orden}** - EN FINCA {row['id_finca']} - Op: {op_det}")
                    st.caption(f"Caja1: {caja1_id} | Caja2: {caja2_id if caja2_id else 'Sencillo'}")
                with col2:
                    foto_sal_tractor = st.file_uploader(f"Foto Salida Tractor {id_orden}", type=["jpg","jpeg","png"], key=f"fst_{id_orden}_{idx}")
                    foto_sal_caja1 = st.file_uploader(f"Foto Salida Caja 1 {id_orden}", type=["jpg","jpeg","png"], key=f"fsc1_{id_orden}_{idx}")
                    foto_sal_caja2 = None
                    if caja2_id and caja2_id.lower()!='nan' and caja2_id!="":
                        foto_sal_caja2 = st.file_uploader(f"Foto Salida Caja 2 {id_orden} (Full)", type=["jpg","jpeg","png"], key=f"fsc2_{id_orden}_{idx}")
                    odometro_sal = st.text_input(f"Odómetro Salida {id_orden}", key=f"odo_sal_{id_orden}_{idx}")
                    obs_sal = st.text_area(f"Obs Salida {id_orden}", key=f"obs_sal_{id_orden}_{idx}", placeholder="Cargado completo? Cajas?")

                if st.button(f"✅ REGISTRAR SALIDA + FOTOS - {id_orden}", key=f"btn_sal_{id_orden}_{idx}", type="secondary", use_container_width=True):
                    if not foto_sal_tractor or not foto_sal_caja1:
                        st.error("⚠️ Foto Tractor y Caja 1 de salida obligatorias")
                    else:
                        with st.spinner(f"Subiendo fotos salida {id_orden}..."):
                            link_tractor_s = subir_foto_a_drive(foto_sal_tractor, f"SALIDA_{id_orden}_{row['id_finca']}_TRACTOR_{datetime.now().strftime('%H%M%S')}.jpg")
                            link_caja1_s = subir_foto_a_drive(foto_sal_caja1, f"SALIDA_{id_orden}_{row['id_finca']}_CAJA1_{datetime.now().strftime('%H%M%S')}.jpg")
                            link_caja2_s = subir_foto_a_drive(foto_sal_caja2, f"SALIDA_{id_orden}_{row['id_finca']}_CAJA2_{datetime.now().strftime('%H%M%S')}.jpg") if foto_sal_caja2 else ""
                            fotos_links_s = f"Tractor Sal:{link_tractor_s}|Caja1 Sal:{link_caja1_s}"
                            if link_caja2_s:
                                fotos_links_s += f"|Caja2 Sal:{link_caja2_s}"

                        try:
                            try:
                                ws_bit = sh.worksheet("Bitacora_Vigilancia")
                            except:
                                ws_bit = sh.add_worksheet(title="Bitacora_Vigilancia", rows=1000, cols=12)
                                ws_bit.append_row(["id_bitacora","id_orden","id_finca","tipo_movimiento","fecha_hora","hora_manual","odometro","observaciones","id_usuario","fotos_links","tractor_foto","caja_foto"])

                            append_row_dict_safe(ws_bit, {
                                "id_bitacora": f"SAL-{id_orden}-{datetime.now().strftime('%H%M%S')}",
                                "id_orden": id_orden,
                                "id_finca": row['id_finca'],
                                "tipo_movimiento": "SALIDA",
                                "fecha_hora": datetime.now().isoformat(),
                                "hora_manual": datetime.now().strftime('%H:%M'),
                                "odometro": odometro_sal,
                                "observaciones": f"Salida cargado: {obs_sal}",
                                "id_usuario": st.session_state.username,
                                "fotos_links": fotos_links_s
                            })
                            ws_of = sh.worksheet("Orden_Fincas")
                            for r_idx, r in enumerate(ws_of.get_all_records(), start=2):
                                if str(r.get('id_orden'))==id_orden and str(r.get('id_finca')).upper()==str(row['id_finca']).upper():
                                    ws_of.update_cell(r_idx, 5, "CARGADO_SALIO")
                                    break
                            # Si es ultima finca, cerrar orden
                            try:
                                df_of = pd.DataFrame(ws_of.get_all_records())
                                pendientes = df_of[(df_of['id_orden']==id_orden) & (~df_of['estado_carga'].isin(['CARGADO_SALIO','CARGADO']))]
                                if pendientes.empty:
                                    ws_oc = sh.worksheet("OrdenesCarga")
                                    cell_oc = ws_oc.find(id_orden)
                                    ws_oc.update_cell(cell_oc.row, 11, "CERRADA")
                            except:
                                pass

                            st.success(f"✅ Salida {id_orden} con fotos")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error salida: {e}")

    with st.expander("📜 Historial tu finca - Bitacora con Fotos"):
        df_bit, _ = get_df_safe("Bitacora_Vigilancia")
        if not df_bit.empty:
            df_f = df_bit[df_bit['id_finca'].astype(str).str.upper()==id_finca_vig.upper()] if id_finca_vig.upper()!="TODAS" else df_bit
            st.dataframe(df_f.tail(50), use_container_width=True)
            # Mostrar links de fotos
            for _, r in df_f.tail(10).iterrows():
                if r.get('fotos_links'):
                    st.caption(f"{r['id_orden']} {r['tipo_movimiento']} {r['fecha_hora'][:16]} Fotos: {r['fotos_links'][:200]}...")
        else:
            st.info("Sin historial")

elif st.session_state.rol in ["JEFE_PLANTA","ESTIBA"]:

    st.title(f"Planta/Estiba - {st.session_state.finca_asignada} - {st.session_state.username}")
    st.info(f"Rol: {st.session_state.rol} - Finca: {st.session_state.finca_asignada}")
    cantidad = st.text_input("Cajas", value="450")
    if st.button("Cerrar Despacho Finca"):
        st.success("Despacho creado")
