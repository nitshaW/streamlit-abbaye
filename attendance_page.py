"""Shared renderer for the Book Date / Event Date pages.

Both mirror the Looker report: the same `ABBAYE_UVE_TRANSACTIONS_GROUPED`
source aggregated to Item · Department · Net Attendance · Net Value, with the
report's filter set. They differ only by which date field drives the date
range — T_TRANSDATE (Book Date) vs TI_CALDATE (Event Date).
"""
import os

import pandas as pd
import streamlit as st

from sf_session import get_session
from auth import require_auth

_NUMERIC = ["TB_GUESTS", "TB_SUBTOTALAGREE", "ADDED_PRICE"]
_RENAME = {
    "TI_ITEMNAME": "Item",
    "PRODUCT_CATEGORY": "Department",
    "TB_GUESTS": "Net Attendance",
    "TB_SUBTOTALAGREE": "Net Value",
    "ADDED_PRICE": "ValueAdded",
    "SOURCE": "Source",
    "NETWORK": "Network",
    "VP_VENUENAME": "Venue",
    "P_CURRENTSTATUS": "Booking Status",
}


@st.cache_data
def _load(date_col):
    session = get_session()
    if session is None:
        return None
    df = session.sql(
        "SELECT * FROM SALES_ANALYTICS.PUBLIC.ABBAYE_UVE_TRANSACTIONS_GROUPED"
    ).to_pandas()
    for c in _NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # Transaction Status: charged / refunded
    ti = df["TI_STATUS"].astype(str)
    act = df["TB_ACTION"].astype(str)
    df["Transaction Status"] = "Charged"
    df.loc[(ti == "9") | (act == "refund"), "Transaction Status"] = "Refunded"

    df = df.rename(columns=_RENAME)
    # Net Value falls back to ValueAdded when missing/zero
    df["Net Value"] = df.apply(
        lambda r: r["ValueAdded"] if pd.isna(r["Net Value"]) or r["Net Value"] == 0 else r["Net Value"],
        axis=1,
    )
    df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
    for c in ["Item", "Department", "Venue", "Source", "Network", "Booking Status"]:
        df[c] = df[c].fillna("Unknown")
    return df


def _csv(df):
    return df.to_csv(index=False).encode("utf-8")


def render(date_col, title):
    st.set_page_config(layout="wide")
    require_auth()
    st.title(title)

    if st.button("Clear Cache"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    df = _load(date_col)
    if df is None:
        st.error("Failed to retrieve data.")
        return

    st.sidebar.header("Filters")
    dr = st.sidebar.date_input("Select date range", [])
    if len(dr) == 2:
        df = df[(df["Date"] >= pd.to_datetime(dr[0])) & (df["Date"] <= pd.to_datetime(dr[1]))]

    for label in ["Source", "Network", "Department", "Venue", "Item", "Booking Status", "Transaction Status"]:
        picked = st.sidebar.multiselect(f"Select {label}", sorted(df[label].dropna().unique()))
        if picked:
            df = df[df[label].isin(picked)]

    st.caption("***Use only reserved status when using Booking Status filter***")

    agg = (
        df.groupby(["Item", "Department"], as_index=False)[["Net Attendance", "Net Value"]]
        .sum()
        .sort_values("Net Attendance", ascending=False)
    )
    grand = agg[["Net Attendance", "Net Value"]].sum().to_frame().T.round(2)
    grand.index = ["Grand Total"]

    st.dataframe(agg, height=600, use_container_width=True)
    st.write("Grand Total")
    st.write(
        grand.applymap(lambda x: f"{x:,.2f}").style.set_properties(
            **{"text-align": "left", "white-space": "nowrap"}
        ).to_html(),
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button(
        "Download as CSV",
        data=_csv(pd.concat([agg, grand])),
        file_name=f"{title.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )
