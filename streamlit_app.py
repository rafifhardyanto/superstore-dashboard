import streamlit as st
import pandas as pd
from pathlib import Path

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Superstore Retail Dashboard", page_icon="🛒", layout="wide")

DATA_PATH = Path(__file__).parent / "superstore_rfm.xlsx"

# Palet warna (sama dengan tema kuning di Read Me)
YELLOW = "#F4C430"
DARK_YELLOW = "#D9A404"
ORANGE = "#C65A1E"
SAND = "#E8D9A8"
WARM_GREY = "#A89F8A"

# Pilihan time frame -> kode frekuensi pandas
FREQ = {"Weekly": "W-MON", "Monthly": "ME", "Quarterly": "QE", "Yearly": "YE"}
PERIOD_NAME = {"Weekly": "Week", "Monthly": "Month", "Quarterly": "Quarter", "Yearly": "Year"}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_excel(DATA_PATH, sheet_name="Transactions_Clean")
    df["order_date"] = pd.to_datetime(df["order_date"])
    return df


def aggregate_data(df, freq):
    """Ringkas transaksi jadi satu baris per periode (minggu/bulan/kuartal/tahun)."""
    agg = df.groupby(pd.Grouper(key="order_date", freq=freq)).agg(
        revenue=("sales", "sum"),
        profit=("profit", "sum"),
        orders=("order_id", "nunique"),
        customers=("customer_id", "nunique"),
    )
    # Metrik turunan dihitung SETELAH agregasi, bukan dijumlahkan/dirata-ratakan
    agg["margin"] = (agg["profit"] / agg["revenue"] * 100).fillna(0)
    agg["aov"] = (agg["revenue"] / agg["orders"]).fillna(0)
    return agg


def format_money(value):
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.2f}K"
    return f"${value:,.2f}"


def calculate_delta(series, is_ratio=False):
    """Bandingkan periode terakhir dengan periode sebelumnya."""
    if len(series) < 2:
        return None
    current, previous = series.iloc[-1], series.iloc[-2]
    if is_ratio:  # untuk persentase (margin) tampilkan selisih poin
        return f"{current - previous:+.2f} pp"
    if previous == 0:
        return None
    return f"{(current - previous) / previous * 100:+.1f}%"


def create_metric_chart(df, column, color, chart_type, height=150):
    chart_data = df[[column]]
    if chart_type == "Bar":
        st.bar_chart(chart_data, y=column, color=color, height=height)
    else:
        st.area_chart(chart_data, y=column, color=color, height=height)


def display_metric(col, title, value_text, df_period, column, color, is_ratio=False):
    with col:
        with st.container(border=True):
            delta = calculate_delta(df_period[column], is_ratio=is_ratio)
            st.metric(title, value_text, delta=delta)
            create_metric_chart(df_period, column, color, chart_type=chart_selection)


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df = load_data()

# ---------------------------------------------------------------------------
# Sidebar: input widgets
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🛒 Superstore Retail")
    st.header("⚙️ Settings")

    min_date = df["order_date"].min().date()
    max_date = df["order_date"].max().date()

    start_date = st.date_input("Start date", min_date, min_value=min_date, max_value=max_date)
    end_date = st.date_input("End date", max_date, min_value=min_date, max_value=max_date)

    time_frame = st.selectbox("Select time frame", list(FREQ.keys()), index=1)
    chart_selection = st.selectbox("Select a chart type", ("Bar", "Area"))

    st.header("🔎 Filters")
    all_regions = sorted(df["region"].unique())
    all_categories = sorted(df["category"].unique())
    all_segments = sorted(df["segment"].unique())

    regions = st.multiselect("Region", all_regions, default=all_regions)
    categories = st.multiselect("Category", all_categories, default=all_categories)
    segments = st.multiselect("Customer segment", all_segments, default=all_segments)

# ---------------------------------------------------------------------------
# Filter data
# ---------------------------------------------------------------------------
if start_date > end_date:
    st.error("Start date tidak boleh lebih besar dari End date.")
    st.stop()

mask = (
    (df["order_date"] >= pd.Timestamp(start_date))
    & (df["order_date"] <= pd.Timestamp(end_date))
    & (df["region"].isin(regions))
    & (df["category"].isin(categories))
    & (df["segment"].isin(segments))
)
df_filtered = df.loc[mask]

if df_filtered.empty:
    st.warning("Tidak ada data untuk kombinasi filter ini. Coba longgarkan filter di sidebar.")
    st.stop()

df_period = aggregate_data(df_filtered, FREQ[time_frame])

# ---------------------------------------------------------------------------
# Overview Bisnis: KPI cards
# ---------------------------------------------------------------------------
st.header("Overview Bisnis")
st.caption(
    f"Periode {start_date:%d %b %Y} – {end_date:%d %b %Y}. "
    f"Perubahan (delta) membandingkan {PERIOD_NAME[time_frame].lower()} terakhir dengan sebelumnya."
)

# Total untuk seluruh rentang terpilih (dihitung dari data mentah, bukan dari jumlah per periode)
total_revenue = df_filtered["sales"].sum()
total_profit = df_filtered["profit"].sum()
profit_margin = total_profit / total_revenue * 100 if total_revenue else 0
total_orders = df_filtered["order_id"].nunique()
total_customers = df_filtered["customer_id"].nunique()
avg_order_value = total_revenue / total_orders if total_orders else 0

row1 = st.columns(3)
display_metric(row1[0], "Total Revenue", format_money(total_revenue), df_period, "revenue", YELLOW)
display_metric(row1[1], "Total Profit", format_money(total_profit), df_period, "profit", DARK_YELLOW)
display_metric(row1[2], "Profit Margin", f"{profit_margin:.2f}%", df_period, "margin", ORANGE, is_ratio=True)

row2 = st.columns(3)
display_metric(row2[0], "Total Customers", f"{total_customers:,}", df_period, "customers", SAND)
display_metric(row2[1], "Total Orders", f"{total_orders:,}", df_period, "orders", WARM_GREY)
display_metric(row2[2], "Avg Order Value", format_money(avg_order_value), df_period, "aov", YELLOW)

# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
left, right = st.columns([2, 1])

with left:
    with st.container(border=True):
        st.subheader(f"Revenue by {PERIOD_NAME[time_frame]}")
        create_metric_chart(df_period, "revenue", YELLOW, chart_selection, height=300)

with right:
    with st.container(border=True):
        st.subheader("Total Revenue by Category")
        by_category = df_filtered.groupby("category")["sales"].sum().sort_values(ascending=False)
        st.bar_chart(by_category, color=DARK_YELLOW, horizontal=True, height=300)

left, right = st.columns(2)

with left:
    with st.container(border=True):
        st.subheader("Total Revenue by Region")
        by_region = df_filtered.groupby("region")["sales"].sum().sort_values(ascending=False)
        st.bar_chart(by_region, color=YELLOW, height=300)

with right:
    with st.container(border=True):
        st.subheader("Total Revenue and Total Profit by Region")
        region_compare = (
            df_filtered.groupby("region")[["sales", "profit"]]
            .sum()
            .rename(columns={"sales": "Total Revenue", "profit": "Total Profit"})
            .sort_values("Total Revenue", ascending=False)
        )
        st.bar_chart(region_compare, color=[YELLOW, ORANGE], stack=False, height=300)

# ---------------------------------------------------------------------------
# DataFrame display
# ---------------------------------------------------------------------------
with st.expander("See DataFrame (aggregated by selected time frame)"):
    st.dataframe(df_period)

with st.expander("See DataFrame (filtered transactions)"):
    st.dataframe(df_filtered)
