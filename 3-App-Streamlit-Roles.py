import streamlit as st
import pandas as pd
import datetime
import os, json
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import gspread

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
FOTOS_BANANO_FOLDER_ID = "1AW6qmZddxQG12q4rHKQmro7Ai3RYXhAR"

class BananoDB:
    def __init__(self, json_key_path="credentials.json", spreadsheet_name="Sistema_Banano_BD", drive_folder_id=FOTOS_BANANO_FOLDER_ID):
        try:
            if "google_credentials" in st.secrets:
                creds_info = dict(st.secrets["google_credentials"])
                creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
                spreadsheet_name = st.secrets["app_config"].get("spreadsheet_name", spreadsheet_name)
                drive_folder_id = st.secrets["app_config"].get("fotos_folder_id", drive_folder_id)
            else:
                raise KeyError
        except Exception:
            if os.path.exists(json_key_path):
                creds = Credentials.from_service_account_file(json_key_path, scopes=SCOPES)
            else:
                creds_info = json.loads(os.environ.get("GOOGLE_CREDENTIALS_JSON","{}"))
                creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)

        self.client = gspread.authorize(creds)
        self.sh = self.client.open(spreadsheet_name)
        self.drive_service = build('drive', 'v3', credentials=creds)
        self.drive_folder_id = drive_folder_id

    def get_df(self, sheet_name):
        try:
            ws = self.sh.worksheet(sheet_name)
            return pd.DataFrame(ws.get_all_records())
        except:
            return pd.DataFrame()

    def append_row_dict(self, sheet_name, data_dict):
        ws = self.sh.worksheet(sheet_name)
        headers = ws.row_values(1)
        row = [data_dict.get(h, "") for h in headers]
        ws.append_row(row, value_input_option='USER_ENTERED')
        return True

    def registrar_catalogo(self, sheet_name, data_dict):
        try:
            self.append_row_dict(sheet_name, data_dict)
            return True
        except Exception as e:
            print(f"Error al registrar en {sheet_name}: {e}")
            return False

    def registrar_termografo_o_filtro(self, tipo_item, folio, marca, estado="DISPONIBLE"):
        sheet_name = "Thermografos" if tipo_item == "THERMOGRAFO" else "Filtros"
        id_item = f"{tipo_item[0]}-{folio}"
        data = {
            "id_item": id_item,
            "folio": folio,
            "marca": marca,
            "estado": estado,
            "fecha_registro": datetime.datetime.now().isoformat()
        }
        return self.append_row_dict(sheet_name, data)

    def registrar_compra_guias(self, cantidad, precio, folio_compra):
        id_compra = f"COMP-{datetime.datetime.now().strftime('%Y%m%d%H%M')}"
        self.append_row_dict("Compra_Guias", {
            "id_compra": id_compra,
            "fecha_compra": datetime.datetime.now().isoformat(),
            "cantidad_juegos": cantidad,
            "precio_unitario": precio,
            "importe_total": cantidad*precio,
            "folio_compra_AAPS": folio_compra,
            "estado": "DISPONIBLE"
        })
        tipos = ["R", "E", "P", "D4", "D5"]
        for tipo in tipos:
            for i in range(1, cantidad+1):
                folio = f"{tipo}{i:02d}" if tipo in ["R","E","P"] else f"{tipo}-{i:02d}"
                self.append_row_dict("Guias_Folios_Stock", {
                    "id_folio": f"{id_compra}-{tipo}-{i}",
                    "id_compra": id_compra,
                    "tipo_documento": tipo,
                    "folio": folio,
                    "estado": "DISPONIBLE"
                })
        return id_compra

    def crear_orden_carga(self, operador_id, tractor_id, caja1_id, caja2_id, fincas_ids, cliente_id, destino_id):
        folio = f"OC-{datetime.datetime.now().strftime('%Y%m%d')}-{operador_id}"
        id_orden = folio
        data = {
            "id_orden": id_orden,
            "folio_orden": folio,
            "fecha_creacion": datetime.datetime.now().isoformat(),
            "id_usuario_crea": "OFICINA_CENTRAL",
            "id_operador": operador_id,
            "id_tractor": tractor_id,
            "id_caja1": caja1_id,
            "id_caja2": caja2_id if caja2_id else "",
            "id_cliente": cliente_id,
            "id_destino": destino_id,
            "id_lote": f"LOTE-{id_orden}",
            "estado": "ABIERTA",
            "ruta_fincas_ids": ",".join(fincas_ids)
        }
        self.append_row_dict("OrdenesCarga", data)
        for idx, finca_id in enumerate(fincas_ids):
            self.append_row_dict("Orden_Fincas", {
                "id": f"{id_orden}-{finca_id}",
                "id_orden": id_orden,
                "id_finca": finca_id,
                "orden_visita": idx+1,
                "estado_carga": "PENDIENTE"
            })
        return id_orden


