import streamlit as st
from snowflake.snowpark import Session
import pandas as pd
from snowflake.snowpark.context import get_active_session
import os
import configparser

st.set_page_config(layout="wide")
st.title("Email Conversion")

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
        snow_df = session.sql(query).to_pandas()
        return snow_df
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
        SALES_ANALYTICS.PUBLIC.FAIRMONT_EMAIL_CONVERSION_RESULTS
    """

# Use the function to retrieve data
df = get_dataframe(query)

# Rename columns
df.rename(columns={
    'year_month': 'Year Month',
    'count_id_notification_60_days': 'Email/60',
    'count_id_fellowship_60_days': 'Profile Converted/60',
    'count_transid_transbook_60_days': 'Gross Booked/60',
    'sum_guests_transbook_60_days': 'Gross Guests/60',
    'sum_subtotalagree_transbook_60_days': 'Gross Value/60',
    'count_id_notification_30_days': 'Email/30',
    'count_id_fellowship_30_days': 'Profile Converted/30',
    'count_transid_transbook_30_days': 'Gross Booked/30',
    'sum_guests_transbook_30_days': 'Gross Guests/30',
    'sum_subtotalagree_transbook_30_days': 'Gross Value/30',
    'count_id_notification_7_days': 'Email/7',
    'count_id_fellowship_7_days': 'Profile Converted/7',
    'count_transid_transbook_7_days': 'Gross Booked/7',
    'sum_guests_transbook_7_days': 'Gross Guests/7',
    'sum_subtotalagree_transbook_7_days': 'Gross Value/7',
    'conversion_percentage_60_days': 'Conversion Rate/60',
    'conversion_percentage_30_days': 'Conversion Rate/30',
    'conversion_percentage_7_days': 'Conversion Rate/7'
}, inplace=True)

# Ensure 'Conversion/60' and 'Conversion/7' have 2 decimal places and include a percentage sign
df['Conversion Rate/60'] = df['Conversion Rate/60'].apply(lambda x: f'{x:.2f}%')
df['Conversion Rate/30'] = df['Conversion Rate/30'].apply(lambda x: f'{x:.2f}%')
df['Conversion Rate/7'] = df['Conversion Rate/7'].apply(lambda x: f'{x:.2f}%')

# Order by 'Year Month' in descending order
df.sort_values(by='Year Month', ascending=False, inplace=True)

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
