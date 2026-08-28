
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
    st.title("🍌 Banano Flow")
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
    st.title("Bienvenido - Sistema de Embarque Banano")
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
    
    tab1, tab2, tab3 = st.tabs(["📦 Crear Orden Carga (POR NOMBRES)", "📄 Guias Stock", "📊 Catalogos + Ultimas Ordenes"])

    with tab1:
        st.subheader("Nueva Orden de Carga - BUSCA POR NOMBRE, no por codigo")
        st.info("🔍 Escribe parte del nombre y selecciona. El sistema guarda el codigo automaticamente. No necesitas memorizar codigos.")
        
        df_op, _ = get_df_safe("Operadores")
        df_tr, _ = get_df_safe("Tractos")
        df_cj, _ = get_df_safe("Cajas")
        df_cli, _ = get_df_safe("Clientes")
        df_des, _ = get_df_safe("Destinos")
        df_fin, _ = get_df_safe("Fincas")

        def crear_opciones_nombres(df, col_id_name, col_nombre_names, col_extra_names=[]):
            if df.empty:
                return [], {}, {}
            # encontrar col id
            col_id_real = None
            for c in df.columns:
                if col_id_name.lower() in c.lower():
                    col_id_real = c
                    break
            if not col_id_real:
                col_id_real = df.columns[0]
            
            def find_col(cands):
                for cand in cands:
                    for col in df.columns:
                        if cand.lower() in col.lower():
                            return col
                return None
            
            col_nom = find_col(col_nombre_names)
            if not col_nom:
                col_nom = df.columns[1] if len(df.columns)>1 else col_id_real
            col_extra = find_col(col_extra_names) if col_extra_names else None
            
            opciones = []
            mapa_id = {}
            mapa_label = {}
            for _, r in df.iterrows():
                id_val = str(r.get(col_id_real,"")).strip()
                if not id_val or id_val.lower()=="nan":
                    continue
                nom = str(r.get(col_nom,"")).strip() if col_nom else id_val
                if not nom or nom.lower()=="nan":
                    nom = id_val
                extra = str(r.get(col_extra,"")).strip() if col_extra else ""
                # Label: Nombre (ID) - extra
                if extra and extra.lower()!="nan" and extra!="":
                    label = f"{nom} ({id_val}) - {extra}"
                else:
                    label = f"{nom} ({id_val})"
                if label not in opciones:
                    opciones.append(label)
                    mapa_id[label]=id_val
                    mapa_label[label]=label
            return opciones, mapa_id, mapa_label

        ops_labels, ops_map, _ = crear_opciones_nombres(df_op, "id_operador", ["nombre","operador","chofer"], ["licencia"])
        trs_labels, trs_map, _ = crear_opciones_nombres(df_tr, "id_tractor", ["placa","marca","economico"], ["marca"])
        cjs_labels, cjs_map, _ = crear_opciones_nombres(df_cj, "id_caja", ["placa","tipo","capacidad"], ["tipo"])
        cli_labels, cli_map, _ = crear_opciones_nombres(df_cli, "id_cliente", ["nombre","cliente"], ["rfc"])
        des_labels, des_map, _ = crear_opciones_nombres(df_des, "id_destino", ["nombre","destino","ciudad"], ["pais"])
        fin_labels, fin_map, _ = crear_opciones_nombres(df_fin, "id_finca", ["nombre","finca"], ["tipo"])

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🚚 Transporte")
            operador_label = st.selectbox("🔍 Operador - Busca por NOMBRE", ops_labels if ops_labels else ["No hay operadores"], key="op_sel")
            operador = ops_map.get(operador_label, "")
            if operador:
                st.caption(f"✓ Codigo guardado: {operador}")

            tractor_label = st.selectbox("🔍 Tracto - Busca por PLACA", trs_labels if trs_labels else ["No hay tractos"], key="tr_sel")
            tractor = trs_map.get(tractor_label, "")
            if tractor:
                st.caption(f"✓ Codigo guardado: {tractor}")

            caja1_label = st.selectbox("🔍 Caja 1 - Busca por PLACA", cjs_labels if cjs_labels else ["No hay cajas"], key="cj1_sel")
            caja1 = cjs_map.get(caja1_label, "")
            if caja1:
                st.caption(f"✓ Codigo guardado: {caja1}")

            caja2_label = st.selectbox("Caja 2 (Full opcional)", ["(Vacio - Sencillo)"] + cjs_labels, key="cj2_sel")
            caja2 = cjs_map.get(caja2_label, "") if caja2_label != "(Vacio - Sencillo)" else ""

        with col2:
            st.markdown("#### 🗺️ Ruta y Cliente")
            fincas_labels_sel = st.multiselect("🔍 Fincas - Busca por NOMBRE (orden de visita)", fin_labels if fin_labels else [], help="Escribe: Esperanza, San Jorge, Estribo...", key="fin_sel")
            fincas = [fin_map.get(l,"") for l in fincas_labels_sel]
            if fincas_labels_sel:
                st.caption(f"✓ Codigos: {', '.join(fincas)}")

            cliente_label = st.selectbox("🔍 Cliente - Busca por NOMBRE", cli_labels if cli_labels else ["No hay clientes"], key="cli_sel")
            cliente = cli_map.get(cliente_label, "")
            if cliente:
                st.caption(f"✓ Codigo: {cliente}")

            destino_label = st.selectbox("🔍 Destino - Busca por CIUDAD", des_labels if des_labels else ["No hay destinos"], key="des_sel")
            destino = des_map.get(destino_label, "")
            if destino:
                st.caption(f"✓ Codigo: {destino}")

            lote_override = st.text_input("Lote (opcional) Ej: 17-1355", value="", key="lote_input", help="Si lo dejas vacio, se genera automatico LOTE-OC-...")

        st.divider()
        if fincas_labels_sel:
            with st.container(border=True):
                st.markdown("**📋 Resumen de tu orden (lo que se guardara):**")
                st.write(f"**Operador:** {operador_label} → Codigo: `{operador}`")
                st.write(f"**Tracto:** {tractor_label} → Codigo: `{tractor}`")
                st.write(f"**Caja 1:** {caja1_label} → Codigo: `{caja1}`")
                if caja2:
                    st.write(f"**Caja 2:** {caja2_label} → Codigo: `{caja2}`")
                st.write(f"**Cliente:** {cliente_label} → Codigo: `{cliente}`")
                st.write(f"**Destino:** {destino_label} → Codigo: `{destino}`")
                st.write(f"**Fincas ({len(fincas)}):**")
                for fl in fincas_labels_sel:
                    st.write(f"  • {fl}")

        if st.button("✅ GENERAR ORDEN + LOTE + RUTA - DAME FOLIO", type="primary", use_container_width=True):
            if not fincas:
                st.warning("⚠️ Selecciona al menos una finca")
            elif not operador or not tractor or not caja1:
                st.warning("⚠️ Selecciona Operador, Tracto y Caja 1")
            else:
                try:
                    id_orden = f"OC-{datetime.now().strftime('%Y%m%d%H%M')}-{operador}"
                    folio_lote = lote_override if lote_override else f"LOTE-{id_orden}"
                    ws_ord = sh.worksheet("OrdenesCarga")
                    row = {
                        "id_orden": id_orden,
                        "folio_orden": id_orden,
                        "fecha_creacion": datetime.now().isoformat(),
                        "id_usuario_crea": st.session_state.username,
                        "id_operador": operador,
                        "id_tractor": tractor,
                        "id_caja1": caja1,
                        "id_caja2": caja2,
                        "id_cliente": cliente,
                        "id_destino": destino,
                        "id_lote": folio_lote,
                        "estado": "ABIERTA",
                        "ruta_fincas_ids": ",".join(fincas)
                    }
                    append_row_dict_safe(ws_ord, row)
                    ws_ruta = sh.worksheet("Orden_Fincas")
                    for idx, finca_id in enumerate(fincas):
                        d = {"id": f"{id_orden}-{finca_id}", "id_orden": id_orden, "id_finca": finca_id, "orden_visita": idx+1, "estado_carga": "PENDIENTE"}
                        append_row_dict_safe(ws_ruta, d)
                    
                    # Guardar en session para mostrar folio grande
                    st.session_state.ultima_orden = {
                        "id_orden": id_orden,
                        "folio": id_orden,
                        "lote": folio_lote,
                        "ruta": ", ".join(fincas),
                        "ruta_labels": ", ".join(fincas_labels_sel),
                        "operador_label": operador_label,
                        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
                    }
                    
                    st.balloons()
                    st.success(f"✅ ¡ORDEN GENERADA EXITOSAMENTE!")
                    st.success(f"📄 FOLIO ORDEN: {id_orden}")
                    st.success(f"📦 LOTE: {folio_lote}")
                    st.info(f"Ruta: {', '.join(fincas_labels_sel)}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al generar: {e}")
                    st.error("Verifica que existan las hojas OrdenesCarga y Orden_Fincas en tu Google Sheets")

        # Mostrar ultimas 5 ordenes generadas
        st.divider()
        st.subheader("📜 Ultimas 5 Ordenes Generadas")
        df_ordenes, _ = get_df_safe("OrdenesCarga")
        if not df_ordenes.empty:
            # ordenar por fecha descendente
            df_last = df_ordenes.tail(5).iloc[::-1]
            for _, r in df_last.iterrows():
                with st.container(border=True):
                    st.markdown(f"**FOLIO: {r.get('id_orden','')}** - Lote: {r.get('id_lote','')} - Estado: {r.get('estado','')}")
                    st.caption(f"Fecha: {r.get('fecha_creacion','')} | Operador: {r.get('id_operador','')} | Ruta: {r.get('ruta_fincas_ids','')}")
        else:
            st.info("Aun no hay ordenes")




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
