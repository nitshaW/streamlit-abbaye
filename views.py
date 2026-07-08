"""Tenant-parameterized dashboard views.

Each function renders one dashboard for a given tenant config (see tenants.py).
All data access is scoped by ``cfg["prefix"]`` (or ``cfg["email"]["table"]``) —
the customer is resolved server-side in Main.py and is never taken from user
input. Cache loaders are keyed by the fully-qualified table name, so
``@st.cache_data`` entries are naturally per-tenant (no cross-tenant leakage).

No st.set_page_config here — that's called once by the Main.py entrypoint that
drives st.navigation.
"""
import pandas as pd
import streamlit as st

from sf_session import get_session

SCHEMA = "SALES_ANALYTICS.PUBLIC"


def _csv(df):
    return df.to_csv(index=False).encode("utf-8")


# ---------------------------------------------------------------- Product Performance
@st.cache_data
def _load_report_items(table):
    df = get_session().sql(f"SELECT * FROM {SCHEMA}.{table}").to_pandas()
    df = df.drop_duplicates()
    df["ITEM_NAME"] = df["ITEM_NAME"].fillna("Unknown")
    df["PRODUCT_CATEGORY"] = df["PRODUCT_CATEGORY"].fillna("Unknown")
    df["BOOKED_MONTH"] = pd.to_datetime(df["BOOKED_MONTH"].astype(str) + "01", format="%Y%m%d")
    df["VALUE"] = df.apply(
        lambda r: r["VALUE_ADDED"] if pd.isna(r["VALUE"]) or r["VALUE"] == 0 else r["VALUE"], axis=1
    )
    df = df.rename(columns={
        "BOOKED_MONTH": "Booked Year Month", "ITEM_NAME": "Item Name",
        "PRODUCT_CATEGORY": "Department", "VIEWED": "View", "ITEMSPURCHASED": "Gross Quantity",
        "CONVERSION": "Conversion", "TRANSACTIONS": "Gross Booked", "ATTENDANCE": "Net Attendance",
        "VALUE": "Net Value", "CANCELLED": "Cancelled",
    })
    df["Booked Year Month"] = df["Booked Year Month"].dt.strftime("%Y-%m")
    return df


