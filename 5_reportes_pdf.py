"""
5 - REPORTES PDF - Despacho / Manifiesto y Semanal
Genera PDFs con firma del operador, thermografo, filtro, etc.
Requiere: pip install reportlab fpdf2
"""
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import datetime

def generar_manifiesto_despacho(datos_despacho, ruta_salida="manifiesto.pdf"):
    """
    datos_despacho = {
        'folio_despacho': 'DESP-FIN001-001',
        'folio_orden': 'OC-20260527',
        'finca': 'Finca La Esperanza (PROPIA)',
        'operador': 'Juan Perez - Lic A123',
        'tractor': 'ABC123 - Econ 101 - Kenworth',
        'caja': 'CJA001 - Placa CJA001',
        'cliente': 'Chiquita USA',
        'destino': 'McAllen TX',
        'lote': 'LOTE-OC-123',
        'factura': 'FAC-9876',
        'guia_fitosanitaria': 'R05, E05, P05, D4-05, D5-05',
        'cajas': 450,
        'carton': '18.5kg Export',
        'calidad': 'Premium',
        'thermografo': 'THERMO-001 Folio T100',
        'filtro': 'FILT-01 Num 50',
        'temp_pulpa': '14.5°C',
        'cuñas': '8 certificadas',
        'quien_estiba': 'Pedro y Jose',
        'preenfria_en': 'FIN-001',
        'semana': 22,
        'fecha': '2026-05-27',
        'firma_path': None # ruta local de firma png
    }
    c = canvas.Canvas(ruta_salida, pagesize=letter)
    w, h = letter
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, h-50, f"MANIFIESTO DE EMBARQUE - {datos_despacho['folio_despacho']}")
    c.setFont("Helvetica", 10)
    y = h-80
    lineas = [
        f"Orden de Carga: {datos_despacho['folio_orden']} | Finca: {datos_despacho['finca']}",
        f"Operador: {datos_despacho['operador']} | Tractor: {datos_despacho['tractor']} | Caja: {datos_despacho['caja']}",
        f"Cliente: {datos_despacho['cliente']} | Destino: {datos_despacho['destino']}",
        f"Lote: {datos_despacho['lote']} | Factura: {datos_despacho['factura']} | Guía Fitosanitaria: {datos_despacho['guia_fitosanitaria']}",
        f"Fecha: {datos_despacho['fecha']} | Semana: {datos_despacho['semana']} | Cantidad: {datos_despacho['cajas']} cajas",
        f"Cartón: {datos_despacho['carton']} | Calidad: {datos_despacho['calidad']} | Peso: 18.5kg",
        f"Thermógrafo: {datos_despacho['thermografo']} | Filtro: {datos_despacho['filtro']} | Temp Pulpa Salida: {datos_despacho['temp_pulpa']}",
        f"Cuñas: {datos_despacho['cuñas']} | Estibadores: {datos_despacho['quien_estiba']} | Preenfría en: {datos_despacho['preenfria_en']}",
    ]
    for linea in lineas:
        c.drawString(50, y, linea)
        y-=20
    y-=20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "Firma del Operador:")
    if datos_despacho.get('firma_path'):
        try:
            c.drawImage(ImageReader(datos_despacho['firma_path']), 200, y-60, width=200, height=80)
        except: pass
    c.rect(50, y-80, 500, 80)
    y-=110
    c.setFont("Helvetica", 8)
    c.drawString(50, y, "Este despacho se genera desde Sistema_Banano_BD - Oficina Central. Documento válido con firma digital.")
    c.save()
    print(f"PDF generado: {ruta_salida}")
    return ruta_salida

def generar_reporte_semanal(lista_despachos, semana, ruta="reporte_semanal.pdf"):
    # lista_despachos = [{'finca':'FIN-001','cajas':450},...]
    c = canvas.Canvas(ruta, pagesize=letter)
    w,h = letter
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, h-50, f"REPORTE SEMANAL DE DESPACHOS - Semana {semana}")
    c.setFont("Helvetica", 10)
    y = h-80
    total = sum(d['cajas'] for d in lista_despachos)
    for d in lista_despachos:
        c.drawString(50, y, f"Finca: {d['finca']} | Despachos: {d.get('despachos',1)} | Cajas: {d['cajas']} | Lote: {d.get('lote','')}")
        y-=18
    y-=20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"TOTAL SEMANA {semana}: {total} CAJAS")
    c.save()
    print(f"Reporte semanal: {ruta}")
    return ruta

if __name__ == "__main__":
    # Ejemplo
    generar_manifiesto_despacho({
        'folio_despacho':'DESP-FIN001-001','folio_orden':'OC-20260527','finca':'La Esperanza',
        'operador':'Juan Perez','tractor':'ABC123','caja':'CJA001','cliente':'Chiquita','destino':'McAllen',
        'lote':'LOTE-01','factura':'FAC-123','guia_fitosanitaria':'R05/E05/P05','cajas':450,
        'carton':'18.5kg','calidad':'Premium','thermografo':'T100','filtro':'F50','temp_pulpa':'14.5C',
        'cuñas':'8','quien_estiba':'Pedro','preenfria_en':'FIN-001','semana':22,'fecha':'2026-05-27'
    })
