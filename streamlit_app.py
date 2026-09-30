import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Superstore Retail Dashboard", page_icon="🛒", layout="wide")

DATA_PATH = Path(__file__).parent / "superstore_rfm.xlsx"

# Palet warna untuk KPI card
YELLOW = "#F4C430"
DARK_YELLOW = "#D9A404"
ORANGE = "#C65A1E"
SAND = "#E8D9A8"
WARM_GREY = "#A89F8A"

# Pilihan time frame -> kode frekuensi pandas
FREQ = {"Weekly": "W-MON", "Monthly": "ME", "Quarterly": "QE", "Yearly": "YE"}
PERIOD_NAME = {"Weekly": "Week", "Monthly": "Month", "Quarterly": "Quarter", "Yearly": "Year"}

# Urutan & warna 10 segmen RFM 
SEGMENT_COLORS = {
    "Loyal Customers": "#4CAF50",
    "Champions": "#F4C430",
    "Can't Lose Them": "#D45B90",
    "Others": "#A89F8A",
    "New Customers": "#29B5E8",
    "Lost": "#B22222",
    "At Risk": "#C65A1E",
    "Hibernating": "#6C7A89",
    "Promising": "#7D44CF",
    "Need Attention": "#E8D9A8",
}
SEGMENT_ORDER = list(SEGMENT_COLORS.keys())


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_excel(DATA_PATH, sheet_name="Transactions_Clean")
    df["order_date"] = pd.to_datetime(df["order_date"])
    return df


@st.cache_data
def load_rfm():
    return pd.read_excel(DATA_PATH, sheet_name="Customer_RFM")


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


def segment_color_scale(present_segments):
    """Skala warna Altair: satu warna tetap untuk tiap segmen."""
    domain = [s for s in SEGMENT_ORDER if s in present_segments]
    return alt.Scale(domain=domain, range=[SEGMENT_COLORS[s] for s in domain])


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df = load_data()
df_rfm = load_rfm()

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
# Filter data transaksi (dipakai tab Overview)
# ---------------------------------------------------------------------------
mask = (
    (df["order_date"] >= pd.Timestamp(start_date))
    & (df["order_date"] <= pd.Timestamp(end_date))
    & (df["region"].isin(regions))
    & (df["category"].isin(categories))
    & (df["segment"].isin(segments))
)
df_filtered = df.loc[mask]