# =========================================================================
# MÓDULO 1: OFICINA CENTRAL
# =========================================================================
def render_oficina_central_catalogos(db):
    st.markdown("### 🗂️ Oficina Central - Gestión y Órdenes")
    t1, t2, t3, t4 = st.tabs(["🚀 Crear Orden", "🗂️ Catálogos", "📑 Guías AAPS", "📦 Bodega"])

    with t1:
        st.subheader("Nueva Orden de Carga")
        df_op = db.get_df("Operadores")
        df_trac = db.get_df("Tractores")
        df_caja = db.get_df("Cajas")
        df_finca = db.get_df("Fincas")
        df_cli = db.get_df("Clientes")
        df_dest = db.get_df("Destinos")
        
        with st.form("f_oc"):
            c1, c2 = st.columns(2)
            with c1:
                op = st.selectbox("Operador", df_op['id_operador'].tolist() if not df_op.empty and 'id_operador' in df_op.columns else [])
                tr = st.selectbox("Tractocamión", df_trac['id_tractor'].tolist() if not df_trac.empty and 'id_tractor' in df_trac.columns else [])
                c_list = df_caja['id_caja'].tolist() if not df_caja.empty and 'id_caja' in df_caja.columns else []
                c1_id = st.selectbox("Caja 1", c_list)
                full = st.checkbox("¿Full (2 Cajas)?")
                c2_id = st.selectbox("Caja 2", [""] + c_list) if full else ""
            with c2:
                f_list = df_finca['id_finca'].tolist() if not df_finca.empty and 'id_finca' in df_finca.columns else []
                st.selectbox("Finca Titular", f_list)
                f_ruta = st.multiselect("Ruta de Fincas", f_list)
                cli = st.selectbox("Cliente", df_cli['id_cliente'].tolist() if not df_cli.empty and 'id_cliente' in df_cli.columns else [])
                dest = st.selectbox("Destino", df_dest['id_destino'].tolist() if not df_dest.empty and 'id_destino' in df_dest.columns else [])
            
            if st.form_submit_button("💾 Generar Orden"):
                if f_ruta:
                    folio = db.crear_orden_carga(op, tr, c1_id, c2_id, f_ruta, cli, dest)
                    st.success(f"Orden creada con éxito: {folio}")
                else:
                    st.error("Seleccione al menos una finca en ruta.")

    with t2:
        st.subheader("Catálogos Maestros")
        cat = st.selectbox("Catálogo", ["Fincas", "Operadores", "Tractores", "Cajas", "Clientes", "Destinos", "LineasTransporte"])
        with st.form("f_cat"):
            if cat == "Fincas":
                d = {"id_finca": st.text_input("Nombre Finca"), "tipo": st.selectbox("Tipo", ["PROPIA", "TERCERO"]), "ubicacion": st.text_input("Ubicación")}
            elif cat == "Operadores":
                d = {"id_operador": st.text_input("Nombre y Licencia"), "telefono": st.text_input("Teléfono"), "domicilio": st.text_input("Domicilio")}
            elif cat == "Tractores":
                d = {"id_tractor": st.text_input("Placas"), "modelo": st.text_input("Modelo"), "linea": st.text_input("Línea"), "num_economico": st.text_input("Económico")}
            elif cat == "Cajas":
                d = {"id_caja": st.text_input("Placas Caja"), "num_economico": st.text_input("Económico"), "linea": st.text_input("Línea")}
            elif cat == "Clientes":
                d = {"id_cliente": st.text_input("Razón Social"), "rfc": st.text_input("RFC"), "domicilio": st.text_input("Domicilio")}
            elif cat == "Destinos":
                d = {"id_destino": st.text_input("ID Destino")}
            else:
                d = {"razon_social": st.text_input("Razón Social"), "rfc": st.text_input("RFC"), "telefono": st.text_input("Teléfono")}
            
            if st.form_submit_button("Guardar en Google Sheets"):
                db.registrar_catalogo(cat, d)
                st.success("¡Guardado con éxito!")
        st.dataframe(db.get_df(cat), use_container_width=True)

    with t3:
        st.subheader("Guías Fitosanitarias AAPS")
        with st.form("f_guias"):
            j = st.number_input("Juegos", 1, 100, 20)
            p = st.number_input("Precio Unitario", 0.0, 1000.0, 250.0)
            fa = st.text_input("Factura AAPS")
            if st.form_submit_button("Registrar Compra y Folios"):
                db.registrar_compra_guias(int(j), float(p), fa)
                st.success("Folios generados correctamente.")
        st.dataframe(db.get_df("Guias_Folios_Stock"), use_container_width=True)

    with t4:
        st.subheader("Inventario de Bodega")
        with st.form("f_bodega"):
            t = st.selectbox("Tipo", ["THERMOGRAFO", "FILTRO"])
            f = st.text_input("Folio / Serie")
            m = st.text_input("Marca")
            if st.form_submit_button("Agregar"):
                db.registrar_termografo_o_filtro(t, f, m)
                st.success("Agregado a bodega.")
        
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            st.markdown("**Thermografos**")
            st.dataframe(db.get_df("Thermografos"), use_container_width=True)
        with c_b2:
            st.markdown("**Filtros**")
            st.dataframe(db.get_df("Filtros"), use_container_width=True)


