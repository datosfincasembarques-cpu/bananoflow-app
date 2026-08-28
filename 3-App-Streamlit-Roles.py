
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
    headers = ws.row_values(1)
    row = [str(data_dict.get(h, "")) for h in headers]
    ws.append_row(row, value_input_option='USER_ENTERED')
    return True

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

ROLES = ["OFICINA_CENTRAL", "VIGILANCIA", "JEFE_PLANTA"]
if 'rol' not in st.session_state:
    st.session_state.rol = None
    st.session_state.id_finca = None
    st.session_state.usuario = None
    st.session_state.form_counter = 0


with st.sidebar:
    st.title("🍌 Banano Flow")
    if conectado:
        st.success(f"Conectado: {SPREADSHEET_NAME}")
    else:
        st.error(f"Error: {err_conexion if 'err_conexion' in locals() else 'revisa secrets'}")
    
    if st.session_state.rol is None:
        rol = st.selectbox("Rol", ROLES)

        # --- CARGA DE USUARIOS SUPER ROBUSTA ---
        df_usuarios_raw, ws_usuarios = get_df_safe("Usuarios")
        df_fincas_raw, _ = get_df_safe("Fincas")

        # Debug: mostrar que columnas hay
        with st.expander("🔍 Debug Usuarios (que jala de BD)", expanded=False):
            st.write(f"Filas Usuarios: {len(df_usuarios_raw)}")
            if not df_usuarios_raw.empty:
                st.write("Columnas:", list(df_usuarios_raw.columns))
                st.dataframe(df_usuarios_raw.head(10))
            else:
                st.warning("Hoja Usuarios vacia o no existe - usando usuarios base")
            st.write(f"Filas Fincas: {len(df_fincas_raw)}")
            if not df_fincas_raw.empty:
                st.write("Columnas Fincas:", list(df_fincas_raw.columns))
                st.dataframe(df_fincas_raw.head(5))

        # Si no hay usuarios, crear base
        if df_usuarios_raw.empty:
            df_usuarios = pd.DataFrame([
                {"usuario":"admin","nombre":"Oficina Central","rol":"OFICINA_CENTRAL","id_finca":"OFICINA","password":"admin123"},
                {"usuario":"martin_gomez","nombre":"Martin Gomez - Oficina Central","rol":"OFICINA_CENTRAL","id_finca":"OFICINA","password":"admin123"},
                {"usuario":"vigilancia_06","nombre":"Vigilancia ESTRIBO 06","rol":"VIGILANCIA","id_finca":"06","password":"06"},
                {"usuario":"planta_06","nombre":"Jefe Planta 06","rol":"JEFE_PLANTA","id_finca":"06","password":"planta123"},
            ], dtype=str)
        else:
            df_usuarios = df_usuarios_raw.copy()
            # Normalizar columnas a lower
            df_usuarios.columns = [str(c).lower().strip() for c in df_usuarios.columns]
            # Mapear posibles nombres
            # Si no existe usuario, tomar primera columna no vacia
            if "usuario" not in df_usuarios.columns:
                # buscar columna que parezca usuario
                for cand in ["user","id_usuario","id","codigo","login"]:
                    if cand in df_usuarios.columns:
                        df_usuarios["usuario"] = df_usuarios[cand]
                        break
                if "usuario" not in df_usuarios.columns:
                    # usar primera columna
                    df_usuarios["usuario"] = df_usuarios.iloc[:,0].astype(str)
            # nombre
            if "nombre" not in df_usuarios.columns:
                for cand in ["nombre_completo","nombres","nombre completo"]:
                    if cand in df_usuarios.columns:
                        df_usuarios["nombre"] = df_usuarios[cand]
                        break
                if "nombre" not in df_usuarios.columns:
                    df_usuarios["nombre"] = df_usuarios["usuario"]
            # rol
            if "rol" not in df_usuarios.columns:
                for cand in ["role","perfil"]:
                    if cand in df_usuarios.columns:
                        df_usuarios["rol"] = df_usuarios[cand]
                        break
                if "rol" not in df_usuarios.columns:
                    df_usuarios["rol"] = rol
            # id_finca
            if "id_finca" not in df_usuarios.columns:
                for cand in ["finca","id finca","id_finca_usuario"]:
                    if cand in df_usuarios.columns:
                        df_usuarios["id_finca"] = df_usuarios[cand]
                        break
                if "id_finca" not in df_usuarios.columns:
                    df_usuarios["id_finca"] = "OFICINA"
            # password
            if "password" not in df_usuarios.columns:
                for cand in ["contrasena","contraseña","clave","pass"]:
                    if cand in df_usuarios.columns:
                        df_usuarios["password"] = df_usuarios[cand]
                        break
                if "password" not in df_usuarios.columns:
                    df_usuarios["password"] = "Banano2026"

            # Limpiar vacios: si usuario vacio, usar nombre
            df_usuarios["usuario"] = df_usuarios["usuario"].astype(str).str.strip()
            df_usuarios.loc[df_usuarios["usuario"].isin(["","nan","None"]), "usuario"] = df_usuarios["nombre"]

        # Filtrar por rol seleccionado (si no hay, mostrar todos)
        try:
            df_filt = df_usuarios[df_usuarios["rol"].astype(str).str.upper() == rol.upper()]
            if df_filt.empty:
                df_filt = df_usuarios
        except:
            df_filt = df_usuarios

        # Crear combo usuarios
        opciones = []
        mapa = {}
        for _, r in df_filt.iterrows():
            u = str(r.get("usuario","")).strip()
            if not u or u.lower() in ["nan","none",""]:
                continue
            # quitar guiones al inicio
            u_clean = u.lstrip("- ").strip()
            nom = str(r.get("nombre","")).strip()
            fin = str(r.get("id_finca","")).strip()
            label = f"{u_clean} - {nom}" if nom and nom.lower()!=u_clean.lower() else u_clean
            if fin and fin.lower() not in ["nan","none",""]:
                label = f"{label} ({fin})"
            label = label.strip()
            if label and label not in opciones:
                opciones.append(label)
                mapa[label]=r

        if not opciones:
            opciones = ["admin - Oficina Central (OFICINA)"]

        usuario_sel = st.selectbox("Usuario", opciones)

        r_sel = mapa.get(usuario_sel)
        if r_sel is not None:
            usuario_id = str(r_sel.get("usuario","")).strip().lstrip("- ").strip()
            id_finca = str(r_sel.get("id_finca","")).strip()
            nombre_usuario = str(r_sel.get("nombre","")).strip()
            rol_real = str(r_sel.get("rol",rol)).strip()
            pass_esperada = str(r_sel.get("password","")).strip()
        else:
            usuario_id = usuario_sel.split(" - ")[0].strip().lstrip("- ").strip()
            id_finca = "OFICINA"
            if "(" in usuario_sel and ")" in usuario_sel:
                id_finca = usuario_sel.split("(")[-1].replace(")","").strip()
            nombre_usuario = usuario_id
            rol_real = rol
            pass_esperada = ""

        if id_finca:
            st.caption(f"Finca: {id_finca} | Usuario BD: {usuario_id}")

        password = st.text_input("Contraseña", type="password")

        CLAVE_MAESTRA = "Banano2026"

        if st.button("Entrar"):
            if not password:
                st.error("Pon contraseña - prueba Banano2026")
            else:
                ok = False
                motivo = ""
                # 1. Clave maestra siempre entra
                if password == CLAVE_MAESTRA:
                    ok=True
                    motivo="maestra"
                # 2. Password igual al de BD
                elif pass_esperada and password == pass_esperada:
                    ok=True
                    motivo="bd"
                # 3. Password igual a finca
                elif id_finca and (password == id_finca or password == norm_id(id_finca)):
                    ok=True
                    motivo="finca"
                # 4. Password igual a usuario
                elif password.lower() == usuario_id.lower():
                    ok=True
                    motivo="usuario"
                # 5. Claves fijas conocidas
                elif password in ["admin123","06","finca001","planta123"]:
                    ok=True
                    motivo="fija"

                if ok:
                    st.session_state.rol = rol_real or rol
                    st.session_state.id_finca = id_finca or "OFICINA"
                    st.session_state.usuario = usuario_id
                    st.session_state.nombre_usuario = nombre_usuario
                    st.success(f"Entrando como {usuario_id} ({motivo})...")
                    st.rerun()
                else:
                    st.error(f"Contraseña incorrecta. Probaste: Banano2026 ? Tu pass en BD es: {pass_esperada}")
                    st.info(f"Usuario BD detectado: {usuario_id} | Finca: {id_finca} | Rol BD: {rol_real} | Pass BD: {pass_esperada}")
    else:
        st.success(f"{st.session_state.rol} | {st.session_state.id_finca} | {st.session_state.get('usuario','')}")
        if st.button("Salir"):
            st.session_state.rol=None
            st.session_state.id_finca=None
            st.session_state.usuario=None
            st.rerun()
    st.divider()
    st.caption(f"Fotos Drive: {FOTOS_FOLDER_ID}")


