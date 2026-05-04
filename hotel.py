import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import math
import json
import hashlib
from supabase import create_client, Client

# ============================================================================
# CONFIGURACIÓN INICIAL
# ============================================================================
st.set_page_config(page_title="Sistema Hotelero CA13", page_icon="🏨", layout="wide")

# ============================================================================
# CONEXIÓN A SUPABASE (Persistencia en la Nube)
# ============================================================================
try:
    SUPABASE_URL = st.secrets["https://santdbbuwwofahucbyzb.supabase.co/rest/v1/"]
    SUPABASE_KEY = st.secrets["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNhbnRkYmJ1d3dvZmFodWNieXpiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzc5MDg3NzgsImV4cCI6MjA5MzQ4NDc3OH0.3MOLvuahpPtJvXaL_a5yqEM5VJB_pLWHInQvNzNqHx8"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    DB_AVAILABLE = True
except KeyError:
    # Modo desarrollo local sin Supabase configurado
    DB_AVAILABLE = False
    supabase = None
    st.warning("⚠️ Modo local: Los datos NO persistirán al recargar. Configura SUPABASE_URL y SUPABASE_KEY en Secrets.")

# ============================================================================
# FUNCIONES DE BASE DE DATOS (Supabase)
# ============================================================================
def db_upsert(table: str, data: dict, pk_column: str = "numero"):
    """Inserta o actualiza un registro en Supabase"""
    if not DB_AVAILABLE or not supabase:
        return None
    try:
        response = supabase.table(table).upsert(data, on_conflict=pk_column).execute()
        return response.data
    except Exception as e:
        st.error(f"❌ Error en DB upsert ({table}): {e}")
        return None

def db_select(table: str, filters: dict = None, order_by: str = None):
    """Consulta registros desde Supabase"""
    if not DB_AVAILABLE or not supabase:
        return []
    try:
        query = supabase.table(table).select("*")
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        if order_by:
            query = query.order(order_by)
        response = query.execute()
        return response.data or []
    except Exception as e:
        st.warning(f"⚠️ Error en DB select ({table}): {e}")
        return []

def db_insert_historial(tipo_registro: str, data: dict):
    """Inserta un nuevo registro en el historial"""
    if not DB_AVAILABLE or not supabase:
        return None
    try:
        response = supabase.table("historial").insert({
            "tipo_registro": tipo_registro,
            "data": data
        }).execute()
        return response.data
    except Exception as e:
        st.error(f"❌ Error insertando historial: {e}")
        return None

def init_db_tables():
    """Inicializa datos base si las tablas están vacías"""
    if not DB_AVAILABLE:
        return
    
    # Verificar si ya hay habitaciones
    existing = db_select("habitaciones")
    if not existing:
        # Crear habitaciones estándar
        for numero, tipo in HABITACIONES_STD:
            db_upsert("habitaciones", {
                "numero": numero, "tipo": tipo, "estado": "Disponible",
                "cliente": None, "reserva": None, "obs": "", "inicio": None,
                "tipo_pago_priv": None, "horas_extra_priv": 0, "penalizaciones": 0
            }, pk_column="numero")
        # Crear privadas
        for privada in PRIVADAS:
            db_upsert("habitaciones", {
                "numero": privada, "tipo": "PRIVADA", "estado": "Disponible",
                "cliente": None, "reserva": None, "obs": "", "inicio": None,
                "tipo_pago_priv": None, "horas_extra_priv": 0, "penalizaciones": 0
            }, pk_column="numero")
        st.success("✅ Base de datos inicializada correctamente")

# ============================================================================
# FUNCIONES DE AUTENTICACIÓN (con Secrets)
# ============================================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def authenticate(username: str, password: str) -> dict:
    """Verifica credenciales usando st.secrets"""
    try:
        secrets = st.secrets
        users = {
            "admin": {"password": hash_password(secrets.get("ADMIN_PASSWORD", "12345")), "role": "admin", "name": "Administrador"},
            "hotelca13": {"password": hash_password(secrets.get("HOTEL_PASSWORD", "123456789")), "role": "user", "name": "Hotel CA13"}
        }
        if username in users and users[username]["password"] == hash_password(password):
            return users[username]
    except Exception:
        # Fallback para desarrollo local
        fallback = {
            "admin": {"password": hash_password("12345"), "role": "admin", "name": "Administrador"},
            "hotelca13": {"password": hash_password("123456789"), "role": "user", "name": "Hotel CA13"}
        }
        if username in fallback and fallback[username]["password"] == hash_password(password):
            return fallback[username]
    return None

# ============================================================================
# CONSTANTES
# ============================================================================
PRIVADAS = ['PRIVADA 1', 'PRIVADA 2', 'PRIVADA 3', 'PRIVADA 4', 'PRIVADA 5']
HABITACIONES_STD = [
    ('A2', 'SENCILLA'), ('A3', 'SENCILLA'), ('A4', 'DOBLE'), ('A5', 'DOBLE'),
    ('A6', 'SENCILLA'), ('A7', 'TRIPLE'), ('A8', 'DOBLE'), ('A9', 'DOBLE'),
    ('A10', 'SENCILLA'), ('A11', 'SENCILLA'), ('A12', 'SENCILLA'), ('A13', 'SENCILLA'),
    ('A14', 'TRIPLE'), ('A15', 'SENCILLA'), ('A16', 'SENCILLA'), ('A17', 'SENCILLA'),
    ('B0', 'SENCILLA'), ('B1', 'SENCILLA'), ('B2', 'DOBLE'), ('B3', 'SENCILLA'),
    ('B4', 'SENCILLA'), ('B5', 'SENCILLA'), ('B6', 'SENCILLA'), ('B7', 'SENCILLA'),
    ('B8', 'DOBLE'), ('B9', 'SENCILLA'), ('C1', 'SENCILLA'), ('C2', 'SENCILLA'),
    ('C3', 'SENCILLA'), ('C4', 'SENCILLA'), ('C5', 'TRIPLE'), ('C6', 'DOBLE'), ('C7', 'DOBLE')
]
TARIFAS = {'SENCILLA': (600, 714), 'DOBLE': (1000, 1190), 'TRIPLE': (1300, 1547)}
ESTADOS = ['Disponible', 'Ocupada', 'Reservada', 'Mantenimiento', 'Pendiente de limpieza']
COLORES = {'Disponible': '#28a745', 'Ocupada': '#dc3545', 'Reservada': '#007bff', 'Mantenimiento': '#ffc107', 'Pendiente de limpieza': '#6f42c1'}

# ============================================================================
# HELPERS - CÁLCULOS
# ============================================================================
def calc_privada_cost(inicio, fin, tipo_pago, horas_extra=0):
    if isinstance(inicio, str): inicio = datetime.fromisoformat(inicio)
    if isinstance(fin, str): fin = datetime.fromisoformat(fin)
    if tipo_pago == "1 noche":
        return 800, "1 noche"
    horas = (fin - inicio).total_seconds() / 3600
    base = 400 if horas <= 3 else 400 + math.ceil(horas - 3) * 150
    total = base + (horas_extra * 150)
    return total, f"{horas:.1f}h + {horas_extra}h extra" if horas_extra else f"{horas:.1f}h"

def calc_hab_cost(tipo, fact, dias):
    base = TARIFAS[tipo][1] if fact == "Con facturación" else TARIFAS[tipo][0]
    return base * dias

def get_next_checkout(fecha, hora):
    if isinstance(fecha, str): fecha = datetime.fromisoformat(fecha).date()
    if isinstance(hora, str): hora = datetime.fromisoformat(hora).time()
    if hora.hour < 6:
        return datetime.combine(fecha, datetime.strptime("11:00", "%H:%M").time())
    return datetime.combine(fecha + timedelta(days=1), datetime.strptime("11:00", "%H:%M").time())

# ============================================================================
# INICIALIZACIÓN DE SESSION STATE
# ============================================================================
def init_session_state():
    # Autenticación
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    
    # Navegación
    if 'page' not in st.session_state:
        st.session_state.page = 'Dashboard'
    if 'show_success' not in st.session_state:
        st.session_state.show_success = ""
    
    # Contadores para limpiar formularios
    for key in ['form_counter_priv', 'form_counter_hab', 'form_counter_res_basica', 'form_counter_res_pa']:
        if key not in st.session_state:
            st.session_state[key] = 0
    
    # Cargar habitaciones desde Supabase
    if 'habitaciones' not in st.session_state:
        if DB_AVAILABLE:
            db_rooms = db_select("habitaciones")
            if db_rooms:
                st.session_state.habitaciones = {r['numero']: r for r in db_rooms}
            else:
                init_db_tables()
                db_rooms = db_select("habitaciones")
                st.session_state.habitaciones = {r['numero']: r for r in db_rooms} if db_rooms else {}
        else:
            # Fallback local para desarrollo
            st.session_state.habitaciones = {n: {'numero': n, 'tipo': t, 'estado': 'Disponible', 'cliente': None, 'reserva': None, 'obs': '', 'inicio': None, 'tipo_pago_priv': None, 'horas_extra_priv': 0, 'penalizaciones': 0} for n, t in HABITACIONES_STD}
            st.session_state.habitaciones.update({p: {'numero': p, 'tipo': 'PRIVADA', 'estado': 'Disponible', 'cliente': None, 'reserva': None, 'obs': '', 'inicio': None, 'tipo_pago_priv': None, 'horas_extra_priv': 0, 'penalizaciones': 0} for p in PRIVADAS})
    
    # Cargar historial
    if 'historial_hab' not in st.session_state:
        if DB_AVAILABLE:
            db_hist = db_select("historial", {"tipo_registro": "HABITACION"})
            st.session_state.historial_hab = [h['data'] for h in db_hist] if db_hist else []
        else:
            st.session_state.historial_hab = []
    
    if 'historial_priv' not in st.session_state:
        if DB_AVAILABLE:
            db_hist = db_select("historial", {"tipo_registro": "PRIVADA"})
            st.session_state.historial_priv = [h['data'] for h in db_hist] if db_hist else []
        else:
            st.session_state.historial_priv = []
    
    # Cargar empresas
    if 'empresas' not in st.session_state:
        if DB_AVAILABLE:
            db_emp = db_select("empresas")
            st.session_state.empresas = {e['nombre']: e['rtn'] for e in db_emp} if db_emp else {}
        else:
            st.session_state.empresas = {}

# ============================================================================
# LOGIN SCREEN
# ============================================================================
def login_screen():
    st.markdown("<h1 style='text-align: center; color: #1e3a5f;'>🏨 Sistema de Hotelería CA13</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Ingresa tus credenciales para continuar</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            username = st.text_input("👤 Usuario", placeholder="admin o hotelca13")
            password = st.text_input("🔒 Contraseña", type="password", placeholder="•••••••••")
            submit = st.form_submit_button("🔐 Iniciar Sesión", use_container_width=True)
            
            if submit:
                if username and password:
                    user = authenticate(username, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.current_user = {'username': username, **user}
                        st.success(f"✅ Bienvenido, {user['name']}")
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos")
                else:
                    st.warning("⚠️ Por favor completa todos los campos")
        
        st.markdown("---")
        st.caption("🔐 Derechos Reservados Hotel CA13")

# ============================================================================
# MAIN APP
# ============================================================================
def main_app():
    with st.sidebar:
        st.title("🏨 HOTEL CA13")
        
        if st.session_state.current_user:
            st.info(f"👤 {st.session_state.current_user['name']}\n\n🔑 {st.session_state.current_user['username']}")
            if st.button("🚪 Cerrar Sesión", key="btn_logout"):
                st.session_state.authenticated = False
                st.session_state.current_user = None
                st.rerun()
        
        st.markdown("---")
        st.radio("Navegación", ["Dashboard", "Habitaciones", "Clientes", "Reservas"], 
                 index=["Dashboard", "Habitaciones", "Clientes", "Reservas"].index(st.session_state.page),
                 label_visibility="collapsed", key="nav")
        st.session_state.page = st.session_state.nav
        
        st.markdown("---")
        st.caption("💾 Estado de persistencia")
        st.caption(f"{'✅ Conectado a Supabase' if DB_AVAILABLE else '⚠️ Modo local (datos temporales)'}")
        
        if DB_AVAILABLE and st.button("🔄 Sincronizar con nube", key="btn_sync"):
            init_session_state()
            st.success("✅ Datos actualizados desde la nube")

    # ================= DASHBOARD =================
    if st.session_state.page == "Dashboard":
        st.title("📊 Dashboard - Historial de Ventas")
        tab1, tab2 = st.tabs(["📋 Historial de Habitaciones", "🔒 Historial de Privadas"])
        
        cols_hab = ['ID', 'NOMBRE_Y_APELLIDO', 'TELEFONO', 'PROCEDENCIA', 'NOMBRE_EMPRESA', 'RTN', 'FACTURACION', 'HABITACION', 'METODO_PAGO', 'MONTO', 'FECHA_INGRESO']
        cols_priv = ['ID', 'HABITACION', 'FECHA_INGRESO', 'MONTO', 'FACTURACION']
        
        with tab1:
            st.subheader("Filtros de Fecha")
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                fecha_inicio_hab = st.date_input("Desde", datetime.now().date() - timedelta(days=7), key="f_inicio_hab")
            with col_f2:
                fecha_fin_hab = st.date_input("Hasta", datetime.now().date(), key="f_fin_hab")
            with col_f3:
                st.button("Filtrar", key="btn_filtro_hab")
            
            if st.session_state.historial_hab:
                df_hab = pd.DataFrame(st.session_state.historial_hab)
                if 'FECHA_INGRESO' in df_hab.columns:
                    df_hab['FECHA_INGRESO'] = pd.to_datetime(df_hab['FECHA_INGRESO'], errors='coerce')
                    mask = (df_hab['FECHA_INGRESO'].dt.date >= fecha_inicio_hab) & (df_hab['FECHA_INGRESO'].dt.date <= fecha_fin_hab)
                    df_filtrado = df_hab[mask].copy()
                else:
                    df_filtrado = df_hab.copy()
                
                for col in cols_hab:
                    if col not in df_filtrado.columns:
                        df_filtrado[col] = ''
                
                st.dataframe(df_filtrado[cols_hab], use_container_width=True, hide_index=True)
                
                if 'MONTO' in df_filtrado.columns and not df_filtrado.empty:
                    total = pd.to_numeric(df_filtrado['MONTO'], errors='coerce').sum()
                    st.success(f"💰 Total del período: L {total:,.2f}")
            else: 
                st.info("Sin registros aún.")
            
        with tab2:
            st.subheader("Filtros de Fecha")
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                fecha_inicio_priv = st.date_input("Desde", datetime.now().date() - timedelta(days=7), key="f_inicio_priv")
            with col_p2:
                fecha_fin_priv = st.date_input("Hasta", datetime.now().date(), key="f_fin_priv")
            with col_p3:
                st.button("Filtrar", key="btn_filtro_priv")
            
            if st.session_state.historial_priv:
                df_priv = pd.DataFrame(st.session_state.historial_priv)
                if 'FECHA_INGRESO' in df_priv.columns:
                    df_priv['FECHA_INGRESO'] = pd.to_datetime(df_priv['FECHA_INGRESO'], errors='coerce')
                    mask = (df_priv['FECHA_INGRESO'].dt.date >= fecha_inicio_priv) & (df_priv['FECHA_INGRESO'].dt.date <= fecha_fin_priv)
                    df_filtrado = df_priv[mask].copy()
                else:
                    df_filtrado = df_priv.copy()
                
                st.dataframe(df_filtrado[cols_priv], use_container_width=True, hide_index=True)
                
                if 'MONTO' in df_filtrado.columns and not df_filtrado.empty:
                    total = pd.to_numeric(df_filtrado['MONTO'], errors='coerce').sum()
                    st.success(f"💰 Total del período: L {total:,.2f}")
            else: 
                st.info("Sin registros aún.")

    # ================= HABITACIONES =================
    elif st.session_state.page == "Habitaciones":
        st.title("🛏️ Estado de Habitaciones")
        
        if st.session_state.show_success:
            st.success(st.session_state.show_success)
            st.session_state.show_success = ""
        
        hab_sel = st.selectbox("Seleccionar Habitación", sorted(st.session_state.habitaciones.keys()), key="sel_hab")
        hab = st.session_state.habitaciones[hab_sel]
        
        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            st.metric("Tipo", hab['tipo'])
        with col_info2:
            st.metric("Estado", hab['estado'])
        with col_info3:
            if hab.get('obs'):
                st.info(f"📝 {hab['obs']}")
        
        # Penalización para Privadas
        if hab_sel in PRIVADAS and hab['estado'] == 'Ocupada':
            st.markdown("---")
            st.subheader("⚠️ Gestión de Penalización")
            
            if hab.get('inicio'):
                inicio = hab['inicio']
                if isinstance(inicio, str): inicio = datetime.fromisoformat(inicio)
                ahora = datetime.now()
                diff = ahora - inicio
                horas, resto = divmod(int(diff.total_seconds()), 3600)
                minutos, segundos = divmod(resto, 60)
                st.info(f"⏱️ Tiempo transcurrido: {horas}h {minutos}m {segundos}s")
                
                tipo_pago = hab.get('tipo_pago_priv', '3 horas')
                horas_extra = hab.get('horas_extra_priv', 0)
                penalizaciones = hab.get('penalizaciones', 0)
                monto_base = 400 if tipo_pago == "3 horas" else 800
                monto_actual = monto_base + (horas_extra * 150) + (penalizaciones * 150)
                
                col_pen1, col_pen2 = st.columns(2)
                with col_pen1:
                    st.metric("💰 Monto actual", f"L {monto_actual}")
                with col_pen2:
                    if st.button("⚡ Aplicar Penalización (+L 150)", key=f"btn_penalizacion_{hab_sel}", type="primary"):
                        hab['penalizaciones'] = penalizaciones + 1
                        nuevo_monto = monto_actual + 150
                        obs_actual = hab.get('obs', '')
                        hab['obs'] = f"{obs_actual} | ⚠️ Penalización aplicada"
                        
                        # Actualizar en historial_priv
                        for registro in reversed(st.session_state.historial_priv):
                            if registro.get('HABITACION') == hab_sel and registro.get('FECHA_INGRESO') == hab['inicio']:
                                registro['MONTO'] = nuevo_monto
                                registro['FACTURACION'] = f"{registro.get('FACTURACION', '')} + Penalización"
                                break
                        
                        # Guardar en Supabase
                        if DB_AVAILABLE:
                            db_upsert("habitaciones", hab, pk_column="numero")
                            # Actualizar historial en DB (simplificado)
                        
                        st.session_state.show_success = f"✅ Penalización de L 150 aplicada a {hab_sel}"
                        st.rerun()
                
                if penalizaciones > 0:
                    st.warning(f"📋 Penalizaciones aplicadas: {penalizaciones} × L 150 = L {penalizaciones * 150}")
        
        # Mantenimiento con observación
        if hab['estado'] == 'Mantenimiento' or (st.session_state.get('temp_estado') == 'Mantenimiento' and st.session_state.get('temp_hab') == hab_sel):
            if hab['estado'] != 'Mantenimiento':
                st.warning("⚠️ Configurar observación de mantenimiento")
                obs_mantenimiento = st.text_area("Observación de mantenimiento", key=f"obs_mant_{hab_sel}", height=70)
                c_acc, c_can = st.columns(2)
                with c_acc:
                    if st.button("✅ Aceptar", key=f"btn_mant_ok_{hab_sel}"):
                        hab['estado'] = 'Mantenimiento'
                        hab['obs'] = f"🔧 {obs_mantenimiento}" if obs_mantenimiento else "🔧 En mantenimiento"
                        if DB_AVAILABLE:
                            db_upsert("habitaciones", hab, pk_column="numero")
                        st.session_state.show_success = "Habitación en mantenimiento"
                        st.rerun()
                with c_can:
                    if st.button("❌ Cancelar", key=f"btn_mant_cancel_{hab_sel}"):
                        st.session_state.temp_estado = None
                        st.session_state.temp_hab = None
                        st.rerun()
                st.stop()
        
        # Bloqueo de reservadas
        if hab['estado'] == 'Reservada':
            st.warning("⚠️ Esta habitación está reservada")
            c1, c2, c3 = st.columns(3)
            if c1.button("BORRAR", key=f"btn_borrar_{hab_sel}"):
                hab['estado'] = 'Disponible'
                hab['reserva'] = None
                hab['obs'] = ''
                if DB_AVAILABLE:
                    db_upsert("habitaciones", hab, pk_column="numero")
                st.session_state.show_success = "Reserva eliminada correctamente"
                st.rerun()
            if c2.button("CAMBIAR DE ESTADO", key=f"btn_cambiar_{hab_sel}"):
                hab['estado'] = st.selectbox("Nuevo estado", ESTADOS, index=0, key=f"estado_{hab_sel}")
                if DB_AVAILABLE:
                    db_upsert("habitaciones", hab, pk_column="numero")
                st.session_state.show_success = "Estado cambiado correctamente"
                st.rerun()
            if c3.button("VOLVER", key=f"btn_volver_{hab_sel}"):
                pass
            st.stop()
        
        # Cambio de estado manual
        if hab['estado'] != 'Reservada':
            nuevo = st.selectbox("Estado", ESTADOS, index=ESTADOS.index(hab['estado']), key=f"estado_sel_{hab_sel}")
            if nuevo == 'Mantenimiento' and hab['estado'] != 'Mantenimiento':
                if st.button("Configurar Mantenimiento", key=f"btn_prep_mant_{hab_sel}"):
                    st.session_state.temp_estado = 'Mantenimiento'
                    st.session_state.temp_hab = hab_sel
                    st.rerun()
            elif st.button("Aplicar Estado", key=f"btn_aplicar_{hab_sel}"):
                hab['estado'] = nuevo
                if nuevo != 'Mantenimiento':
                    hab['obs'] = ''
                if DB_AVAILABLE:
                    db_upsert("habitaciones", hab, pk_column="numero")
                st.session_state.show_success = f"Estado cambiado a {nuevo}"
                st.rerun()
        
        # Grid visual
        st.markdown("---")
        st.subheader("Todas las Habitaciones")
        cols_grid = st.columns(5)
        
        for i, (n, h) in enumerate(sorted(st.session_state.habitaciones.items())):
            with cols_grid[i%5]:
                content = f"<div style='background:{COLORES[h['estado']]};padding:15px;border-radius:8px;text-align:center;color:white;font-weight:bold;margin:5px 0;min-height:120px;display:flex;flex-direction:column;justify-content:center;align-items:center;'>"
                content += f"<div style='font-size:18px'>{n}</div>"
                content += f"<small>{h['tipo']}</small>"
                content += f"<div style='margin-top:5px'>{h['estado']}</div>"
                if h.get('obs'):
                    content += f"<div style='margin-top:5px;font-size:11px;background:rgba(255,255,255,0.3);padding:3px;border-radius:3px;max-width:100%;word-wrap:break-word'>{h['obs']}</div>"
                if n in PRIVADAS and h['estado'] == 'Ocupada' and h.get('inicio'):
                    ahora = datetime.now()
                    inicio = h['inicio']
                    if isinstance(inicio, str): inicio = datetime.fromisoformat(inicio)
                    diff = ahora - inicio
                    horas, resto = divmod(int(diff.total_seconds()), 3600)
                    minutos, segundos = divmod(resto, 60)
                    tipo_pago_guardado = h.get('tipo_pago_priv', '3 horas')
                    horas_extra_guardadas = h.get('horas_extra_priv', 0)
                    penalizaciones = h.get('penalizaciones', 0)
                    costo, dur = calc_privada_cost(inicio, ahora, tipo_pago_guardado, horas_extra_guardadas)
                    costo_con_penalizaciones = costo + (penalizaciones * 150)
                    extra_text = f" +{horas_extra_guardadas}h" if horas_extra_guardadas > 0 else ""
                    pen_text = f" ⚠️×{penalizaciones}" if penalizaciones > 0 else ""
                    content += f"<div style='margin-top:8px;background:rgba(0,0,0,0.3);padding:5px;border-radius:5px;font-size:11px'>⏱️ {horas}h {minutos}m {segundos}s{extra_text}{pen_text}<br>💰 L {costo_con_penalizaciones}</div>"
                content += "</div>"
                st.markdown(content, unsafe_allow_html=True)

    # ================= CLIENTES =================
    elif st.session_state.page == "Clientes":
        st.title("👥 Registro de Clientes")
        
        if st.session_state.show_success:
            st.success(st.session_state.show_success)
            st.session_state.show_success = ""
        
        tipo = st.radio("Tipo", ["🔒 Privada", "🛏️ Habitación"], horizontal=True, key="tipo_cliente")
        
        if tipo == "🔒 Privada":
            st.subheader("Registro de Privada")
            privadas_disp = [p for p in PRIVADAS if st.session_state.habitaciones[p]['estado'] == 'Disponible']
            
            c1, c2 = st.columns(2)
            with c1:
                fecha = st.date_input("Fecha de ingreso", datetime.now(), key=f"priv_fecha_{st.session_state.form_counter_priv}")
                hora = st.time_input("Hora de ingreso", datetime.now().time(), key=f"priv_hora_{st.session_state.form_counter_priv}")
                priv_sel = st.selectbox("Habitación", privadas_disp if privadas_disp else ["No disponibles"], key=f"priv_sel_{st.session_state.form_counter_priv}")
                tipo_pago = st.radio("Duración", ["3 horas", "1 noche"], horizontal=True, key=f"priv_tipo_{st.session_state.form_counter_priv}")
                
                horas_extra = 0
                if tipo_pago == "3 horas":
                    with st.expander("⏱️ ¿Desea horas adicionales? (+L 150/hora)", expanded=False):
                        horas_extra = st.number_input("Horas adicionales", min_value=0, max_value=10, value=0, step=1, key=f"horas_extra_{st.session_state.form_counter_priv}")
                        costo_extra = horas_extra * 150
                        if horas_extra > 0:
                            st.info(f"💰 Costo adicional: L {costo_extra}")
                        col_acc, col_can = st.columns(2)
                        with col_acc:
                            if st.button("✅ Aceptar horas extra", key=f"btn_aceptar_extra_{st.session_state.form_counter_priv}"):
                                st.session_state[f"horas_extra_confirmadas_{st.session_state.form_counter_priv}"] = horas_extra
                                st.rerun()
                        with col_can:
                            if st.button("❌ Cancelar", key=f"btn_cancelar_extra_{st.session_state.form_counter_priv}"):
                                st.session_state[f"horas_extra_confirmadas_{st.session_state.form_counter_priv}"] = 0
                                st.rerun()
                
                horas_extra_confirmadas = st.session_state.get(f"horas_extra_confirmadas_{st.session_state.form_counter_priv}", 0)
                monto_base = 400 if tipo_pago == "3 horas" else 800
                monto = monto_base + (horas_extra_confirmadas * 150)
                st.metric("💰 Monto a pagar", f"L {monto}")
                pago = st.selectbox("Método de pago", ["Efectivo", "Tarjeta", "Transferencia"], key=f"priv_pago_{st.session_state.form_counter_priv}")
                
            with c2:
                st.info("ℹ️ No se requieren datos personales para privadas")
                if st.button("Ocupar Privada", type="primary", key="btn_ocupar_priv"):
                    if priv_sel != "No disponibles":
                        inicio = datetime.combine(fecha, hora)
                        registro = {
                            'ID': len(st.session_state.historial_priv) + 1,
                            'HABITACION': priv_sel,
                            'FECHA_INGRESO': inicio.isoformat(),
                            'MONTO': monto,
                            'FACTURACION': f'{tipo_pago} +{horas_extra_confirmadas}h extra - {pago}' if horas_extra_confirmadas > 0 else f'{tipo_pago} - {pago}'
                        }
                        st.session_state.historial_priv.append(registro)
                        
                        st.session_state.habitaciones[priv_sel].update({
                            'estado': 'Ocupada', 'inicio': inicio.isoformat(),
                            'obs': f'{tipo_pago} +{horas_extra_confirmadas}h - L {monto}' if horas_extra_confirmadas > 0 else f'{tipo_pago} - L {monto}',
                            'tipo_pago_priv': tipo_pago, 'horas_extra_priv': horas_extra_confirmadas, 'penalizaciones': 0
                        })
                        
                        # Guardar en Supabase
                        if DB_AVAILABLE:
                            db_upsert("habitaciones", st.session_state.habitaciones[priv_sel], pk_column="numero")
                            db_insert_historial("PRIVADA", registro)
                        
                        st.session_state.show_success = "Ya se realizó el pago"
                        st.session_state.form_counter_priv += 1
                        if f"horas_extra_confirmadas_{st.session_state.form_counter_priv}" in st.session_state:
                            del st.session_state[f"horas_extra_confirmadas_{st.session_state.form_counter_priv}"]
                        st.rerun()
                    else:
                        st.error("❌ No hay privadas disponibles")
        else:
            # CLIENTE - HABITACIÓN
            st.subheader("Registro de Habitación")
            uploaded = st.file_uploader("📂 Cargar empresas (Excel/CSV)", type=['xlsx', 'csv'], key="upload_empresas")
            if uploaded:
                try:
                    df_emp = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
                    for _, row in df_emp.iterrows():
                        if 'EMPRESA' in row.columns and 'RTN' in row.columns:
                            st.session_state.empresas[row['EMPRESA']] = str(row['RTN'])
                            if DB_AVAILABLE:
                                db_upsert("empresas", {"nombre": row['EMPRESA'], "rtn": str(row['RTN'])}, pk_column="nombre")
                    st.success(f"✅ {len(df_emp)} empresas cargadas correctamente.")
                except Exception as e:
                    st.error(f"Error al cargar archivo: {e}")
            
            st.markdown("---")
            st.subheader(" Agregar Nueva Empresa")
            col_emp1, col_emp2, col_emp3 = st.columns([2, 2, 1])
            with col_emp1:
                nueva_empresa = st.text_input("Nombre de Empresa", key="nueva_empresa_input")
            with col_emp2:
                nuevo_rtn = st.text_input("RTN", key="nuevo_rtn_input")
            with col_emp3:
                if st.button("Agregar", key="btn_agregar_empresa"):
                    if nueva_empresa and nuevo_rtn:
                        st.session_state.empresas[nueva_empresa] = nuevo_rtn
                        if DB_AVAILABLE:
                            db_upsert("empresas", {"nombre": nueva_empresa, "rtn": nuevo_rtn}, pk_column="nombre")
                        st.success("✅ Empresa agregada")
                        st.rerun()
            
            st.markdown("---")
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nombre", key=f"hab_nom_{st.session_state.form_counter_hab}")
                ape = st.text_input("Apellido", key=f"hab_ape_{st.session_state.form_counter_hab}")
                dni = st.text_input("DNI", key=f"hab_dni_{st.session_state.form_counter_hab}")
                tel = st.text_input("Teléfono", key=f"hab_tel_{st.session_state.form_counter_hab}")
                proc = st.text_input("Procedencia", key=f"hab_proc_{st.session_state.form_counter_hab}")
            with c2:
                emp_opts = list(st.session_state.empresas.keys())
                emp_sel = st.selectbox("Empresa", [""] + emp_opts, key=f"hab_empresa_sel_{st.session_state.form_counter_hab}")
                rtn_default = st.session_state.empresas.get(emp_sel, "") if emp_sel else ""
                rtn = st.text_input("RTN", value=rtn_default, key=f"hab_rtn_{emp_sel if emp_sel else 'manual'}_{st.session_state.form_counter_hab}")
                if emp_sel and rtn and rtn != rtn_default:
                    if st.button("Agregar esta empresa", key=f"btn_agr_emp_{emp_sel}_{st.session_state.form_counter_hab}"):
                        st.session_state.empresas[emp_sel] = rtn
                        if DB_AVAILABLE:
                            db_upsert("empresas", {"nombre": emp_sel, "rtn": rtn}, pk_column="nombre")
                        st.success("✅ Empresa agregada al registro")
                        st.rerun()
                
                habs_disp = [h for h, d in st.session_state.habitaciones.items() if d['estado'] == 'Disponible' and h not in PRIVADAS]
                hab_sel = st.selectbox("Habitación", habs_disp if habs_disp else ["No disponibles"], key=f"hab_sel_cliente_{st.session_state.form_counter_hab}")
                pago = st.selectbox("Método de pago", ["Efectivo", "Tarjeta", "Transferencia"], key=f"hab_pago_{st.session_state.form_counter_hab}")
            
            fact = "Con facturación" if (emp_sel and rtn) else "Sin facturación"
            st.caption(f"📄 Facturación: {fact}")
            
            c3, c4 = st.columns(2)
            with c3:
                f_ing = st.date_input("Fecha ingreso", datetime.now(), key=f"hab_f_ing_{st.session_state.form_counter_hab}")
                h_ing = st.time_input("Hora ingreso", datetime.now().time(), key=f"hab_h_ing_{st.session_state.form_counter_hab}")
            with c4:
                checkout_def = get_next_checkout(f_ing, h_ing)
                f_sal = st.date_input("Fecha salida", checkout_def.date(), key=f"hab_f_sal_{st.session_state.form_counter_hab}")
                dias = max(1, (f_sal - f_ing).days + (1 if checkout_def.date() != f_sal else 0))
                st.info(f"📅 Duración: {dias} día(s)\n⏰ Salida esperada: {checkout_def.strftime('%d/%m %H:%M')}")
            
            if hab_sel != "No disponibles":
                tipo_h = st.session_state.habitaciones[hab_sel]['tipo']
                monto = calc_hab_cost(tipo_h, fact, dias)
                st.metric("💰 Total a pagar", f"L {monto}")
                
                if st.button("Registrar Cliente y Facturar", type="primary", key="btn_registrar_hab"):
                    if nom and ape and dni:
                        fecha_ing_completa = datetime.combine(f_ing, h_ing)
                        cl = {
                            'ID': len(st.session_state.historial_hab) + 1, 'NOMBRE': nom, 'APELLIDO': ape, 'DNI': dni,
                            'TELEFONO': tel, 'PROCEDENCIA': proc, 'EMPRESA': emp_sel, 'RTN': rtn,
                            'FACTURACION': fact, 'MONTO': monto, 'METODO_PAGO': pago,
                            'FECHA_INGRESO': fecha_ing_completa.isoformat(), 'FECHA_SALIDA_ESP': checkout_def.isoformat(), 'DIAS': dias
                        }
                        registro = {
                            'ID': cl['ID'], 'NOMBRE_Y_APELLIDO': f"{nom} {ape}", 'TELEFONO': tel, 'PROCEDENCIA': proc,
                            'NOMBRE_EMPRESA': emp_sel, 'RTN': rtn, 'FACTURACION': fact, 'HABITACION': hab_sel,
                            'METODO_PAGO': pago, 'MONTO': monto, 'FECHA_INGRESO': fecha_ing_completa.isoformat()
                        }
                        st.session_state.historial_hab.append(registro)
                        st.session_state.habitaciones[hab_sel].update({'estado': 'Ocupada', 'cliente': cl, 'obs': f"{dias} día(s) - {nom} {ape}"})
                        
                        if DB_AVAILABLE:
                            db_upsert("habitaciones", st.session_state.habitaciones[hab_sel], pk_column="numero")
                            db_insert_historial("HABITACION", registro)
                        
                        st.session_state.show_success = "Ya se realizó el pago"
                        st.session_state.form_counter_hab += 1
                        st.rerun()
                    else:
                        st.error("❌ Complete los campos obligatorios (Nombre, Apellido, DNI)")

    # ================= RESERVAS =================
    elif st.session_state.page == "Reservas":
        st.title("📅 Reservas")
        if st.session_state.show_success:
            st.success(st.session_state.show_success)
            st.session_state.show_success = ""
        
        mod = st.radio("Modalidad", ["Básica", "Pago Anticipado"], horizontal=True, key="res_modalidad")
        nom = st.text_input("Nombre", key=f"res_nom_{st.session_state.form_counter_res_basica if mod == 'Básica' else st.session_state.form_counter_res_pa}")
        ape = st.text_input("Apellido", key=f"res_ape_{st.session_state.form_counter_res_basica if mod == 'Básica' else st.session_state.form_counter_res_pa}")
        habs_disp = [h for h, d in st.session_state.habitaciones.items() if d['estado'] == 'Disponible' and h not in PRIVADAS]
        hab_sel = st.selectbox("Habitación", habs_disp if habs_disp else ["No disponibles"], key=f"res_hab_sel_{st.session_state.form_counter_res_basica if mod == 'Básica' else st.session_state.form_counter_res_pa}")
        f_res = st.date_input("Fecha reserva", datetime.now(), key=f"res_fecha_{st.session_state.form_counter_res_basica if mod == 'Básica' else st.session_state.form_counter_res_pa}")
        al_llegar = st.checkbox("Al llegar", key=f"res_al_llegar_{st.session_state.form_counter_res_basica if mod == 'Básica' else st.session_state.form_counter_res_pa}")
        dias_reserva = 0 if al_llegar else st.number_input("Días de reserva", min_value=1, value=1, key=f"res_dias_{st.session_state.form_counter_res_basica if mod == 'Básica' else st.session_state.form_counter_res_pa}")
        
        if mod == "Pago Anticipado":
            st.markdown("---")
            st.subheader("Datos para Pago Anticipado")
            c1, c2 = st.columns(2)
            with c1:
                dni = st.text_input("DNI", key=f"respa_dni_{st.session_state.form_counter_res_pa}")
                tel = st.text_input("Teléfono", key=f"respa_tel_{st.session_state.form_counter_res_pa}")
                proc = st.text_input("Procedencia", key=f"respa_proc_{st.session_state.form_counter_res_pa}")
            with c2:
                emp_opts = list(st.session_state.empresas.keys())
                emp_sel = st.selectbox("Empresa", [""] + emp_opts, key=f"respa_empresa_{st.session_state.form_counter_res_pa}")
                rtn_default = st.session_state.empresas.get(emp_sel, "") if emp_sel else ""
                rtn = st.text_input("RTN", value=rtn_default, key=f"respa_rtn_{emp_sel if emp_sel else 'manual'}_{st.session_state.form_counter_res_pa}")
                pago = st.selectbox("Método de pago", ["Efectivo", "Tarjeta", "Transferencia"], key=f"respa_pago_{st.session_state.form_counter_res_pa}")
            
            fact = "Con facturación" if (emp_sel and rtn) else "Sin facturación"
            st.caption(f"📄 Facturación: {fact}")
            
            if hab_sel != "No disponibles":
                f_inicio = st.date_input("Inicio reserva", f_res, key=f"respa_f_inicio_{st.session_state.form_counter_res_pa}")
                dias_estadia = st.number_input("Días de estadía", min_value=1, value=1, key=f"respa_dias_estadia_{st.session_state.form_counter_res_pa}")
                tipo_h = st.session_state.habitaciones[hab_sel]['tipo']
                monto = calc_hab_cost(tipo_h, fact, dias_estadia)
                st.metric("💰 Total a pagar", f"L {monto}")
                
                if st.button("Confirmar Reserva", type="primary", key="btn_confirmar_reserva_pa"):
                    if nom and ape and dni:
                        metodo_pago_reserva = f"{pago}, Reservación"
                        cl = {
                            'ID': len(st.session_state.historial_hab) + 1, 'NOMBRE': nom, 'APELLIDO': ape, 'DNI': dni,
                            'TELEFONO': tel, 'PROCEDENCIA': proc, 'EMPRESA': emp_sel, 'RTN': rtn,
                            'FACTURACION': fact, 'MONTO': monto, 'METODO_PAGO': metodo_pago_reserva, 'DIAS': dias_estadia
                        }
                        registro = {
                            'ID': cl['ID'], 'NOMBRE_Y_APELLIDO': f"{nom} {ape}", 'TELEFONO': tel, 'PROCEDENCIA': proc,
                            'NOMBRE_EMPRESA': emp_sel, 'RTN': rtn, 'FACTURACION': fact, 'HABITACION': hab_sel,
                            'METODO_PAGO': metodo_pago_reserva, 'MONTO': monto,
                            'FECHA_INGRESO': f_inicio.isoformat() if isinstance(f_inicio, datetime) else str(f_inicio)
                        }
                        st.session_state.historial_hab.append(registro)
                        obs = f"Reservada {dias_reserva} días, estadía {dias_estadia} días - {nom} {ape} (Pago anticipado)"
                        st.session_state.habitaciones[hab_sel].update({
                            'estado': 'Reservada',
                            'reserva': {'NOMBRE': nom, 'APELLIDO': ape, 'FECHA': f_inicio.isoformat() if isinstance(f_inicio, datetime) else str(f_inicio), 'DIAS_RESERVA': dias_reserva, 'DIAS_ESTADIA': dias_estadia, 'PAGO_ANTICIPADO': True, 'METODO_PAGO': pago},
                            'cliente': cl, 'obs': obs
                        })
                        
                        if DB_AVAILABLE:
                            db_upsert("habitaciones", st.session_state.habitaciones[hab_sel], pk_column="numero")
                            db_insert_historial("HABITACION", registro)
                        
                        st.session_state.show_success = "Ya se realizó la reserva"
                        st.session_state.form_counter_res_pa += 1
                        st.rerun()
                    else:
                        st.error("❌ Complete los campos obligatorios")
        else:
            if st.button("Confirmar Reserva", type="primary", key="btn_confirmar_reserva_basica"):
                if nom and ape and hab_sel != "No disponibles":
                    obs = f"Reservada - Al llegar - {nom} {ape}" if al_llegar else f"Reservada {dias_reserva} días - {nom} {ape}"
                    st.session_state.habitaciones[hab_sel].update({
                        'estado': 'Reservada',
                        'reserva': {'NOMBRE': nom, 'APELLIDO': ape, 'FECHA': f_res.isoformat() if isinstance(f_res, datetime) else str(f_res), 'DIAS_RESERVA': dias_reserva, 'PAGO_ANTICIPADO': False},
                        'obs': obs
                    })
                    if DB_AVAILABLE:
                        db_upsert("habitaciones", st.session_state.habitaciones[hab_sel], pk_column="numero")
                    st.session_state.show_success = "Ya se realizó la reserva"
                    st.session_state.form_counter_res_basica += 1
                    st.rerun()
                else:
                    st.error("❌ Complete los campos obligatorios")

    # Footer
    st.markdown("---")
    st.markdown(f"""
    <div style='text-align: center; color: gray; font-size: 12px;'>
        © 2026 Sistema de Hotelería CA13 | 
        💾 {'Conectado a Supabase ✅' if DB_AVAILABLE else 'Modo local ⚠️'} |
        🔄 {datetime.now().strftime('%H:%M:%S')}
    </div>
    """, unsafe_allow_html=True)

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================
if __name__ == "__main__":
    init_session_state()
    if not st.session_state.authenticated:
        login_screen()
    else:
        main_app()
