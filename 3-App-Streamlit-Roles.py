
"""
3 - APP BANANO FLOW - FIX LECTURA BD + REMISION/FACTURA
Fix robusto para Tractos/Tractocamiones y Cajas
Nueva: remision y factura editables despues
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

st.set_page_config(page_title="Embarques FIX", layout="wide", page_icon="🍌")

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
    # variantes como Operadores que si funciona
    mapa_variantes = {
        "Tractos": ["Tractos","Tractocamiones","Tractocamion","Tractores"],
        "Tractocamiones": ["Tractocamiones","Tractos","Tractocamion"],
        "Cajas": ["Cajas","Cajas_Thermoking","Cajas_Thermo"],
        "Cajas_Thermoking": ["Cajas_Thermoking","Cajas","Cajas_Thermo"],
    }
    candidatos = mapa_variantes.get(sheet_name, [sheet_name])
    for name in candidatos:
        try:
            ws = sh.worksheet(name)
            records = ws.get_all_records()
            df = pd.DataFrame(records, dtype=str)
            df.columns = [str(c).strip() for c in df.columns]
            return df, ws
        except:
            continue
    # fuzzy search
    try:
        for ws in sh.worksheets():
            tl = ws.title.lower()
            sl = sheet_name.lower()
            if "tracto" in sl and "tracto" in tl:
                try:
                    df = pd.DataFrame(ws.get_all_records(), dtype=str)
                    df.columns=[str(c).strip() for c in df.columns]
                    return df, ws
                except: pass
            if "caja" in sl and "caja" in tl:
                try:
                    df = pd.DataFrame(ws.get_all_records(), dtype=str)
                    df.columns=[str(c).strip() for c in df.columns]
                    return df, ws
                except: pass
    except:
        pass
    return pd.DataFrame(dtype=str), None

def ensure_columns_exist(ws, required_cols):
    try:
        headers = ws.row_values(1)
        headers_clean = [str(h).strip() for h in headers]
        added=False
        for col in required_cols:
            if col not in headers_clean:
                ws.update_cell(1, len(headers)+1, col)
                headers.append(col)
                added=True
        return added
    except:
        return False

def append_row_dict_safe(ws, data_dict):
    try:
        ensure_columns_exist(ws, list(data_dict.keys()))
        headers = ws.row_values(1)
        headers = [str(h).strip() for h in headers]
        row = [str(data_dict.get(h, "")) for h in headers]
        ws.append_row(row, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        st.error(f"Error guardando: {e}")
        return False

def subir_foto_a_drive(file_uploader, nombre_archivo):
    try:
        if file_uploader is None: return ""
        import tempfile, os
        from googleapiclient.http import MediaFileUpload
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(file_uploader.getbuffer())
            tmp_path = tmp.name
        file_metadata = {'name': nombre_archivo, 'parents': [FOTOS_FOLDER_ID] if FOTOS_FOLDER_ID else []}
        media = MediaFileUpload(tmp_path, mimetype='image/jpeg')
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        try:
            drive_service.permissions().create(fileId=file['id'], body={'type':'anyone','role':'reader'}).execute()
        except: pass
        os.unlink(tmp_path)
        return file.get('webViewLink','')
    except Exception as e:
        st.error(f"Error foto {e}")
        return ""

try:
    client, sh, drive_service = get_db()
    conectado=True
except Exception as e:
    conectado=False
    err_conexion=str(e)

ROLES=["OFICINA_CENTRAL","VIGILANCIA","JEFE_PLANTA","ESTIBA"]
if 'rol' not in st.session_state:
    for k in ["rol","id_finca","usuario","username","nombre_usuario","id_usuario","finca_asignada"]:
        st.session_state[k]=None

with st.sidebar:
    st.title("🍌 Embarques FIX")
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
        try:
            df_filt=df_activos[df_activos["rol"].astype(str).str.upper()==rol.upper()]
            if df_filt.empty: df_filt=df_activos
        except: df_filt=df_activos
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
        st.caption(f"ID:{id_usuario} User:{username} Finca:{finca_asignada}")
        pwd=st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            ok = pwd=="1234" or pwd=="Banano2026" or (pass_bd and pwd==pass_bd) or pwd.lower()==username.lower() or (finca_asignada and pwd.upper()==finca_asignada.upper())
            if ok:
                st.session_state.rol=rol_real or rol
                st.session_state.finca_asignada=finca_asignada
                st.session_state.id_finca=finca_asignada if finca_asignada!="TODAS" else "OFICINA"
                st.session_state.username=username
                st.session_state.id_usuario=id_usuario
                st.session_state.nombre_usuario=nombre_usuario
                st.rerun()
            else: st.error(f"Incorrecta BD:{pass_bd} prueba 1234")
    else:
        st.success(f"{st.session_state.rol} | {st.session_state.finca_asignada} | {st.session_state.username}")
        if st.button("Salir"):
            for k in ["rol","id_finca","finca_asignada","usuario","username","id_usuario","nombre_usuario"]: st.session_state[k]=None
            st.rerun()

if st.session_state.rol is None:
    st.title("Bienvenido Embarques"); st.stop()

if st.session_state.rol=="OFICINA_CENTRAL":
    st.title(f"Oficina Central - {st.session_state.username}")
    tab1, tab2, tab3, tab4 = st.tabs(["📦 Crear Orden (FIX BD)", "✏️ Remision/Factura Editar Despues", "📄 Guias", "📊 Catalogos"])
    with tab1:
        st.subheader("Nueva Orden - FIX lectura Tractos/Cajas como Operadores")
        df_op, ws_op = get_df_safe("Operadores")
        df_tr, _ = get_df_safe("Tractos")
        df_tr2, _ = get_df_safe("Tractocamiones")
        df_cj, _ = get_df_safe("Cajas")
        df_cj2, _ = get_df_safe("Cajas_Thermoking")
        df_cli,_=get_df_safe("Clientes")
        df_des,_=get_df_safe("Destinos")
        df_fin,_=get_df_safe("Fincas")

        # unir tractos y cajas
        if not df_tr.empty and not df_tr2.empty:
            df_tr_u = pd.concat([df_tr, df_tr2], ignore_index=True).drop_duplicates()
        else:
            df_tr_u = df_tr if not df_tr.empty else df_tr2
        if not df_cj.empty and not df_cj2.empty:
            df_cj_u = pd.concat([df_cj, df_cj2], ignore_index=True).drop_duplicates()
        else:
            df_cj_u = df_cj if not df_cj.empty else df_cj2

        with st.expander("DEBUG - Que encontro", expanded=True):
            st.write(f"Operadores {len(df_op)} OK ejemplo")
            st.write(f"Tractos hoja Tractos:{len(df_tr)} Tractocamiones:{len(df_tr2)} Unido:{len(df_tr_u)}")
            st.write(f"Cajas hoja Cajas:{len(df_cj)} Thermo:{len(df_cj2)} Unido:{len(df_cj_u)}")
            if not df_tr_u.empty:
                st.dataframe(df_tr_u.head(3), use_container_width=True)
            else:
                st.error("No encontro Tractos - revisa nombres hojas en Sheets, debe existir Tractos o Tractocamiones con datos")
                st.write(f"Hojas disponibles: {[w.title for w in sh.worksheets()]}")
            if not df_cj_u.empty:
                st.dataframe(df_cj_u.head(3), use_container_width=True)
            else:
                st.error("No encontro Cajas")

        def lista_ops(df):
            if df.empty: return [], {}
            col_id = next((c for c in df.columns if "id_operador" in c.lower()), df.columns[0])
            col_nom = next((c for c in df.columns if "nombre" in c.lower()), df.columns[1] if len(df.columns)>1 else col_id)
            lista=[]; mapa={}
            for _,r in df.iterrows():
                idv=str(r.get(col_id,"")).strip()
                if not idv or idv.lower()=="nan": continue
                nom=str(r.get(col_nom,"")).strip()
                if not nom: continue
                lista.append(nom); mapa[nom]=r.to_dict()
            return sorted(set(lista)), mapa

        def lista_tractos(df):
            if df.empty: return [], {}
            col_id = next((c for c in df.columns if "id_tractor" in c.lower()), df.columns[0])
            col_pla = next((c for c in df.columns if "placa" in c.lower()), df.columns[1] if len(df.columns)>1 else col_id)
            col_marca = next((c for c in df.columns if "marca" in c.lower()), None)
            lista=[]; mapa={}
            for _,r in df.iterrows():
                idv=str(r.get(col_id,"")).strip()
                if not idv or idv.lower()=="nan": continue
                pla=str(r.get(col_pla,"")).strip() or idv
                marca=str(r.get(col_marca,"")).strip() if col_marca else ""
                label = f"{pla} ({marca}) - {idv}" if marca and marca.lower()!="nan" else f"{pla} - {idv}"
                lista.append(label); mapa[label]=r.to_dict()
            return sorted(set(lista)), mapa

        def lista_cajas(df):
            if df.empty: return [], {}
            col_id = next((c for c in df.columns if "id_caja" in c.lower()), df.columns[0])
            col_pla = next((c for c in df.columns if "placa" in c.lower()), df.columns[1] if len(df.columns)>1 else col_id)
            col_cap = next((c for c in df.columns if "capacidad" in c.lower()), None)
            lista=[]; mapa={}
            for _,r in df.iterrows():
                idv=str(r.get(col_id,"")).strip()
                if not idv or idv.lower()=="nan": continue
                pla=str(r.get(col_pla,"")).strip() or idv
                cap=str(r.get(col_cap,"")).strip() if col_cap else ""
                label = f"{pla} ({cap}) - {idv}" if cap and cap.lower()!="nan" else f"{pla} - {idv}"
                lista.append(label); mapa[label]=r.to_dict()
            return sorted(set(lista)), mapa

        def lista_simple(df, id_key, nom_key):
            if df.empty: return [], {}
            col_id = next((c for c in df.columns if id_key.lower() in c.lower()), df.columns[0])
            col_nom = next((c for c in df.columns if nom_key.lower() in c.lower()), df.columns[1] if len(df.columns)>1 else col_id)
            lista=[]; mapa={}
            for _,r in df.iterrows():
                idv=str(r.get(col_id,"")).strip()
                if not idv or idv.lower()=="nan": continue
                nom=str(r.get(col_nom,"")).strip() or idv
                lista.append(nom); mapa[nom]=r.to_dict()
            return sorted(set(lista)), mapa

        ops_n, ops_m = lista_ops(df_op)
        trs_n, trs_m = lista_tractos(df_tr_u)
        cjs_n, cjs_m = lista_cajas(df_cj_u)
        cli_n, cli_m = lista_simple(df_cli, "id_cliente", "razon")
        des_n, des_m = lista_simple(df_des, "id_destino", "ciudad")
        fin_n, fin_m = lista_simple(df_fin, "id_finca", "nombre")

        st.markdown("### Transporte")
        c1,c2,c3=st.columns([2,1,1])
        with c1:
            op_sel=st.selectbox("Operador (SI lee)", ops_n if ops_n else ["No hay"], key="op_fix2")
            op_data=ops_m.get(op_sel,{})
            id_op=str(op_data.get('id_operador','') or op_sel)
        with c2:
            st.text_input("Licencia", value=str(op_data.get('licencia_num','') or op_data.get('licencia','')), disabled=True, key="lic_fix2")
        with c3:
            st.text_input("Tel", value=str(op_data.get('telefono','')), disabled=True, key="tel_fix2")

        c1,c2,c3=st.columns(3)
        with c1:
            tr_sel=st.selectbox("Tracto - FIX", trs_n if trs_n else ["No hay tractos"], key="tr_fix2")
            tr_data=trs_m.get(tr_sel,{})
            id_tr=str(tr_data.get('id_tractor','') or tr_sel)
            st.caption(f"ID:{id_tr} Placas:{tr_data.get('placas','') or tr_data.get('placa','')}")
        with c2:
            cj1_sel=st.selectbox("Caja1 - FIX", cjs_n if cjs_n else ["No hay cajas"], key="cj1_fix2")
            cj1_data=cjs_m.get(cj1_sel,{})
            id_cj1=str(cj1_data.get('id_caja','') or cj1_sel)
            st.caption(f"ID:{id_cj1}")
        with c3:
            cj2_sel=st.selectbox("Caja2 Full", ["(Vacio)"]+cjs_n, key="cj2_fix2")
            if cj2_sel!="(Vacio)":
                cj2_data=cjs_m.get(cj2_sel,{})
                id_cj2=str(cj2_data.get('id_caja','') or cj2_sel)
            else: id_cj2=""

        st.markdown("### Remision y Factura (NUEVO)")
        r1,r2,r3,r4=st.columns(4)
        with r1: lote=st.text_input("Lote", key="lote_fix")
        with r2: rem=st.text_input("Folio Remision (ahora o despues)", placeholder="REM-123", key="rem_fix")
        with r3: fac=st.text_input("Folio Factura (ahora o despues)", placeholder="FAC-123", key="fac_fix")
        with r4: fac2=st.text_input("Factura2 Full", placeholder="FAC-124", key="fac2_fix")

        st.markdown("### Ruta")
        col1,col2,col3=st.columns([2,1,1])
        with col1:
            fin_sel=st.multiselect("Fincas", fin_n, key="fin_fix")
            ids_fin=[]
            for fn in fin_sel:
                d=fin_m.get(fn,{})
                ids_fin.append(str(d.get('id_finca','') or fn))
        with col2:
            cli_sel=st.selectbox("Cliente", cli_n if cli_n else ["No hay"], key="cli_fix")
            cli_data=cli_m.get(cli_sel,{})
            id_cli=str(cli_data.get('id_cliente','') or cli_sel)
        with col3:
            des_sel=st.selectbox("Destino", des_n if des_n else ["No hay"], key="des_fix")
            des_data=des_m.get(des_sel,{})
            id_des=str(des_data.get('id_destino','') or des_sel)
        obs=st.text_area("Observaciones", key="obs_fix")

        if st.button("GENERAR ORDEN CON REMISION/FACTURA", type="primary", use_container_width=True):
            if not fin_sel:
                st.warning("Selecciona finca")
            elif "No hay" in tr_sel or "No hay" in cj1_sel:
                st.warning("Falta tracto/caja - revisa DEBUG, pon datos en Sheets")
            else:
                try:
                    id_orden=f"OC-{datetime.now().strftime('%Y%m%d%H%M')}-{id_op}"
                    ws_ord=sh.worksheet("OrdenesCarga")
                    ensure_columns_exist(ws_ord, ["folio_remision","folio_factura","folio_factura2","id_lote","observaciones"])
                    row={"id_orden":id_orden,"folio_orden":id_orden,"fecha_creacion":datetime.now().isoformat(),"id_usuario_crea":st.session_state.username,"id_operador":id_op,"id_tractor":id_tr,"id_caja1":id_cj1,"id_caja2":id_cj2,"id_cliente":id_cli,"id_destino":id_des,"id_lote":lote if lote else f"LOTE-{id_orden}","folio_remision":rem,"folio_factura":fac,"folio_factura2":fac2,"estado":"ABIERTA","observaciones":obs,"ruta_fincas_ids":",".join(ids_fin)}
                    append_row_dict_safe(ws_ord,row)
                    ws_ruta=sh.worksheet("Orden_Fincas")
                    for idx,fid in enumerate(ids_fin):
                        append_row_dict_safe(ws_ruta,{"id":f"{id_orden}-{fid}","id_orden":id_orden,"id_finca":fid,"orden_visita":idx+1,"estado_carga":"PENDIENTE"})
                    st.balloons(); st.success(f"ORDEN {id_orden} Rem:{rem} Fac:{fac}"); st.rerun()
                except Exception as e: st.error(str(e))

    with tab2:
        st.subheader("Editar Remision/Factura despues - carro ya se fue")
        df_ord, ws_ord = get_df_safe("OrdenesCarga")
        if df_ord.empty: st.warning("No hay ordenes")
        else:
            ids=list(reversed(df_ord['id_orden'].astype(str).tolist()))
            sel=st.selectbox("Orden", ids[:100], key="sel_edit_fix")
            if sel:
                fila=df_ord[df_ord['id_orden']==sel]
                if not fila.empty:
                    r=fila.iloc[0]
                    st.write(f"{r.get('id_orden','')} Lote:{r.get('id_lote','')} Estado:{r.get('estado','')}")
                    c1,c2,c3,c4=st.columns(4)
                    with c1: new_rem=st.text_input("Remision", value=str(r.get('folio_remision','') or ""), key="erem")
                    with c2: new_fac=st.text_input("Factura", value=str(r.get('folio_factura','') or ""), key="efac")
                    with c3: new_fac2=st.text_input("Factura2", value=str(r.get('folio_factura2','') or ""), key="efac2")
                    with c4: new_lote=st.text_input("Lote", value=str(r.get('id_lote','')), key="elote")
                    new_obs=st.text_area("Obs", value=str(r.get('observaciones','')), key="eobs")
                    if st.button("GUARDAR", type="primary", use_container_width=True):
                        try:
                            ws=sh.worksheet("OrdenesCarga")
                            ensure_columns_exist(ws, ["folio_remision","folio_factura","folio_factura2","id_lote","observaciones"])
                            cell=ws.find(sel)
                            headers=[str(h).strip() for h in ws.row_values(1)]
                            def idx_col(opts):
                                for o in opts:
                                    if o in headers: return headers.index(o)+1
                                return None
                            if idx_col(["folio_remision"]): ws.update_cell(cell.row, idx_col(["folio_remision"]), new_rem)
                            if idx_col(["folio_factura"]): ws.update_cell(cell.row, idx_col(["folio_factura"]), new_fac)
                            if idx_col(["folio_factura2"]): ws.update_cell(cell.row, idx_col(["folio_factura2"]), new_fac2)
                            if idx_col(["id_lote"]): ws.update_cell(cell.row, idx_col(["id_lote"]), new_lote)
                            if idx_col(["observaciones"]): ws.update_cell(cell.row, idx_col(["observaciones"]), new_obs)
                            st.success(f"Actualizada {sel}"); st.rerun()
                        except Exception as e: st.error(str(e))
            st.divider()
            st.dataframe(df_ord.tail(30), use_container_width=True)

    with tab3:
        df_stock,_=get_df_safe("Guias_Folios_Stock")
        st.dataframe(df_stock.tail(50) if not df_stock.empty else pd.DataFrame(), use_container_width=True)
    with tab4:
        for nombre in ["Fincas","Operadores","Tractos","Tractocamiones","Cajas","Cajas_Thermoking","Clientes","Destinos","OrdenesCarga"]:
            df,_=get_df_safe(nombre)
            with st.expander(f"{nombre} ({len(df)})"):
                st.dataframe(df, use_container_width=True)

elif st.session_state.rol=="VIGILANCIA":
    st.title("Vigilancia")
    df_of,_=get_df_safe("Orden_Fincas")
    df_oc,_=get_df_safe("OrdenesCarga")
    if df_of.empty: st.warning("No hay ordenes"); st.stop()
    finca=st.session_state.finca_asignada
    df_f=df_of if finca.upper()=="TODAS" else df_of[df_of['id_finca'].astype(str).str.upper()==finca.upper()]
    df_p=df_f[~df_f['estado_carga'].isin(['CARGADO_SALIO','EN_FINCA'])].copy()
    df_e=df_f[df_f['estado_carga']=='EN_FINCA'].copy()
    st.write(f"Pend:{len(df_p)} En finca:{len(df_e)}")
    for idx,row in df_p.iterrows():
        id_ord=str(row['id_orden']).strip()
        det=df_oc[df_oc['id_orden']==id_ord] if not df_oc.empty else pd.DataFrame()
        with st.container(border=True):
            st.write(f"{id_ord} Rem:{det.iloc[0].get('folio_remision','') if not det.empty else ''} Fac:{det.iloc[0].get('folio_factura','') if not det.empty else ''}")
            ft=st.file_uploader(f"Tractor {id_ord}", type=["jpg","png"], key=f"ft_{id_ord}_{idx}")
            fc=st.file_uploader(f"Caja {id_ord}", type=["jpg","png"], key=f"fc_{id_ord}_{idx}")
            if st.button(f"Entrada {id_ord}", key=f"ent_{id_ord}_{idx}"):
                if not ft or not fc: st.error("Fotos")
                else:
                    lt=subir_foto_a_drive(ft,f"ENT_{id_ord}.jpg")
                    lc=subir_foto_a_drive(fc,f"ENT_{id_ord}_C.jpg")
                    ws=sh.worksheet("Bitacora_Vigilancia") if "Bitacora_Vigilancia" in [w.title for w in sh.worksheets()] else sh.add_worksheet(title="Bitacora_Vigilancia", rows=1000, cols=12)
                    append_row_dict_safe(ws,{"id_bitacora":f"ENT-{id_ord}-{datetime.now().strftime('%H%M%S')}","id_orden":id_ord,"id_finca":row['id_finca'],"tipo_movimiento":"ENTRADA","fecha_hora":datetime.now().isoformat(),"id_usuario":st.session_state.username,"fotos_links":f"{lt}|{lc}"})
                    ws_of=sh.worksheet("Orden_Fincas")
                    for i,r in enumerate(ws_of.get_all_records(), start=2):
                        if str(r.get('id_orden'))==id_ord and str(r.get('id_finca')).upper()==str(row['id_finca']).upper():
                            ws_of.update_cell(i,5,"EN_FINCA"); break
                    st.success("OK"); st.rerun()
    for idx,row in df_e.iterrows():
        id_ord=str(row['id_orden']).strip()
        with st.container(border=True):
            st.write(f"SALIDA {id_ord}")
            fs=st.file_uploader(f"Salida {id_ord}", type=["jpg","png"], key=f"fs_{id_ord}_{idx}")
            if st.button(f"Salida {id_ord}", key=f"sal_{id_ord}_{idx}"):
                if not fs: st.error("Foto")
                else:
                    ls=subir_foto_a_drive(fs,f"SAL_{id_ord}.jpg")
                    ws=sh.worksheet("Bitacora_Vigilancia") if "Bitacora_Vigilancia" in [w.title for w in sh.worksheets()] else sh.add_worksheet(title="Bitacora_Vigilancia", rows=1000, cols=12)
                    append_row_dict_safe(ws,{"id_bitacora":f"SAL-{id_ord}-{datetime.now().strftime('%H%M%S')}","id_orden":id_ord,"id_finca":row['id_finca'],"tipo_movimiento":"SALIDA","fecha_hora":datetime.now().isoformat(),"id_usuario":st.session_state.username,"fotos_links":ls})
                    ws_of=sh.worksheet("Orden_Fincas")
                    for i,r in enumerate(ws_of.get_all_records(), start=2):
                        if str(r.get('id_orden'))==id_ord and str(r.get('id_finca')).upper()==str(row['id_finca']).upper():
                            ws_of.update_cell(i,5,"CARGADO_SALIO"); break
                    st.success("Salida OK"); st.rerun()

else:
    st.title("Planta")
    st.info("Planta simplificada")
