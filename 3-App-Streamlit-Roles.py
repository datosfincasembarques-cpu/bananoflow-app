# ==================================================
# SISTEMA DE EMBARQUES DE BANANO
# Archivo: 3-App-Streamlit-Roles.py
# Propósito: Control de embarques con roles, permisos y consultas
# ==================================================

import streamlit as st
import pandas as pd
from datetime import datetime
from ConexionBanano import ConexionBanano

# --------------------------
# CONFIGURACIÓN DE PÁGINA
# --------------------------
st.set_page_config(page_title="Sistema Embarques Banano", layout="wide")

# --------------------------
# CONEXIÓN A BASE DE DATOS
# --------------------------
conexion = ConexionBanano()

# --------------------------
# AUTENTICACIÓN DE USUARIO
# --------------------------
if "usuario" not in st.session_state:
    st.title("🔐 Inicio de Sesión")
    user = st.text_input("Usuario")
    passw = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        usrs = conexion.leer_hoja("Usuarios")
        ok = next((u for u in usrs if u["usuario"] == user and u["contraseña"] == passw), None)
        if ok:
            st.session_state.usuario = ok
            st.rerun()
        else:
            st.error("Credenciales inválidas")
    st.stop()

# Datos del usuario autenticado
usr = st.session_state.usuario
rol = usr["rol"]
finca_usr = usr["finca_asignada"]

# --------------------------
# MENÚ DINÁMICO POR ROL
# --------------------------
st.sidebar.title(f"👤 {usr['nombre_completo']}")
st.sidebar.info(f"Rol: {rol} | Finca: {finca_usr}")

# Menú según perfil del usuario
menu = ["🏠 Inicio", "📋 Órdenes de Carga", "🌴 Registro en Finca", "📊 Reportes"]
if rol in ["OFICINA_CENTRAL", "ADMIN"]:
    menu = [
        "🏠 Inicio",
        "📋 Crear Orden de Carga",
        "📑 Catálogos",
        "🚛 Compra de Guías",
        "📊 Reportes"
    ]

opcion = st.sidebar.radio("Menú", menu)