def product_performance(cfg):
    st.title("Product Performance")
    try:
        df = _load_report_items(f"{cfg['prefix']}_REPORT_ITEMS")
    except Exception:
        st.error("Unable to load data right now. Please try again later.")
        return

    st.sidebar.header("Filters")
    for label in ["Booked Year Month", "Item Name", "Department"]:
        picked = st.sidebar.multiselect(f"Select {label}", sorted(df[label].dropna().unique()))
        if picked:
            df = df[df[label].isin(picked)]

    cols = ["Booked Year Month", "Item Name", "Department", "View", "Gross Booked",
            "Conversion", "Net Attendance", "Net Value", "Cancelled", "Gross Quantity"]
    table = df[cols].sort_values("View", ascending=False)

    grand = table.select_dtypes(include=["number"]).sum().to_frame().T
    grand.index = ["Grand Total"]
    grand["Conversion"] = (grand["Gross Booked"] / grand["View"] * 100) if grand["View"].iloc[0] else 0
    grand = grand.reindex(columns=["View", "Gross Booked", "Conversion", "Net Attendance",
                                   "Net Value", "Cancelled", "Gross Quantity"]) \
                 .rename(columns={"Conversion": "Overall Conversion"}).round(2)

    st.dataframe(table, height=600, use_container_width=True)
    st.write("Grand Total")
    st.write(grand.map(lambda x: f"{x:,.2f}").to_html(), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button("Download Product Performance as CSV", data=_csv(pd.concat([table, grand])),
                       file_name="product_performance.csv", mime="text/csv")


# ---------------------------------------------------------------- Book Date / Event Date
_ATT_NUMERIC = ["TB_GUESTS", "TB_SUBTOTALAGREE", "ADDED_PRICE"]
_ATT_RENAME = {
    "TI_ITEMNAME": "Item", "PRODUCT_CATEGORY": "Department", "TB_GUESTS": "Net Attendance",
    "TB_SUBTOTALAGREE": "Net Value", "ADDED_PRICE": "ValueAdded", "SOURCE": "Source",
    "NETWORK": "Network", "VP_VENUENAME": "Venue", "P_CURRENTSTATUS": "Booking Status",
}


@st.cache_data
def _load_transactions(table):
    df = get_session().sql(f"SELECT * FROM {SCHEMA}.{table}").to_pandas()
    for c in _ATT_NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    ti, act = df["TI_STATUS"].astype(str), df["TB_ACTION"].astype(str)
    df["Transaction Status"] = "Charged"
    df.loc[(ti == "9") | (act == "refund"), "Transaction Status"] = "Refunded"
    df = df.rename(columns=_ATT_RENAME)
    df["Net Value"] = df.apply(
        lambda r: r["ValueAdded"] if pd.isna(r["Net Value"]) or r["Net Value"] == 0 else r["Net Value"], axis=1
    )
    for c in ["Item", "Department", "Venue", "Source", "Network", "Booking Status"]:
        df[c] = df[c].fillna("Unknown")
    return df


def attendance(cfg, date_col, title):
    st.title(title)
    try:
        df = _load_transactions(f"{cfg['prefix']}_UVE_TRANSACTIONS_GROUPED").copy()
    except Exception:
        st.error("Unable to load data right now. Please try again later.")
        return
    df["Date"] = pd.to_datetime(df[date_col], errors="coerce")

    st.sidebar.header("Filters")
    dr = st.sidebar.date_input("Select date range", [])
    if len(dr) == 2:
        df = df[(df["Date"] >= pd.to_datetime(dr[0])) & (df["Date"] <= pd.to_datetime(dr[1]))]
    for label in ["Source", "Network", "Department", "Venue", "Item", "Booking Status", "Transaction Status"]:
        picked = st.sidebar.multiselect(f"Select {label}", sorted(df[label].dropna().unique()))
        if picked:
            df = df[df[label].isin(picked)]

    st.caption("***Use only reserved status when using Booking Status filter***")
    agg = (df.groupby(["Item", "Department"], as_index=False)[["Net Attendance", "Net Value"]]
             .sum().sort_values("Net Attendance", ascending=False))
    grand = agg[["Net Attendance", "Net Value"]].sum().to_frame().T.round(2)
    grand.index = ["Grand Total"]

    st.dataframe(agg, height=600, use_container_width=True)
    st.write("Grand Total")
    st.write(grand.map(lambda x: f"{x:,.2f}").to_html(), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button("Download as CSV", data=_csv(pd.concat([agg, grand])),
                       file_name=f"{title.lower().replace(' ', '_')}.csv", mime="text/csv")


# ---------------------------------------------------------------- Email Campaigns
_EMAIL_NUMERIC = ["SENT", "OPEN", "CLICKS", "DATA_CLICKS", "DATA_OPENS"]


@st.cache_data
def _load_email(table):
    df = get_session().sql(f"SELECT * FROM {SCHEMA}.{table}").to_pandas()
    df = df.drop_duplicates(subset=["DATA_ID"])           # no-op on pre-deduped views
    for c in _EMAIL_NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["DATA_TS_DATE"] = pd.to_datetime(df["DATA_TS_DATE"]).dt.tz_localize(None)
    return df


def _email_section(title, d):
    st.markdown(f"## 📅 {title}")
    if d.empty:
        st.caption("No data")
        return
    record = d["DATA_ID"].count()
    sent, opened = d["SENT"].sum(), d["OPEN"].sum()
    data_clicks, clicks = d["DATA_CLICKS"].sum(), d["CLICKS"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Email Sent", int(record))
    c2.metric("Emails Delivered", int(sent))
    c3.metric("Emails Opened", int(opened))
    c4.metric("AVG Delivery Rate", f"{(sent/record if record else 0):.2%}")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Data Clicks", int(data_clicks))
    c6.metric("Email With at Least 1 Click", int(clicks))
    c7.metric("Click Rate (CTR)", f"{(clicks/sent if sent else 0):.2%}")
    c8.metric("AVG Open Rate", f"{(opened/sent if sent else 0):.2%}")


def email_campaigns(cfg):
    st.title("📧 Email Campaigns")
    ec = cfg["email"]
    try:
        df = _load_email(ec["table"]).copy()
    except Exception:
        st.error("Unable to load data right now. Please try again later.")
        return

    # Scope to this customer's emails (source table may be multi-property).
    subj = df[ec["subject_field"]].fillna("")
    df = df[subj.str.contains(ec["subject_match"], case=False, na=False)]

    if df.empty:
        st.info("No email data for this customer yet.")
        return

    from datetime import timedelta
    start, end = df["DATA_TS_DATE"].min().date(), df["DATA_TS_DATE"].max().date()
    dr = st.sidebar.date_input("Select date range", [start, end])
    if len(dr) == 2:
        df = df[(df["DATA_TS_DATE"] >= pd.Timestamp(dr[0]))
                & (df["DATA_TS_DATE"] < pd.Timestamp(dr[1]) + timedelta(days=1))]

    tag = df[ec["tag_field"]].fillna("")
    for tag_value, label in ec["buckets"]:
        _email_section(label, df[tag == tag_value])
    _email_section("Total Emails", df)

    st.markdown("## 📊 General Data")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📧 Emails Sent")
        st.dataframe(df.groupby("DATA_STATE").size().reset_index(name="Total"), use_container_width=True)
    with col2:
        st.markdown("### 🔄 Open Frequency")
        st.dataframe(df.groupby("DATA_OPENS").size().reset_index(name="Total"), use_container_width=True)


# Page-key -> render(cfg). Referenced by tenants.py page sets + Main.py router.
PAGES = {
    "product_performance": product_performance,
    "book_date": lambda cfg: attendance(cfg, "T_TRANSDATE", "Book Date"),
    "event_date": lambda cfg: attendance(cfg, "TI_CALDATE", "Event Date"),
    "email_campaigns": email_campaigns,
}
