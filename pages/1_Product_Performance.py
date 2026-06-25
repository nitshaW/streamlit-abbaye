import os
import sys

import streamlit as st
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from auth import require_auth
from sf_session import get_session

st.set_page_config(layout="wide")
require_auth()
st.title("Product Performance")


@st.cache_data
def get_dataframe(query):
    session = get_session()
    if session is None:
        st.error("Session is not initialized.")
        return None
    try:
        df = session.sql(query).to_pandas()
        df = df.drop_duplicates()
        df["ITEM_NAME"] = df["ITEM_NAME"].fillna("Unknown")
        df["PRODUCT_CATEGORY"] = df["PRODUCT_CATEGORY"].fillna("Unknown")
        df["BOOKED_MONTH"] = pd.to_datetime(df["BOOKED_MONTH"].astype(str) + "01", format="%Y%m%d")
        # Net value falls back to value-added when missing/zero
        df["VALUE"] = df.apply(
            lambda r: r["VALUE_ADDED"] if pd.isna(r["VALUE"]) or r["VALUE"] == 0 else r["VALUE"], axis=1
        )
        df = df.rename(columns={
            "BOOKED_MONTH": "Booked Year Month",
            "ITEM_NAME": "Item Name",
            "PRODUCT_CATEGORY": "Department",
            "VIEWED": "View",
            "ITEMSPURCHASED": "Gross Quantity",
            "CONVERSION": "Conversion",
            "TRANSACTIONS": "Gross Booked",
            "ATTENDANCE": "Net Attendance",
            "VALUE": "Net Value",
            "CANCELLED": "Cancelled",
        })
        df["Booked Year Month"] = df["Booked Year Month"].dt.strftime("%Y-%m")
        return df
    except Exception as e:
        st.error(f"Failed to execute query or process data: {str(e)}")
        return None


if st.button("Clear Cache"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()


def convert_df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")


df = get_dataframe("SELECT * FROM SALES_ANALYTICS.PUBLIC.ABBAYE_REPORT_ITEMS")

if df is not None:
    st.sidebar.header("Filters")
    for label in ["Booked Year Month", "Item Name", "Department"]:
        picked = st.sidebar.multiselect(f"Select {label}", sorted(df[label].dropna().unique()))
        if picked:
            df = df[df[label].isin(picked)]

    cols = [
        "Booked Year Month", "Item Name", "Department", "View", "Gross Booked",
        "Conversion", "Net Attendance", "Net Value", "Cancelled", "Gross Quantity",
    ]
    table = df[cols].sort_values("View", ascending=False)

    # Grand total with overall conversion = Gross Booked / View * 100
    grand = table.select_dtypes(include=["number"]).sum().to_frame().T
    grand.index = ["Grand Total"]
    grand["Conversion"] = (grand["Gross Booked"] / grand["View"] * 100) if grand["View"].iloc[0] else 0
    grand = grand.reindex(columns=[
        "View", "Gross Booked", "Conversion", "Net Attendance", "Net Value", "Cancelled", "Gross Quantity"
    ]).rename(columns={"Conversion": "Overall Conversion"}).round(2)

    st.dataframe(table, height=600, use_container_width=True)
    st.write("Grand Total")
    st.write(
        grand.applymap(lambda x: f"{x:,.2f}").style.set_properties(
            **{"text-align": "left", "white-space": "nowrap"}
        ).to_html(),
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button(
        "Download Product Performance as CSV",
        data=convert_df_to_csv(pd.concat([table, grand])),
        file_name="product_performance.csv",
        mime="text/csv",
    )
else:
    st.error("Failed to retrieve data.")