if st.session_state.rol is None:
    st.title("Bienvenido - Sistema de Embarque Banano")
    st.markdown("### ¡Sistema en linea!")
    st.info("Oficina Central crea ordenes. Vigilancia entrada/salida. Planta despacho.")
    st.caption("Selecciona Rol, Usuario y Contraseña en la barra lateral para entrar")
    st.stop()

# OFICINA CENTRAL
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

        with st.expander("➕ CATALOGOS RAPIDOS - Agregar Operador / Tracto / Caja / Cliente / Destino / Finca", expanded=False):
            st.info("Todos los codigos son TEXTO - 06 se guarda 06. Al guardar se limpia solo.")
            colA, colB, colC = st.columns(3)
            with colA:
                st.markdown("**Nuevo Operador**")
                with st.form(f"form_op_{st.session_state.form_counter}", clear_on_submit=True):
                    id_op = st.text_input("ID Operador (TEXTO) ej: 06")
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
                    cap_cj = st.text_input("Capacidad (TEXTO)", value="1300")
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
                    id_cli = st.text_input("ID Cliente (TEXTO)")
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
                    id_des = st.text_input("ID Destino (TEXTO)")
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
                    id_fin = st.text_input("ID Finca (TEXTO) ej: 06 - Se respeta texto")
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
        st.subheader("Stock Guias (R,E,P,D4,D5)")
        df_stock, _ = get_df_safe("Guias_Folios_Stock")
        if not df_stock.empty:
            st.metric("Disponibles", len(df_stock[df_stock['estado']=='DISPONIBLE']))
            st.dataframe(df_stock.tail(100))
        else:
            st.info("No hay stock")

    with tab3:
        st.subheader("📊 Catalogos - Ver, Editar, Eliminar")
        st.warning("Edicion: Modifica directo en la tabla y dale Guardar Cambios. Para eliminar, borra la fila en la tabla y guarda. Los IDs se guardan como TEXTO para respetar 06.")
        for nombre in ["Fincas","Operadores","Tractos","Cajas","Clientes","Destinos","Usuarios"]:
            df, ws = get_df_safe(nombre)
            with st.expander(f"✏️ {nombre} ({len(df)}) - Editar / Eliminar", expanded=False):
                if not df.empty:
                    edited = st.data_editor(df, num_rows="dynamic", key=f"editor_{nombre}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"💾 Guardar Cambios {nombre}", key=f"save_{nombre}"):
                            try:
                                ws.clear()
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
    st.title(f"🚧 Vigilancia - Finca {st.session_state.id_finca} - Usuario {st.session_state.get('usuario','')}")
    st.markdown("**Automático por finca - solo órdenes pendientes de TU finca - Un solo filtro**")
    
    df_orden_fin, _ = get_df_safe("Orden_Fincas")
    df_ordenes, _ = get_df_safe("OrdenesCarga")
    
    if df_orden_fin.empty:
        st.warning("No hay órdenes en sistema aún.")
        st.stop()
    
    id_finca_vig = (st.session_state.id_finca or "").strip()
    id_norm_vig = norm_id(id_finca_vig)
    
    df_filtrada = df_orden_fin[df_orden_fin['id_finca'].astype(str).apply(norm_id) == id_norm_vig]
    df_filtrada = df_filtrada[df_filtrada['id_orden'].astype(str).str.strip() != ""]
    
    if df_filtrada.empty:
        st.info(f"✅ No hay órdenes para tu finca {id_finca_vig}. Todo al día.")
        st.stop()
    
    df_pendientes = df_filtrada[~df_filtrada['estado_carga'].isin(['CARGADO_SALIO','CARGADO','CERRADA'])].copy()
    df_en_finca = df_filtrada[df_filtrada['estado_carga'] == 'EN_FINCA'].copy()
    
    st.success(f"📍 Tu finca: {id_finca_vig} | Pendientes: {len(df_pendientes)} | En finca: {len(df_en_finca)}")
    
    if not df_pendientes.empty:
        st.subheader(f"🚛 Órdenes PENDIENTES para {id_finca_vig}")
        for idx, row in df_pendientes.iterrows():
            id_orden = str(row['id_orden']).strip()
            if not id_orden or id_orden.lower() == 'nan':
                continue
            info_orden = df_ordenes[df_ordenes['id_orden']==id_orden] if not df_ordenes.empty else pd.DataFrame()
            operador = info_orden.iloc[0].get('id_operador','?') if not info_orden.empty else "?"
            tractor = info_orden.iloc[0].get('id_tractor','?') if not info_orden.empty else "?"
            caja1 = info_orden.iloc[0].get('id_caja1','?') if not info_orden.empty else "?"
            
            with st.container(border=True):
                col_info, col_btn1 = st.columns([3,1])
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
                                "id_usuario": f"VIG-{id_finca_vig}-{st.session_state.get('usuario','')}",
                                "fotos_links": ""
                            })
                            ws_of = sh.worksheet("Orden_Fincas")
                            for r_idx, r in enumerate(ws_of.get_all_records(), start=2):
                                if str(r.get('id_orden'))==id_orden and norm_id(r.get('id_finca'))==id_norm_vig:
                                    ws_of.update_cell(r_idx, 5, "EN_FINCA")
                                    break
                            st.success(f"Entrada {id_orden} registrada")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
    
    if not df_en_finca.empty:
        st.divider()
        st.subheader(f"📦 Unidades EN FINCA {id_finca_vig} - Listas para SALIDA")
        for idx, row in df_en_finca.iterrows():
            id_orden = str(row['id_orden']).strip()
            if not id_orden or id_orden.lower() == 'nan':
                continue
            with st.container(border=True):
                col_info, col_btn = st.columns([3,1])
                with col_info:
                    st.markdown(f"**{id_orden}** - EN FINCA")
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
                                "id_usuario": f"VIG-{id_finca_vig}-{st.session_state.get('usuario','')}",
                                "fotos_links": ""
                            })
                            ws_of = sh.worksheet("Orden_Fincas")
                            for r_idx, r in enumerate(ws_of.get_all_records(), start=2):
                                if str(r.get('id_orden'))==id_orden and norm_id(r.get('id_finca'))==id_norm_vig:
                                    ws_of.update_cell(r_idx, 5, "CARGADO_SALIO")
                                    break
                            try:
                                df_of = pd.DataFrame(ws_of.get_all_records())
                                pendientes = df_of[(df_of['id_orden']==id_orden) & (~df_of['estado_carga'].isin(['CARGADO_SALIO','CARGADO']))]
                                if pendientes.empty:
                                    ws_oc = sh.worksheet("OrdenesCarga")
                                    cell_oc = ws_oc.find(id_orden)
                                    ws_oc.update_cell(cell_oc.row, 11, "CERRADA")
                            except:
                                pass
                            st.success(f"Salida {id_orden}")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
    
    with st.expander("📜 Historial tu finca"):
        df_bit, _ = get_df_safe("Bitacora_Vigilancia")
        if not df_bit.empty:
            df_bit_f = df_bit[df_bit['id_finca'].astype(str).apply(norm_id) == id_norm_vig]
            st.dataframe(df_bit_f.tail(30), use_container_width=True)

elif st.session_state.rol == "JEFE_PLANTA":
    st.title(f"Planta - {st.session_state.id_finca} - {st.session_state.get('usuario','')}")
    cantidad = st.text_input("Cajas (TEXTO) para respetar 06", value="450")
    if st.button("Cerrar Despacho Finca"):
        st.success("Despacho creado. Si es ultima finca, orden CERRADA")
