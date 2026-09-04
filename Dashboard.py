from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import os
from conexion_drive import descargar_excel_drive

st.set_page_config(
    page_title="Dashboard Servicio Técnico Medellín",
    page_icon="📊",
    layout="wide"
)

BASE_DIR = Path(__file__).parent
LOGO_PATH = BASE_DIR / "Logo.jpg"
PRESUPUESTO_PATH = BASE_DIR / "PLANTILLA PRESUPUESTO VENTAS ST 2026.xlsx"

# Configuración Google Drive para Excel Base
DRIVE_FILE_ID = os.environ.get("DRIVE_FILE_ID", "1ubI7JOJ4Qj8eghNEk8zZmHr8sg8we5EjAQkgTsyItzc")
DRIVE_CREDENTIALS_PATH = BASE_DIR / "service-account.json"

MESES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width='stretch')
        
    opcion_menu = st.radio(
        "Menú Principal",
        options=["Fallas", "Gerencia", "Presupuesto"],
        index=0,
        help="Selecciona el módulo que deseas visualizar"
    )
    st.divider()


def normalizar_texto(col):
    return (
        col.astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r'GARANTA', 'GARANTÍA', regex=True)
        .str.replace(r'MANTENIMIETO', 'MANTENIMIENTO', regex=True)
        .str.replace(r'\s+', ' ', regex=True)
    )


#@st.cache_data
def cargar_datos(archivo_excel):
    """Lee TABLA_FALLAS, separa categorías múltiples y normaliza texto."""
    if isinstance(archivo_excel, Path) and not archivo_excel.exists():
        return None, 0

    df = pd.read_excel(archivo_excel, sheet_name="TABLA_MADRE", header=1)
    df.columns = df.columns.str.strip()
    df["RECORD_ID"] = df.index

    total_original = df["OTT"].nunique() if "OTT" in df.columns else len(df)

    # Una OTT puede tener varias categorías separadas por ";" -> una fila por categoría
    if "CATEGORIA" in df.columns:
        df["CATEGORIA"] = df["CATEGORIA"].astype(str).str.split(";")
        df = df.explode("CATEGORIA")

    for col in ["EQUIPO", "MODELO", "FALLA_ESTANDARIZADA", "CATEGORIA", "MES", "DESCRIPCION", "TIPO_SERVICIO"]:
        if col in df.columns:
            df[col] = normalizar_texto(df[col])

    if "f" in df.columns:
        df.rename(columns={"f": "AÑO"}, inplace=True)

    return df, total_original


#@st.cache_data
def extraer_repuestos_codigos(df: pd.DataFrame) -> pd.DataFrame:
    #"""REPUESTOS y CODIGO vienen separados por ';' y emparejados por posición."""
    if df.empty or "REPUESTOS" not in df.columns or "CODIGO" not in df.columns:
        return pd.DataFrame(columns=["EQUIPO", "CODIGO", "REPUESTO", "OTT"])

    filas = []
    for _, fila in df.iterrows():
        reps = [r.strip().upper() for r in str(fila.get("REPUESTOS", "")).split(";")
                if r.strip() and r.strip().upper() != "NAN"]
        cods = [c.strip().upper() for c in str(fila.get("CODIGO", "")).split(";")
                if c.strip() and c.strip().upper() != "NAN"]

        for i in range(max(len(reps), len(cods))):
            filas.append({
                "EQUIPO": fila.get("EQUIPO", "SIN EQUIPO"),
                "CODIGO": cods[i] if i < len(cods) else "SIN CÓDIGO",
                "REPUESTO": reps[i] if i < len(reps) else "SIN ESPECIFICAR",
                "OTT": fila.get("OTT", None),
            })

    return pd.DataFrame(filas)

#@st.cache_data
def cargar_datos_presupuesto(ruta_ppto: Path, archivo_facturacion):
    if not ruta_ppto.exists() or archivo_facturacion is None:
        return None, None

    df_ppto_raw = pd.read_excel(ruta_ppto, sheet_name="SERVICIO TECNICO", header=None)
    fila_medellin = df_ppto_raw.iloc[16]  # Fila 17 de Excel = "T. DPTO. TÉCNICO MEDELLIN"
    ppto_mensual = {
        mes: float(fila_medellin.iloc[i]) if pd.notna(fila_medellin.iloc[i]) else 0.0
        for i, mes in enumerate(MESES, start=2)
    }

    df_fact = pd.read_excel(archivo_facturacion, sheet_name="2026-")
    df_fact.columns = df_fact.columns.str.strip()
    df_fact["FECHA"] = pd.to_datetime(df_fact["FECHA"], errors="coerce")

    return ppto_mensual, df_fact