# ---------------------------------------------------------------------------
# Tab 1: Overview Bisnis
# ---------------------------------------------------------------------------
def render_overview():
    st.header("Overview Bisnis")

    if start_date > end_date:
        st.error("Start date tidak boleh lebih besar dari End date.")
        return
    if df_filtered.empty:
        st.warning("Tidak ada data untuk kombinasi filter ini. Coba longgarkan filter di sidebar.")
        return

    st.caption(f"Periode {start_date:%d %b %Y} – {end_date:%d %b %Y}")

    df_period = aggregate_data(df_filtered, FREQ[time_frame])

    # Total untuk seluruh rentang terpilih (dari data mentah, bukan jumlah per periode)
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
# Tab 2: RFM Segmentation
# ---------------------------------------------------------------------------
def render_rfm():
    st.header("RFM Segmentation")
    st.caption(
        "Segmentasi RFM dihitung dari seluruh riwayat transaksi (per 31 Des 2017), "
        "jadi filter tanggal dan kategori tidak berlaku di tab ini. "
        "Filter Region dan Customer segment di sidebar tetap berlaku."
    )

    selected_segments = st.multiselect("RFM Segment", SEGMENT_ORDER, default=SEGMENT_ORDER)

    rfm = df_rfm[
        df_rfm["region"].isin(regions)
        & df_rfm["business_segment"].isin(segments)
        & df_rfm["segment_rfm"].isin(selected_segments)
    ]
    if rfm.empty:
        st.warning("Tidak ada pelanggan untuk kombinasi filter ini.")
        return

    # Ringkasan per segmen: jumlah pelanggan + persentase
    seg = rfm.groupby("segment_rfm").size().rename("customers").reset_index()
    seg = seg.sort_values("customers", ascending=False).reset_index(drop=True)
    seg["pct"] = seg["customers"] / seg["customers"].sum() * 100
    seg["label"] = [f"{s} ({p:.1f}%)" for s, p in zip(seg["segment_rfm"], seg["pct"])]
    seg["color"] = [SEGMENT_COLORS[s] for s in seg["segment_rfm"]]

    color_scale = segment_color_scale(set(seg["segment_rfm"]))

    left, right = st.columns(2)

    # --- Donut chart: Segment Percentage ---
    with left:
        with st.container(border=True):
            st.subheader("Segment Percentage")
            donut = (
                alt.Chart(seg)
                .mark_arc(innerRadius=70, outerRadius=130)
                .encode(
                    theta=alt.Theta("customers:Q"),
                    color=alt.Color(
                        "label:N",
                        scale=alt.Scale(domain=seg["label"].tolist(), range=seg["color"].tolist()),
                        legend=alt.Legend(title=None),
                    ),
                    order=alt.Order("customers:Q", sort="descending"),
                    tooltip=[
                        alt.Tooltip("segment_rfm:N", title="Segment"),
                        alt.Tooltip("customers:Q", title="Customers"),
                        alt.Tooltip("pct:Q", title="Persentase (%)", format=".2f"),
                    ],
                )
            )
            # Angka total pelanggan di tengah donut
            center = (
                alt.Chart(pd.DataFrame({"total": [f"{len(rfm):,}"]}))
                .mark_text(size=34, fontWeight="bold", color=DARK_YELLOW)
                .encode(text="total:N")
            )
            st.altair_chart((donut + center).properties(height=300))

    # --- Bar chart: Segment Split ---
    with right:
        with st.container(border=True):
            st.subheader("Segment Split")
            bars = (
                alt.Chart(seg)
                .mark_bar()
                .encode(
                    x=alt.X("customers:Q", title="Jumlah Customer"),
                    y=alt.Y("segment_rfm:N", sort="-x", title=None),
                    color=alt.Color("segment_rfm:N", scale=color_scale, legend=None),
                    tooltip=[
                        alt.Tooltip("segment_rfm:N", title="Segment"),
                        alt.Tooltip("customers:Q", title="Customers"),
                    ],
                )
            )
            bar_labels = (
                alt.Chart(seg)
                .mark_text(align="left", dx=4, color=WARM_GREY)
                .encode(
                    x=alt.X("customers:Q"),
                    y=alt.Y("segment_rfm:N", sort="-x"),
                    text="customers:Q",
                )
            )
            st.altair_chart((bars + bar_labels).properties(height=300))

    # --- Scatter plot: Recency vs Monetary ---
    with st.container(border=True):
        st.subheader(f"Recency vs Monetary — {len(rfm):,} pelanggan")
        st.caption("Ukuran titik = frequency. Kamu bisa zoom dan geser grafiknya.")
        scatter_data = rfm[["customer_name", "segment_rfm", "recency_days", "frequency", "monetary"]]
        scatter = (
            alt.Chart(scatter_data)
            .mark_circle(opacity=0.75)
            .encode(
                x=alt.X("recency_days:Q", title="Hari Semenjak Order Terakhir"),
                y=alt.Y("monetary:Q", title="Monetary ($)", axis=alt.Axis(format="$,.0f")),
                size=alt.Size("frequency:Q", legend=None, scale=alt.Scale(range=[30, 300])),
                color=alt.Color("segment_rfm:N", scale=color_scale, legend=alt.Legend(title="RFM Segment")),
                tooltip=[
                    alt.Tooltip("customer_name:N", title="Customer"),
                    alt.Tooltip("segment_rfm:N", title="Segment"),
                    alt.Tooltip("recency_days:Q", title="Recency (hari)"),
                    alt.Tooltip("frequency:Q", title="Frequency"),
                    alt.Tooltip("monetary:Q", title="Monetary", format="$,.2f"),
                ],
            )
            .properties(height=400)
            .interactive()
        )
        st.altair_chart(scatter)

    # --- Customer list ---
    with st.container(border=True):
        st.subheader("Customers List")
        customer_list = (
            rfm[["customer_name", "region", "recency_days", "frequency", "monetary", "segment_rfm"]]
            .sort_values("customer_name")
            .rename(
                columns={
                    "customer_name": "Customer Name",
                    "region": "Region",
                    "recency_days": "Recency Days",
                    "frequency": "Frequency",
                    "monetary": "Monetary",
                    "segment_rfm": "RFM Segment",
                }
            )
        )
        st.dataframe(
            customer_list,
            hide_index=True,
            column_config={"Monetary": st.column_config.NumberColumn(format="$%.2f")},
        )


# ---------------------------------------------------------------------------
# Tampilkan tab
# ---------------------------------------------------------------------------
tab_overview, tab_rfm = st.tabs(["📊 Overview", "👥 RFM Segmentation"])

with tab_overview:
    render_overview()

with tab_rfm:
    render_rfm()