# =========================================================================
# MÓDULO 2: CASETA DE VIGILANCIA
# =========================================================================
def render_caseta_vigilancia(db):
    st.markdown("### 🛡️ Caseta de Vigilancia - Control de Ingreso / Salida")
    df_ord = db.get_df("OrdenesCarga")
    
    if df_ord.empty:
        st.info("No hay órdenes de carga registradas todavía.")
        return

    ordenes_activas = df_ord[df_ord['estado'] == 'ABIERTA']['id_orden'].tolist()
    sel_orden = st.selectbox("Seleccione Orden de Carga Abierta", ordenes_activas if ordenes_activas else ["Sin órdenes abiertas"])

    if sel_orden and sel_orden != "Sin órdenes abiertas":
        with st.form("form_caseta"):
            st.markdown("#### Registro en Caseta")
            sello = st.text_input("Número de Sello de Seguridad")
            termografo_folio = st.text_input("Folio Termógrafo Instalado")
            filtro_folio = st.text_input("Folio Filtro Instalado")
            
            st.markdown("Evidencia Fotográfica (Unidad / Sello)")
            foto_subida = st.file_uploader("Subir Fotografía", type=["jpg", "png", "jpeg"])

            if st.form_submit_button("Confirmar Inspección y Salida de Caseta"):
                link_foto = ""
                if foto_subida is not None:
                    temp_path = os.path.join(".", foto_subida.name)
                    with open(temp_path, "wb") as f:
                        f.write(foto_subida.getbuffer())
                    link_foto = db.subir_foto_drive(temp_path, foto_subida.name)
                    os.remove(temp_path)
                
                db.append_row_dict("Caseta_Control", {
                    "id_registro": f"CASETA-{sel_orden}",
                    "id_orden": sel_orden,
                    "fecha_hora": datetime.datetime.now().isoformat(),
                    "sello": sello,
                    "termografo": termografo_folio,
                    "filtro": filtro_folio,
                    "foto_url": link_foto,
                    "estado": "VERIFICADO"
                })
                st.success(f"Caseta registrada exitosamente para la orden {sel_orden}.")


# =========================================================================
# MÓDULO 3: PLANTA EMPACADORA / FINCA
# =========================================================================
def render_planta_empacadora(db):
    st.markdown("### 🍌 Planta Empacadora - Recepción en Finca y Carga")
    df_ord = db.get_df("OrdenesCarga")
    
    if df_ord.empty:
        st.info("No hay órdenes disponibles para empacadora.")
        return

    ordenes_activas = df_ord[df_ord['estado'] == 'ABIERTA']['id_orden'].tolist()
    sel_orden = st.selectbox("Seleccionar Orden para Empaque", ordenes_activas if ordenes_activas else ["Sin órdenes"])

    if sel_orden and sel_orden != "Sin órdenes":
        with st.form("form_empaque"):
            finca_actual = st.text_input("Nombre de Finca de Proceso actual")
            cajas_procesadas = st.number_input("Cantidad de Cajas de banano empacadas", min_value=0, value=1000)
            observaciones = st.text_area("Observaciones de Calidad")

            if st.form_submit_button("Registrar Producción de Finca"):
                db.append_row_dict("Empaque_Finca", {
                    "id_empaque": f"EMP-{sel_orden}-{finca_actual}",
                    "id_orden": sel_orden,
                    "finca": finca_actual,
                    "cajas": cajas_procesadas,
                    "observaciones": observaciones,
                    "fecha": datetime.datetime.now().isoformat()
                })
                st.success("¡Producción registrada correctamente para esta finca!")


# =========================================================================
# PUNTO DE ENTRADA PRINCIPAL Y NAVEGACIÓN POR ROLES
# =========================================================================
if __name__ == "__main__":
    st.set_page_config(page_title="Sistema de Embarque Bananero", layout="wide")
    db = BananoDB()

    st.sidebar.title("Menú del Sistema")
    rol = st.sidebar.selectbox("Seleccione Módulo / Rol", [
        "Oficina Central", 
        "Caseta de Vigilancia", 
        "Planta Empacadora / Finca"
    ])

    st.sidebar.markdown("---")
    st.sidebar.info("Sistema conectado a Google Sheets y Google Drive.")

    if rol == "Oficina Central":
        render_oficina_central_catalogos(db)
    elif rol == "Caseta de Vigilancia":
        render_caseta_vigilancia(db)
    elif rol == "Planta Empacadora / Finca":
        render_planta_empacadora(db)