# FILTROS 

def filtro_multiselect(df: pd.DataFrame, columna: str, etiqueta: str, key: str) -> pd.DataFrame:
    """Filtro genérico: opciones ordenadas alfabéticamente."""
    if columna not in df.columns:
        return df
    opciones = sorted(df[columna].dropna().unique())
    seleccion = st.multiselect(etiqueta, opciones, default=opciones, key=key)
    return df[df[columna].isin(seleccion)]


def filtro_mes(df: pd.DataFrame, key: str) -> pd.DataFrame:
    if "MES" not in df.columns:
        return df
    disponibles = [m for m in MESES if m in df["MES"].unique()]
    seleccion = st.multiselect("Mes", disponibles, default=disponibles, key=key)
    return df[df["MES"].isin(seleccion)]

# GRÁFICOS 
def grafico_pie(df: pd.DataFrame, columna: str, titulo: str, paleta) -> px.pie:
    conteo = df[columna].value_counts().reset_index()
    return px.pie(conteo, names=columna, values="count", title=titulo, hole=0.4, color_discrete_sequence=paleta)


def grafico_barras_conteo(df: pd.DataFrame, columna: str, titulo: str, paleta, etiqueta_x=None) -> px.bar:
    conteo = df[columna].value_counts().reset_index()
    return px.bar(conteo, x=columna, y="count", title=titulo, labels={columna: etiqueta_x or columna, "count": "Cantidad"},
                  color_discrete_sequence=paleta)


def grafico_barras_agrupadas(df: pd.DataFrame, x: str, color: str, titulo: str, paleta) -> px.bar:
    agrupado = df.groupby([x, color]).size().reset_index(name="Cantidad OTTs")
    fig = px.bar(agrupado, x=x, y="Cantidad OTTs", color=color, title=titulo, barmode="group", text="Cantidad OTTs", labels={x: x.title(), "Cantidad OTTs": "Ingresos Únicos (OTTs)"},
                 color_discrete_sequence=paleta)
    fig.update_traces(textposition="outside")
    return fig

# MÓDULO 1: FALLAS

if opcion_menu == "Fallas":
    try:
        excel_bytes = descargar_excel_drive(DRIVE_FILE_ID, str(DRIVE_CREDENTIALS_PATH))
        df_fallas, total_fallas_original = cargar_datos(io.BytesIO(excel_bytes))
    except Exception as e:
        st.error(f"Error al descargar la base de datos de Google Drive: {e}")
        st.stop()

    if df_fallas is None:
        st.error("No se pudo cargar la base de datos.")
        st.stop()

    with st.sidebar:
        st.subheader("Filtros de Análisis")
        df_filtrado = filtro_multiselect(df_fallas, "AÑO", "Año", key="f_anio")
        df_filtrado = filtro_mes(df_filtrado, key="f_mes")
        df_filtrado = filtro_multiselect(df_filtrado, "EQUIPO", "Equipo", key="f_equipo")
        df_filtrado = filtro_multiselect(df_filtrado, "MODELO", "Modelo", key="f_modelo")
        df_filtrado = filtro_multiselect(df_filtrado, "FALLA_ESTANDARIZADA", "Falla", key="f_falla")

    total_filtrados = df_filtrado["OTT"].nunique() if "OTT" in df_filtrado.columns else df_filtrado["RECORD_ID"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Fallas (OTTs)", total_filtrados, delta=f"de {total_fallas_original} OTTs totales")
    c2.metric("Modelos", df_filtrado["MODELO"].nunique() if "MODELO" in df_filtrado.columns else 0)
    c3.metric("Categorías", df_filtrado["CATEGORIA"].nunique() if "CATEGORIA" in df_filtrado.columns else 0)
    c4.metric("Tipos de Falla", df_filtrado["FALLA_ESTANDARIZADA"].nunique() if "FALLA_ESTANDARIZADA" in df_filtrado.columns else 0)

    st.divider()

    if not df_filtrado.empty:
        col1, col2 = st.columns(2)
        col1.plotly_chart(
            grafico_barras_conteo(df_filtrado, "FALLA_ESTANDARIZADA", "Fallas más frecuentes", px.colors.qualitative.Set2, "Falla Estandarizada"),
            width='stretch')
        col2.plotly_chart(
            grafico_barras_conteo(df_filtrado, "CAUSA_RAIZ", "Causas de las fallas más frecuentes",px.colors.qualitative.Pastel, "Causa Raíz"),
            width='stretch')
        st.plotly_chart(
            grafico_pie(df_filtrado, "CATEGORIA", "Distribución por Categoría", px.colors.qualitative.Pastel2),
            width='stretch')
    else:
        st.warning("No hay datos disponibles para los filtros seleccionados.")

    st.subheader("Datos Detallados")
    st.dataframe(df_filtrado.drop(columns=["RECORD_ID"], errors="ignore"), width='stretch')


# MÓDULO 2: GERENCIA

elif opcion_menu == "Gerencia":
    try:
        excel_bytes = descargar_excel_drive(DRIVE_FILE_ID, str(DRIVE_CREDENTIALS_PATH))
        df_fallas, total_fallas_original = cargar_datos(io.BytesIO(excel_bytes))
    except Exception as e:
        st.error(f"Error al descargar la base de datos de Google Drive: {e}")
        st.stop()

    if df_fallas is None:
        st.error("No se pudo cargar la base de datos.")
        st.stop()

    with st.sidebar:
        st.subheader("Filtros Gerenciales")
        df_gerencia = filtro_multiselect(df_fallas, "AÑO", "Año", key="g_anio")
        df_gerencia = filtro_mes(df_gerencia, key="g_mes")
        df_gerencia = filtro_multiselect(df_gerencia, "EQUIPO", "Equipo", key="g_equipo")
        df_gerencia = filtro_multiselect(df_gerencia, "TIPO_SERVICIO", "Tipo de Servicio", key="g_tiposervicio")
        df_gerencia = filtro_multiselect(df_gerencia, "DESCRIPCION", "Descripción", key="g_descripcion")

    #deduplicar
    df_gerencia_unicas = df_gerencia.drop_duplicates(subset=["OTT"]) if "OTT" in df_gerencia.columns else df_gerencia


    total_servicios = len(df_gerencia_unicas)
    total_preventivo = df_gerencia_unicas["TIPO_SERVICIO"].str.contains("PREVENTIVO", na=False).sum() if "TIPO_SERVICIO" in df_gerencia_unicas.columns else 0
    total_garantia = df_gerencia_unicas["DESCRIPCION"].str.contains("GARANTÍA|GARANTIA", na=False).sum() if "DESCRIPCION" in df_gerencia_unicas.columns else 0
    pct_preventivo = round(total_preventivo / total_servicios * 100, 1) if total_servicios else 0
    pct_garantia = round(total_garantia / total_servicios * 100, 1) if total_servicios else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Ingresos (OTTs)", total_servicios)
    c2.metric("% Mant. Preventivo", f"{pct_preventivo}%", delta=f"{total_preventivo} OTTs")
    c3.metric("% En Garantía", f"{pct_garantia}%", delta=f"{total_garantia} OTTs")
    c4.metric("Tipos de Equipos", df_gerencia_unicas["EQUIPO"].nunique() if "EQUIPO" in df_gerencia_unicas.columns else 0)

    st.divider()

    if not df_gerencia_unicas.empty:
        col1, col2 = st.columns(2)
        col1.plotly_chart(
            grafico_pie(df_gerencia_unicas, "TIPO_SERVICIO", "Distribución por Tipo de Servicio", px.colors.qualitative.Set2),
            width='stretch')
        col2.plotly_chart(
            grafico_pie(df_gerencia_unicas, "DESCRIPCION", "Distribución por Descripción (Garantía / Particular)", px.colors.qualitative.Pastel),
            width='stretch')

        st.subheader("Análisis por Equipo")
        col_eq1, col_eq2 = st.columns(2)
        if "EQUIPO" in df_gerencia_unicas.columns and "TIPO_SERVICIO" in df_gerencia_unicas.columns:
            col_eq1.plotly_chart(
                grafico_barras_agrupadas(df_gerencia_unicas, "EQUIPO", "TIPO_SERVICIO","Tipo de Servicio según el Equipo (OTTs Únicas)", px.colors.qualitative.Set2),
                width='stretch')
        if "EQUIPO" in df_gerencia_unicas.columns and "DESCRIPCION" in df_gerencia_unicas.columns:
            col_eq2.plotly_chart(
                grafico_barras_agrupadas(df_gerencia_unicas, "EQUIPO", "DESCRIPCION", "Descripción (Garantía / Particular) según el Equipo (OTTs Únicas)", px.colors.qualitative.Pastel),
                width='stretch')

        st.divider()
        st.subheader(" Repuestos Utilizados por Equipo ")

        df_rep_cod = extraer_repuestos_codigos(df_gerencia_unicas)
        if not df_rep_cod.empty:
            df_grouped_rep = df_rep_cod.groupby(["EQUIPO", "REPUESTO", "CODIGO"]).size().reset_index(name="CANTIDAD")
            lista_equipos = sorted(df_grouped_rep["EQUIPO"].unique())
            cols_equipos = st.columns(len(lista_equipos)) if lista_equipos else [st.container()]
            paleta_pastel = px.colors.qualitative.Set2 + px.colors.qualitative.Pastel + px.colors.qualitative.Pastel2

            for idx, equipo_nombre in enumerate(lista_equipos):
                df_sub = df_grouped_rep[df_grouped_rep["EQUIPO"] == equipo_nombre].sort_values("CANTIDAD", ascending=False)
                with cols_equipos[idx % len(cols_equipos)]:
                    fig_sub = px.bar(
                        df_sub, x="REPUESTO", y="CANTIDAD", color="REPUESTO",
                        hover_data={"CODIGO": True, "REPUESTO": True, "CANTIDAD": True},
                        title=f"Repuestos: {equipo_nombre}", text="CANTIDAD",
                        labels={"REPUESTO": "Repuesto", "CANTIDAD": "Cantidad", "CODIGO": "Código de Repuesto"},
                        color_discrete_sequence=paleta_pastel
                    )
                    fig_sub.update_traces(
                        textposition="outside",
                        hovertemplate="<b>Repuesto:</b> %{x}<br><b>Código:</b> %{customdata[0]}<br><b>Cantidad:</b> %{y}<extra></extra>"
                    )
                    fig_sub.update_layout(showlegend=False, xaxis_title=None, yaxis_title="Cantidad", margin=dict(l=20, r=20, t=50, b=50))
                    st.plotly_chart(fig_sub, width='stretch')
        else:
            st.info("No se encontraron registros de repuestos para los filtros seleccionados.")

        st.divider()
    else:
        st.warning("No hay datos disponibles para los filtros seleccionados.")

    st.subheader("Registros de OTTs Únicas")
    st.dataframe(df_gerencia_unicas.drop(columns=["RECORD_ID"], errors="ignore"), width='stretch')


# MÓDULO 3: PRESUPUESTO 
elif opcion_menu == "Presupuesto":
    st.info("Para visualizar este módulo, por favor sube el archivo Excel de Facturación.")
    archivo_facturacion = st.file_uploader("Cargar Excel de Facturación", type=["xlsx", "xls"])
    
    if archivo_facturacion is None:
        st.warning("El módulo de Presupuesto requiere el archivo de facturación.")
        st.stop()

    ppto_mensual, df_fact = cargar_datos_presupuesto(PRESUPUESTO_PATH, archivo_facturacion)
    if ppto_mensual is None or df_fact is None:
        st.error("No se pudieron cargar los archivos de presupuesto o facturación.")
        st.stop()

    df_fact_2026 = df_fact[df_fact["FECHA"].dt.year == 2026].copy()
    df_fact_2026["MES_NUM"] = df_fact_2026["FECHA"].dt.month
    fact_por_mes = df_fact_2026.groupby("MES_NUM")["VALOR ANTES DE IVA"].sum()

    filas = []
    for num_mes, mes in enumerate(MESES, start=1):
        ppto = ppto_mensual.get(mes, 0.0)
        facturado = fact_por_mes.get(num_mes, 0.0)
        evaluado = facturado > 0
        estado = "PENDIENTE" if not evaluado else ("CUMPLIÓ" if facturado >= ppto else "NO CUMPLIÓ")
        filas.append({
            "MES_NUM": num_mes, "MES": mes, "PRESUPUESTO": ppto, "FACTURADO": facturado,
            "DIFERENCIA": (facturado - ppto) if evaluado else 0.0,
            "% CUMPLIMIENTO": (facturado / ppto * 100) if (ppto > 0 and evaluado) else 0.0,
            "ESTADO": estado, "EVALUADO": evaluado,
        })
    df_comparativa = pd.DataFrame(filas)

    with st.sidebar:
        st.subheader("Filtros de Presupuesto")
        meses_sel = st.multiselect("Seleccionar Meses", MESES, default=MESES)
    df_comp = df_comparativa[df_comparativa["MES"].isin(meses_sel)]

    total_ppto = df_comp["PRESUPUESTO"].sum()
    total_fact = df_comp["FACTURADO"].sum()
    evaluados = df_comp[df_comp["EVALUADO"]]
    cumplidos = (evaluados["FACTURADO"] >= evaluados["PRESUPUESTO"]).sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Presupuesto Total", f"${total_ppto:,.0f}")
    c2.metric("Facturación Total", f"${total_fact:,.0f}", delta=f"${total_fact - total_ppto:,.0f}")
    c3.metric("% Cumplimiento Global", f"{(total_fact / total_ppto * 100) if total_ppto else 0:.1f}%")
    c4.metric("Meses Cumplidos", f"{cumplidos} / {len(evaluados)}")

    st.divider()

    if not df_comp.empty:
        col1, col2 = st.columns(2)

        with col1:
            fig_bar = go.Figure()
            fig_bar.add_bar(x=df_comp["MES"], y=df_comp["PRESUPUESTO"], name="Presupuesto Meta", marker_color="#94A3B8")
            colores_estado = {"CUMPLIÓ": "#22C55E", "NO CUMPLIÓ": "#EF4444", "PENDIENTE": "#94A3B8"}
            fig_bar.add_bar(x=df_comp["MES"], y=df_comp["FACTURADO"], name="Facturación Real",
                             marker_color=df_comp["ESTADO"].map(colores_estado))
            fig_bar.update_layout(title="Presupuesto Meta vs Facturación Real", barmode="group",
                                   xaxis_title="Mes", yaxis_title="Valor ($)",
                                   legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_bar, width='stretch')

        with col2:
            def color_pct(p):
                return "#22C55E" if p >= 100 else "#F59E0B" if p >= 80 else "#EF4444"

            fig_pct = go.Figure()
            fig_pct.add_bar(x=df_comp["MES"], y=df_comp["% CUMPLIMIENTO"], name="% Cumplimiento",
                             marker_color=df_comp["% CUMPLIMIENTO"].apply(color_pct),
                             text=df_comp["% CUMPLIMIENTO"].map(lambda p: f"{p:.1f}%"), textposition="outside")
            fig_pct.add_hline(y=100, line_dash="dash", line_color="#2563EB")
            fig_pct.update_layout(title="Porcentaje de Cumplimiento Mensual (Meta 100%)",
                                   xaxis_title="Mes", yaxis_title="% Cumplimiento",
                                   yaxis=dict(range=[0, max(df_comp["% CUMPLIMIENTO"].max() * 1.15, 120)]))
            st.plotly_chart(fig_pct, width='stretch')

    st.divider()

    st.subheader("Resumen Mensual de Presupuesto (Medellín)")
    df_tabla = df_comp.copy()
    df_tabla["PRESUPUESTO"] = df_tabla["PRESUPUESTO"].map(lambda x: f"${x:,.0f}")
    df_tabla["FACTURADO"] = df_tabla["FACTURADO"].map(lambda x: f"${x:,.0f}")
    df_tabla["DIFERENCIA"] = df_tabla["DIFERENCIA"].map(lambda x: f"${x:,.0f}")
    df_tabla["% CUMPLIMIENTO"] = df_tabla["% CUMPLIMIENTO"].map(lambda x: f"{x:.1f}%")
    st.dataframe(df_tabla[["MES", "PRESUPUESTO", "FACTURADO", "DIFERENCIA", "% CUMPLIMIENTO", "ESTADO"]], width='stretch')

    with st.expander("Facturación Medellín 2026"):
        st.dataframe(df_fact_2026, width='stretch')