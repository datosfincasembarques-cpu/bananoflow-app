# app.py — Tu código existente + DASHBOARD (sin modificar tu lógica)
import streamlit as st
import pandas as pd
from datetime import datetime
from ConexionBanano import ConexionBanano

st.set_page_config(page_title="Sistema Embarques Banano", layout="wide")

# === TU CONEXIÓN EXISTENTE — NO SE MODIFICA ===
conexion = ConexionBanano()

# === TU AUTENTICACIÓN EXISTENTE — NO SE MODIFICA ===
if "usuario" not in st.session_state:
    st.title("🔐 Inicio de Sesión")
    user = st.text_input("Usuario")
    passw = st.text_input("Contraseña", type="password")
    if st.button("Ingresar"):
        usrs = conexion.leer_hoja("Usuarios")
        ok = next((u for u in usrs if u["usuario"]==user and u["contraseña"]==passw), None)
        if ok:
            st.session_state.usuario = ok
            st.rerun()
        else:
            st.error("Credenciales inválidas")
    st.stop()

usr = st.session_state.usuario
rol = usr["rol"]
finca_usr = usr["finca_asignada"]

# === TU MENÚ EXISTENTE — NO SE MODIFICA ===
st.sidebar.title(f"👤 {usr['nombre_completo']}")
st.sidebar.info(f"Rol: {rol} | Finca: {finca_usr}")

menu = ["🏠 Inicio", "📋 Órdenes de Carga", "🚛 Guias Sanitarias", "🌴 Registro en Finca", "📊 Reportes"]
if rol in ["OFICINA_CENTRAL","ADMIN"]:
    menu = ["🏠 Inicio", "📋 Crear Orden de Carga", "📑 Catálogos", "🚛 Compra de Guías", "📊 Reportes"]

opcion = st.sidebar.radio("Menú", menu)

# ==================================================
# 📊 DASHBOARD — AGREGADO SIN TOCAR TU LÓGICA
# ==================================================
if opcion == "🏠 Inicio":
    st.header("📊 Panel de Control — Embarques Banano")
    st.markdown("---")

    try:
        # Leer datos usando TUS métodos existentes — SIN CAMBIOS
        df_ordenes = pd.DataFrame(conexion.leer_hoja("OrdenesCarga"))
        df_guias = pd.DataFrame(conexion.leer_hoja("GuiasSanitarias_Folios"))

        # === CÁLCULO DE INDICADORES ===
        # 📋 Órdenes pendientes de cerrar (no cerradas)
        ordenes_pendientes = 0
        ordenes_cerradas = 0
        if "estado" in df_ordenes.columns:
            ordenes_pendientes = df_ordenes[df_ordenes["estado"] != "CERRADA"].shape[0]
            ordenes_cerradas = df_ordenes[df_ordenes["estado"] == "CERRADA"].shape[0]

        # 🚛 Guías pendientes de usar (DISPONIBLES)
        guias_disponibles = 0
        guias_usadas = 0
        juegos_disponibles = 0
        juegos_usados = 0
        if "estado" in df_guias.columns:
            guias_disponibles = df_guias[df_guias["estado"] == "DISPONIBLE"].shape[0]
            guias_usadas = df_guias[df_guias["estado"] == "USADA"].shape[0]
            juegos_disponibles = guias_disponibles // 5  # 5 folios = 1 guía completa
            juegos_usados = guias_usadas // 5

        # 📅 Órdenes creadas hoy
        ordenes_hoy = 0
        if "fecha_creacion" in df_ordenes.columns:
            hoy = datetime.now().strftime("%Y-%m-%d")
            ordenes_hoy = df_ordenes[df_ordenes["fecha_creacion"].astype(str).str.startswith(hoy)].shape[0]

        # === MOSTRAR TARJETAS ===
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                label="📋 Órdenes Pendientes de Cierre",
                value=f"{ordenes_pendientes}",
                delta=f"{ordenes_hoy} de hoy",
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

        # === LISTA DE ÓRDENES PENDIENTES ===
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
# === TU LÓGICA DE PANTALLAS RESTANTES — SIN CAMBIOS ===
# ==================================================
elif opcion == "📋 Crear Orden de Carga":
    # TU CÓDIGO EXISTENTE — NO SE MODIFICA
    pass

elif opcion == "🚛 Compra de Guías":
    # TU CÓDIGO EXISTENTE — NO SE MODIFICA
    pass

elif opcion == "📑 Catálogos":
    # TU CÓDIGO EXISTENTE — NO SE MODIFICA
    pass

elif opcion == "🌴 Registro en Finca":
    # TU CÓDIGO EXISTENTE — NO SE MODIFICA
    pass

elif opcion == "📊 Reportes":
    # TU CÓDIGO EXISTENTE — NO SE MODIFICA
    pass

# ... mantén el resto de tu código tal cual lo tenías ...