# ==================================================
# 📊 PANTALLA DE INICIO — DASHBOARD PRINCIPAL
# ==================================================
if opcion == "🏠 Inicio":
    st.header("📊 Panel de Control — Embarques Banano")
    st.markdown("---")

    try:
        # Leer datos directamente de tu base
        df_ordenes = pd.DataFrame(conexion.leer_hoja("OrdenesCarga"))
        df_guias = pd.DataFrame(conexion.leer_hoja("GuiasSanitarias_Folios"))

        # 📋 Cálculo: Órdenes pendientes de cierre
        ordenes_pendientes = 0
        ordenes_cerradas = 0
        ordenes_hoy = 0
        if "estado" in df_ordenes.columns:
            ordenes_pendientes = df_ordenes[df_ordenes["estado"] != "CERRADA"].shape[0]
            ordenes_cerradas = df_ordenes[df_ordenes["estado"] == "CERRADA"].shape[0]
        if "fecha_creacion" in df_ordenes.columns:
            hoy = datetime.now().strftime("%Y-%m-%d")
            ordenes_hoy = df_ordenes[df_ordenes["fecha_creacion"].astype(str).str.startswith(hoy)].shape[0]

        # 🚛 Cálculo: Guías disponibles y usadas
        guias_disponibles = 0
        guias_usadas = 0
        juegos_disponibles = 0
        juegos_usados = 0
        if "estado" in df_guias.columns:
            guias_disponibles = df_guias[df_guias["estado"] == "DISPONIBLE"].shape[0]
            guias_usadas = df_guias[df_guias["estado"] == "USADA"].shape[0]
            juegos_disponibles = guias_disponibles // 5  # 5 folios = 1 juego completo
            juegos_usados = guias_usadas // 5

        # 🎯 Tarjetas visuales
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="📋 Órdenes Pendientes de Cierre",
                value=f"{ordenes_pendientes}",
                delta=f"{ordenes_hoy} creadas hoy",
                delta_color="inverse"
            )
            st.caption("No cerradas aún")

        with col2:
            st.metric(
                label="🚛 Guías Sanitarias Disponibles",
                value=f"{juegos_disponibles} juegos",
                delta=f"{guias_disponibles} folios",
                delta_color="normal"
            )
            st.caption("Pendientes de uso")

        with col3:
            st.metric(
                label="✅ Guías Ya Utilizadas",
                value=f"{juegos_usados} juegos",
                delta=f"{guias_usadas} folios",
                delta_color="off"
            )
            st.caption("Asignadas a transporte")

        st.markdown("---")

        # 📋 Lista detallada de órdenes pendientes
        st.subheader("📋 Órdenes Pendientes de Cierre")
        if "estado" in df_ordenes.columns and not df_ordenes.empty:
            df_pendientes = df_ordenes[df_ordenes["estado"] != "CERRADA"]
            if not df_pendientes.empty:
                st.dataframe(
                    df_pendientes[["id_orden", "fecha_creacion", "id_operador", "fincas_carga", "estado"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.success("🎉 ¡Todas las órdenes han sido cerradas!")
        else:
            st.info("ℹ️ Sin datos de órdenes disponibles")

    except Exception as e:
        st.warning(f"ℹ️ Mostrando panel: {str(e)}")
        st.info("Verifica que existan las hojas con datos cargados")

    st.markdown("---")
    st.info("👇 Selecciona una opción del menú para continuar")

# ==================================================
# 📋 CREAR ORDEN DE CARGA — Solo Oficina Central/Admin
# ==================================================
elif opcion == "📋 Crear Orden de Carga":
    st.header("📋 Crear Orden de Carga")
    st.info("""
        Aquí se registran los datos del operador, vehículo, fincas de carga,
        guías sanitarias asignadas y datos del destino.
    """)
    # ── PEGA AQUÍ TU CÓDIGO DEL FORMULARIO DE CREACIÓN ──

# ==================================================
# 📑 CATÁLOGOS — Solo Oficina Central/Admin
# ==================================================
elif opcion == "📑 Catálogos":
    st.header("📑 Mantenimiento de Catálogos")
    st.info("""
        Fincas propias y de terceros, Líneas de transporte,
        Operadores, Tractocamiones, Cajas Thermoking, Clientes, Destinos.
    """)
    # ── PEGA AQUÍ TU CÓDIGO DE CATÁLOGOS ──

# ==================================================
# 🚛 COMPRA DE GUÍAS SANITARIAS — Solo Oficina Central/Admin
# ==================================================
elif opcion == "🚛 Compra de Guías":
    st.header("🚛 Compra y Registro de Guías Sanitarias")
    st.info("""
        Registro de lotes comprados a la AAPS, generación automática
        de folios por documento.
    """)
    # ── PEGA AQUÍ TU CÓDIGO DE COMPRA DE GUÍAS ──

# ==================================================
# 🌴 REGISTRO EN FINCA — Vigilancia / Encargado
# ==================================================
elif opcion == "🌴 Registro en Finca":
    st.header("🌴 Registro de Entrada y Carga en Finca")
    st.info("""
        📌 Caseta de Vigilancia: Hora de entrada, revisión de documentos, fotos.
        📌 Planta Empacadora: Estado de caja, llantas, cantidad de fruta, temperatura.
        📌 Preenfriado: Registro de tiempos y temperatura de pulpa.
    """)
    # ── PEGA AQUÍ TU CÓDIGO DE REGISTRO EN FINCA ──

# ==================================================
# 📊 REPORTES — Todos los usuarios
# ==================================================
elif opcion == "📊 Reportes":
    st.header("📊 Reportes y Consultas")
    st.info("""
        📋 Despachos por semana y finca
        🚛 Guías sanitarias usadas y disponibles
        📈 Estado de recorrido de transportes
    """)
    # ── PEGA AQUÍ TU CÓDIGO DE REPORTES ──

# ==================================================
# 📋 CONSULTA DE ÓRDENES DE CARGA — Fincas / Oficina
# ==================================================
elif opcion == "📋 Órdenes de Carga":
    st.header("📋 Consulta y Seguimiento de Órdenes de Carga")
    st.markdown("---")

    try:
        # Leer todas las órdenes
        df_ordenes = pd.DataFrame(conexion.leer_hoja("OrdenesCarga"))

        if df_ordenes.empty:
            st.info("ℹ️ No hay órdenes registradas aún")
        else:
            # ── FILTROS DE BÚSQUEDA ──
            st.subheader("🔍 Filtros")
            col_f1, col_f2, col_f3 = st.columns(3)

            with col_f1:
                estados = ["TODOS"]
                if "estado" in df_ordenes.columns:
                    estados += sorted(df_ordenes["estado"].dropna().unique().tolist())
                filtro_estado = st.selectbox("Estado de la Orden", estados)

            with col_f2:
                operadores = ["TODOS"]
                if "id_operador" in df_ordenes.columns:
                    operadores += sorted(df_ordenes["id_operador"].dropna().unique().tolist())
                filtro_operador = st.selectbox("Operador", operadores)

            with col_f3:
                filtro_fecha = st.text_input("Fecha (AAAA-MM-DD)", placeholder="Ej: 2026-08-28")

            # ── APLICAR FILTROS ──
            df_filtrado = df_ordenes.copy()

            if filtro_estado != "TODOS" and "estado" in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado["estado"] == filtro_estado]

            if filtro_operador != "TODOS" and "id_operador" in df_filtrado.columns:
                df_filtrado = df_filtrado[df_filtrado["id_operador"] == filtro_operador]

            if filtro_fecha.strip() and "fecha_creacion" in df_filtrado.columns:
                df_filtrado = df_filtrado[
                    df_filtrado["fecha_creacion"].astype(str).str.startswith(filtro_fecha.strip())
                ]

            # ── APLICAR PERMISOS POR FINCA ──
            # Si NO es oficina central/admin → solo ver sus fincas asignadas
            if rol not in ["OFICINA_CENTRAL", "ADMIN"]:
                if "fincas_carga" in df_filtrado.columns:
                    df_filtrado = df_filtrado[
                        df_filtrado["fincas_carga"].astype(str).str.contains(str(finca_usr), case=False, na=False)
                    ]
                    st.info(f"🔒 Mostrando solo órdenes de su finca: **{finca_usr}**")

            # ── MOSTRAR RESULTADOS ──
            st.markdown("---")
            st.subheader(f"📋 Órdenes Encontradas: **{len(df_filtrado)}**")

            columnas_mostrar = [
                "id_orden", "fecha_creacion", "id_operador",
                "id_tractor", "fincas_carga", "cantidad_cajas",
                "folio_factura", "estado"
            ]
            # Verificar que las columnas existan
            columnas_validas = [c for c in columnas_mostrar if c in df_filtrado.columns]

            st.dataframe(
                df_filtrado[columnas_validas].sort_values("id_orden", ascending=False),
                use_container_width=True,
                hide_index=True,
                height=500
            )

            # ── VER DETALLE DE UNA ORDEN ──
            st.markdown("---")
            st.subheader("🔎 Ver Detalle de una Orden")
            lista_ordenes = ["Seleccione..."]
            if "id_orden" in df_filtrado.columns:
                lista_ordenes += sorted(df_filtrado["id_orden"].dropna().unique().tolist(), reverse=True)
            orden_seleccionada = st.selectbox("Seleccione el Número de Orden", lista_ordenes)

            if orden_seleccionada and orden_seleccionada != "Seleccione...":
                detalle = df_ordenes[df_ordenes["id_orden"] == orden_seleccionada]
                if not detalle.empty:
                    detalle = detalle.iloc[0]
                    st.write("#### 📋 Datos Generales de la Orden")
                    st.json(detalle.to_dict())

                    # Botón para cerrar orden (solo Oficina Central)
                    if rol in ["OFICINA_CENTRAL", "ADMIN"]:
                        if "estado" in detalle and detalle["estado"] != "CERRADA":
                            st.markdown("---")
                            if st.button("🔒 Marcar Orden como CERRADA"):
                                # Buscar fila en la hoja
                                filas = conexion.leer_hoja("OrdenesCarga")
                                cerrada = False
                                for i, fila in enumerate(filas, start=2):  # fila 1 = encabezados
                                    if fila.get("id_orden") == orden_seleccionada:
                                        conexion.actualizar_celda("OrdenesCarga", i, 11, "CERRADA")
                                        st.success(f"✅ Orden {orden_seleccionada} ha sido CERRADA")
                                        cerrada = True
                                        st.rerun()
                                        break
                                if not cerrada:
                                    st.warning("⚠️ No se encontró la fila para actualizar")

    except Exception as e:
        st.error(f"⚠️ Error al consultar órdenes: {str(e)}")
        st.info("Verifica que la hoja 'OrdenesCarga' exista y tenga los encabezados correctos")
