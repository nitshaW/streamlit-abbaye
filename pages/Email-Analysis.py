import streamlit as st
from snowflake.snowpark import Session
import pandas as pd
from snowflake.snowpark.context import get_active_session
import os
import configparser

st.set_page_config(layout="wide")
st.title("Fairmont Email Analysis")

# Snowflake session via shared key-pair auth helper (see sf_session.py)
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sf_session import get_session

# Define a function to execute a query and return a DataFrame
@st.cache_data
def get_dataframe(query):
    session = get_session()
    if session is None:
        st.error("Session is not initialized.")
        return None
    try:
        # Execute query and fetch results
        snow_df = session.sql(query).collect()
        pandas_df = pd.DataFrame(snow_df)
        return pandas_df
    except Exception as e:
        st.error(f"Failed to execute query or process data: {str(e)}")
        return None

# Clear cache button
if st.button("Clear Cache"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.experimental_rerun()

# SQL query
query = """
    SELECT 
        *
    FROM 
        SALES_ANALYTICS.PUBLIC.FAIRMONT_EMAIL_ANALYSIS
    """

# Use the function to retrieve data
df = get_dataframe(query)

# Display the search input
st.markdown("## 🔍 Search the Table")
search_input = st.text_input("Type to search the table", "")

# Filter the dataframe based on the search input
if search_input:
    df = df[df.apply(lambda row: row.astype(str).str.contains(search_input, case=False).any(), axis=1)]

# Display the table result
if df is not None:
    st.markdown("## 📊 Table Result")
    st.dataframe(df, height=600, width=None)

# Button to link to external Google Sheet
st.markdown("## 📄 External Resources")
st.markdown("[Link to Google Sheet](https://docs.google.com/spreadsheets/d/1mZ0HIjC_TmwPJZRyAPRrSRdBeQa1x9eLhoN5_6q7whk/edit#gid=1600916908)")
