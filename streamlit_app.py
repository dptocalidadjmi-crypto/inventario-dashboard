"""
Dashboard de inventario para Streamlit Community Cloud.
Lee directamente del export CSV de Google Sheets.

Configuracion (en Streamlit Cloud -> App settings -> Secrets):
    SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/<ID>/export?format=csv"
    LOW_STOCK_DEFAULT_THRESHOLD = "5"

Para pruebas locales tambien acepta variables de entorno con los mismos nombres.
"""

import csv
import io
import os
import re

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


def get_config(key: str, default: str = "") -> str:
    """Read from Streamlit secrets first, then environment variables."""
    try:
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.getenv(key, default)


CSV_URL           = get_config("SHEET_CSV_URL")
DEFAULT_THRESHOLD = float(get_config("LOW_STOCK_DEFAULT_THRESHOLD", "5"))

st.set_page_config(
    page_title="Inventario",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .metric-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        border-left: 5px solid #1565c0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .metric-card.alert { border-left-color: #c62828; }
    .metric-card.warn  { border-left-color: #f57c00; }
    .metric-label { color: #666; font-size: 13px; margin-bottom: 4px; }
    .metric-value { font-size: 32px; font-weight: 700; color: #1a237e; }
    .metric-value.red   { color: #c62828; }
    .metric-value.orange { color: #f57c00; }
    .section-title {
        font-size: 18px;
        font-weight: 600;
        color: #1a237e;
        margin-top: 8px;
        padding-bottom: 6px;
        border-bottom: 2px solid #e3f2fd;
    }
</style>
""", unsafe_allow_html=True)


# ── Parsing helpers ────────────────────────────────────────────────────────────

def is_category_header(row: list) -> bool:
    sku      = row[0].strip() if len(row) > 0 else ""
    entradas = row[2].strip() if len(row) > 2 else ""
    salidas  = row[3].strip() if len(row) > 3 else ""
    stock    = row[4].strip() if len(row) > 4 else ""

    numeric_empty = all(v in ("", "0", "0.0") for v in [entradas, salidas, stock])
    looks_like_product = bool(re.search(r"[\d\-]", sku)) or sku.upper().startswith("CONSUMO")

    return numeric_empty and not looks_like_product and sku != ""


def parse_float(val: str) -> float:
    val = val.strip()
    if "," in val and "." not in val:
        parts = val.split(",")
        if len(parts) == 2 and len(parts[1]) <= 2:
            val = val.replace(",", ".")
        else:
            val = val.replace(",", "")
    try:
        return float(val)
    except ValueError:
        return 0.0


def extract_category(sku: str, name: str) -> str:
    if sku.upper().startswith("CONSUMO"):
        return "CONSUMO TALLER"
    first_word = name.split()[0].upper() if name else ""
    return first_word or "SIN CATEGORIA"


# ── Data loading ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def load_sheet() -> pd.DataFrame:
    resp = requests.get(CSV_URL, allow_redirects=True, timeout=30)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")
    if "html" in content_type:
        raise RuntimeError(
            "El Sheet no es publico: Google devolvio una pagina de login. "
            "Compartelo como 'Cualquiera con el enlace puede ver'."
        )

    reader = csv.reader(io.StringIO(resp.text))
    records = []

    for raw in reader:
        row = raw + [""] * (7 - len(raw))

        sku         = row[0].strip()
        description = row[1].strip()

        if not sku and not description:
            continue
        if sku.upper() in ("CLAVE DE PRODUCTO", "CLAVE", "STOCK DE ALMACEN 2 Y 3"):
            continue
        if is_category_header(row):
            continue
        if not sku:
            continue

        records.append({
            "sku":         sku,
            "descripcion": description or sku,
            "entradas":    parse_float(row[2]),
            "salidas":     parse_float(row[3]),
            "stock":       parse_float(row[4]),
            "categoria":   extract_category(sku, description),
        })

    return pd.DataFrame(records)


# ── Status and display helpers ─────────────────────────────────────────────────

def status(row) -> str:
    if row["stock"] <= 0:
        return "Sin Stock"
    if row["stock"] <= DEFAULT_THRESHOLD:
        return "Bajo"
    return "OK"


def kpi_card(label, value, color="normal"):
    card_cls = "alert" if color == "red" else ("warn" if color == "orange" else "")
    val_cls  = color if color in ("red", "orange") else ""
    st.markdown(f"""
    <div class="metric-card {card_cls}">
        <div class="metric-label">{label}</div>
        <div class="metric-value {val_cls}">{value}</div>
    </div>
    """, unsafe_allow_html=True)


# ── App ────────────────────────────────────────────────────────────────────────

st.markdown("# 📦 Dashboard de Inventario")
st.caption("Datos directos de Google Sheets · actualiza la página para refrescar")

if not CSV_URL:
    st.error("Configura SHEET_CSV_URL en los Secrets de la app "
             "(Streamlit Cloud → App settings → Secrets).")
    st.stop()

try:
    df = load_sheet()
except Exception as e:
    st.error(f"No se pudo leer el Google Sheet: {e}")
    st.stop()

if df.empty:
    st.warning("No se encontraron productos en el sheet.")
    st.stop()

df["estado"] = df.apply(status, axis=1)

# ── KPI row ────────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
with c1: kpi_card("SKUs Totales", f"{len(df):,}")
with c2: kpi_card("Categorías",   f"{df['categoria'].nunique():,}")
with c3:
    n = len(df[df["estado"] == "Bajo"])
    kpi_card("Stock Bajo", f"{n:,}", "orange" if n > 0 else "normal")
with c4:
    n = len(df[df["estado"] == "Sin Stock"])
    kpi_card("Sin Stock", f"{n:,}", "red" if n > 0 else "normal")

st.markdown("<br>", unsafe_allow_html=True)

# ── Charts row ─────────────────────────────────────────────────────────────────
left, right = st.columns(2)

with left:
    st.markdown('<div class="section-title">Stock por Categoría (top 15)</div>',
                unsafe_allow_html=True)
    cat = (df.groupby("categoria")["stock"]
             .sum().reset_index()
             .sort_values("stock", ascending=True)
             .tail(15))
    fig = px.bar(cat, x="stock", y="categoria", orientation="h",
                 color_discrete_sequence=["#1565c0"],
                 labels={"stock": "Unidades en stock", "categoria": ""})
    fig.update_layout(margin=dict(l=0, r=10, t=10, b=0), height=400,
                      plot_bgcolor="white", paper_bgcolor="white")
    fig.update_xaxes(showgrid=True, gridcolor="#f0f0f0")
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.markdown('<div class="section-title">Estado del Inventario</div>',
                unsafe_allow_html=True)
    status_df = df["estado"].value_counts().reset_index()
    status_df.columns = ["Estado", "Items"]
    fig2 = px.pie(
        status_df, values="Items", names="Estado",
        color="Estado",
        color_discrete_map={"OK": "#2e7d32", "Bajo": "#f57c00", "Sin Stock": "#c62828"},
        hole=0.45,
    )
    fig2.update_traces(textinfo="label+percent+value")
    fig2.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=400,
                       showlegend=False, paper_bgcolor="white")
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Alerts section ─────────────────────────────────────────────────────────────
alerts = df[df["estado"] != "OK"]
if not alerts.empty:
    with st.expander(f"⚠️ Items que necesitan atención ({len(alerts)} items)", expanded=True):
        sin_stock = alerts[alerts["estado"] == "Sin Stock"]
        bajo      = alerts[alerts["estado"] == "Bajo"]

        if not sin_stock.empty:
            st.error(f"**Sin Stock ({len(sin_stock)} items)**")
            st.dataframe(
                sin_stock[["sku", "descripcion", "categoria", "stock"]],
                use_container_width=True, hide_index=True
            )

        if not bajo.empty:
            st.warning(f"**Stock Bajo ({len(bajo)} items)**")
            st.dataframe(
                bajo[["sku", "descripcion", "categoria", "stock"]],
                use_container_width=True, hide_index=True
            )

# ── Full inventory table ────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Inventario Completo</div>',
            unsafe_allow_html=True)

f1, f2, f3 = st.columns([3, 2, 1])
search      = f1.text_input("🔍 Buscar (nombre o SKU)", "")
cats        = ["Todas"] + sorted(df["categoria"].dropna().unique().tolist())
cat_filter  = f2.selectbox("Categoría", cats)
stat_filter = f3.selectbox("Estado", ["Todos", "Sin Stock", "Bajo", "OK"])

filtered = df.copy()
if search:
    mask = (filtered["sku"].str.contains(search, case=False, na=False) |
            filtered["descripcion"].str.contains(search, case=False, na=False))
    filtered = filtered[mask]
if cat_filter != "Todas":
    filtered = filtered[filtered["categoria"] == cat_filter]
if stat_filter != "Todos":
    filtered = filtered[filtered["estado"] == stat_filter]


def highlight(row):
    if row["estado"] == "Sin Stock":
        return ["background-color: #ffebee"] * len(row)
    if row["estado"] == "Bajo":
        return ["background-color: #fff8e1"] * len(row)
    return [""] * len(row)


show_cols = ["sku", "descripcion", "categoria", "entradas", "salidas", "stock", "estado"]
st.dataframe(
    filtered[show_cols].style.apply(highlight, axis=1),
    use_container_width=True,
    height=480,
    hide_index=True,
)
st.caption(f"Mostrando {len(filtered):,} de {len(df):,} items")
