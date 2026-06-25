import os
import sys
from datetime import timedelta

import streamlit as st
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth import require_auth
from sf_session import get_session

st.set_page_config(layout="wide")
require_auth()
st.title("📧 Email Campaigns")

# ABBAYE_MANDRILL_NOTIFICATIONS is a multi-property table, so scope to Abbaye by
# subject. Abbaye automatic emails: days:15 ("Préparez votre séjour …") and
# days:0 (guest-portal account). No dedicated view exists, so we de-dup here.
PROPERTY_MATCH = "Abbaye des Vaux-de-Cernay"
NUMERIC_COLS = ["SENT", "OPEN", "CLICKS", "DATA_CLICKS", "DATA_OPENS"]


@st.cache_data
def get_dataframe(query):
    session = get_session()
    if session is None:
        st.error("Session is not initialized.")
        return None
    try:
        df = session.sql(query).to_pandas()
        df = df.drop_duplicates(subset=["DATA_ID"])
        for c in NUMERIC_COLS:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
        df["DATA_TS_DATE"] = pd.to_datetime(df["DATA_TS_DATE"]).dt.tz_localize(None)
        return df
    except Exception as e:
        st.error(f"Failed to execute query or process data: {str(e)}")
        return None


if st.button("Clear Cache"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

query = f"""
    SELECT *
    FROM SALES_ANALYTICS.PUBLIC.ABBAYE_MANDRILL_NOTIFICATIONS
    WHERE DATA_SUBJECT ILIKE '%{PROPERTY_MATCH}%'
"""
df = get_dataframe(query)


def render_section(title, d):
    st.markdown(f"## 📅 {title}")
    if d.empty:
        st.caption("No data")
        return
    record = d["DATA_ID"].count()
    sent = d["SENT"].sum()
    opened = d["OPEN"].sum()
    data_clicks = d["DATA_CLICKS"].sum()
    clicks = d["CLICKS"].sum()
    delivery_rate = sent / record if record else 0
    ctr = clicks / sent if sent else 0
    open_rate = opened / sent if sent else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Email Sent", int(record))
    c2.metric("Emails Delivered", int(sent))
    c3.metric("Emails Opened", int(opened))
    c4.metric("AVG Delivery Rate", f"{delivery_rate:.2%}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Data Clicks", int(data_clicks))
    c6.metric("Email With at Least 1 Click", int(clicks))
    c7.metric("Click Rate (CTR)", f"{ctr:.2%}")
    c8.metric("AVG Open Rate", f"{open_rate:.2%}")


if df is not None and not df.empty:
    start_default = df["DATA_TS_DATE"].min().date()
    end_default = df["DATA_TS_DATE"].max().date()
    date_range = st.sidebar.date_input("Select date range", [start_default, end_default])
    if len(date_range) == 2:
        start = pd.Timestamp(date_range[0])
        end = pd.Timestamp(date_range[1]) + timedelta(days=1)
        df = df[(df["DATA_TS_DATE"] >= start) & (df["DATA_TS_DATE"] < end)]

    tag = df["NOTIFICATION_TAG"].fillna("")
    render_section("Automatic Emails 15 days", df[tag == "days:15"])
    render_section("Guest Portal (0 days)", df[tag == "days:0"])
    render_section("Total Emails", df)

    st.markdown("## 📊 General Data")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📧 Emails Sent")
        st.dataframe(df.groupby("DATA_STATE").size().reset_index(name="Total"), use_container_width=True)
    with col2:
        st.markdown("### 🔄 Open Frequency")
        st.dataframe(df.groupby("DATA_OPENS").size().reset_index(name="Total"), use_container_width=True)

else:
    st.error("Failed to retrieve data.")
