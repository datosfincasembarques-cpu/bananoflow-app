
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pandas as pd
import datetime
import streamlit as st
import os, json

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
FOTOS_BANANO_FOLDER_ID = "1AW6qmZddxQG12q4rHKQmro7Ai3RYXhAR"

class BananoDB:
    def __init__(self, json_key_path="credentials.json", spreadsheet_name="Sistema_Banano_BD", drive_folder_id=FOTOS_BANANO_FOLDER_ID):
        # Cloud: lee secrets.toml
        try:
            if "google_credentials" in st.secrets:
                creds_info = dict(st.secrets["google_credentials"])
                creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
                spreadsheet_name = st.secrets["app_config"].get("spreadsheet_name", spreadsheet_name)
                drive_folder_id = st.secrets["app_config"].get("fotos_folder_id", drive_folder_id)
            else:
                raise KeyError
        except Exception:
            # Local
            if os.path.exists(json_key_path):
                creds = Credentials.from_service_account_file(json_key_path, scopes=SCOPES)
            else:
                # fallback env var
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

    def subir_foto_drive(self, local_path, nombre_archivo):
        file_metadata = {'name': nombre_archivo, 'parents': [self.drive_folder_id] if self.drive_folder_id else []}
        media = MediaFileUpload(local_path, mimetype='image/jpeg')
        file = self.drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
        self.drive_service.permissions().create(fileId=file['id'], body={'type':'anyone','role':'reader'}).execute()
        return file['webViewLink']

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

    def ordenes_por_finca(self, id_finca, rol="VIGILANCIA"):
        df_orden_fincas = self.get_df("Orden_Fincas")
        if df_orden_fincas.empty:
            return pd.DataFrame()
        filtradas = df_orden_fincas[df_orden_fincas['id_finca'] == id_finca]
        ids_orden = filtradas['id_orden'].unique().tolist()
        df_ordenes = self.get_df("OrdenesCarga")
        if df_ordenes.empty:
            return pd.DataFrame()
        return df_ordenes[df_ordenes['id_orden'].isin(ids_orden)]

    def cerrar_orden_si_ultima_finca(self, id_orden):
        df = self.get_df("Orden_Fincas")
        pendientes = df[(df['id_orden'] == id_orden) & (df['estado_carga'] != 'CARGADO')]
        if pendientes.empty:
            ws = self.sh.worksheet("OrdenesCarga")
            try:
                cell = ws.find(id_orden)
                ws.update_cell(cell.row, 14, "CERRADA")
                return True
            except:
                pass
        return False
