import streamlit as st
from snowflake.snowpark import Session
import plotly.express as px
import pandas as pd
from snowflake.snowpark.context import get_active_session
import os
import configparser

st.set_page_config(layout="wide")
st.title("Attendance - Booked Analysis")

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

        # Perform preprocessing on Snowflake using Snowpark DataFrame operations
        snow_df = snow_df.drop_duplicates()

        # Replace nulls in specific columns with 'Unknown'
        snow_df['NETWORK'] = snow_df['NETWORK'].fillna('Unknown')
        snow_df['PRODUCT_CATEGORY'] = snow_df['PRODUCT_CATEGORY'].fillna('Unknown')
        snow_df['SOURCE'] = snow_df['SOURCE'].fillna('Unknown')
        snow_df['P_VENUENAME'] = snow_df['P_VENUENAME'].fillna('Unknown')
        snow_df['P_CURRENTSTATUS'] = snow_df['P_CURRENTSTATUS'].fillna('Unknown')
        snow_df['B_ITEMNAME'] = snow_df['B_ITEMNAME'].fillna('Unknown')

        # Rename columns
        snow_df.rename(columns={
            'B_ITEMNAME': 'Item',
            'PRODUCT_CATEGORY': 'Department',
            'GUESTS': 'Net Attendance',
            'B_VALUE': 'Net Value',
            'ADDED_PRICE': 'ValueAdded',
            'SOURCE': 'Source',
            'P_CALDATE': 'Event Date',
            'NETWORK': 'Network',
            'P_VENUENAME': 'Venue',
            'P_CURRENTSTATUS': 'Booking Status'
        }, inplace=True)
        
        # Define the list of sources to keep
        sources_to_keep = ['guestportal', 'internal', '', 'fairmontbanff']

        # Filter the DataFrame to keep only the rows where 'Source' is in the specified list
        snow_df = snow_df[snow_df['Source'].isin(sources_to_keep)]

        # Convert Event Date' to datetime
        snow_df['Event Date'] = pd.to_datetime(snow_df['Event Date'], format='%Y-%m-%d')


        # Handle Value column with ValueAdded
        snow_df['Net Value'] = snow_df.apply(
            lambda row: row['ValueAdded'] if pd.isna(row['Net Value']) or row['Net Value'] == 0 else row['Net Value'],
            axis=1
        )

        return snow_df
    except Exception as e:
        st.error(f"Failed to execute query or process data: {str(e)}")
        return None

# Clear cache button
if st.button("Clear Cache"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.experimental_rerun()
    
# Function to convert DataFrame to CSV
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# SQL query with fully qualified table name
query = """
    SELECT 
        *
    FROM 
        SALES_ANALYTICS.PUBLIC.FAIRMONT_UVE_BOOKINGS_GROUPED
    """

# Use the function to retrieve data
df = get_dataframe(query)

# Check if df is not None before applying filters
if df is not None:
    # Interactive filters
    st.sidebar.header("Filters")

    date_range = st.sidebar.date_input("Select Event Date Range", [])
    
    if len(date_range) == 2:
            df = df[(df['Event Date'] >= pd.to_datetime(date_range[0])) & (df['Event Date'] <= pd.to_datetime(date_range[1]))]

    selected_source = st.sidebar.multiselect("Select Source", df['Source'].unique())
    if selected_source:
        df = df[df['Source'].isin(selected_source)]

    selected_network = st.sidebar.multiselect("Select Network", df['Network'].unique())
    if selected_network:
        df = df[df['Network'].isin(selected_network)]

    selected_department = st.sidebar.multiselect("Select Department", df['Department'].unique())
    if selected_department:
        df = df[df['Department'].isin(selected_department)]

    selected_venue = st.sidebar.multiselect("Select Venue", df['Venue'].unique())
    if selected_venue:
        df = df[df['Venue'].isin(selected_venue)]

    selected_item = st.sidebar.multiselect("Select Item", df['Item'].unique())
    if selected_item:
        df = df[df['Item'].isin(selected_item)]

    selected_booking_status = st.sidebar.multiselect("Select Booking Status", df['Booking Status'].unique())
    if selected_booking_status:
        df = df[df['Booking Status'].isin(selected_booking_status)]

    # Group by month and create plot
    df['Month'] = pd.to_datetime(df['Event Date']).dt.to_period('M').dt.to_timestamp()

    chart_data_attendance = df.groupby(['Month', 'Item']).agg({'Net Attendance': 'sum'}).reset_index()
    chart_data_value = df.groupby(['Month', 'Item']).agg({'Net Value': 'sum'}).reset_index()

    aggregated_tab, chart_tab = st.tabs(["Aggregated Tabular Data", "Charts"])

    with aggregated_tab:
        st.write("Aggregated Tabular Data")
        aggregated_df = df.groupby(['Item', 'Department']).agg({'Net Attendance': 'sum', 'Net Value': 'sum'}).reset_index()

        # Calculate grand total row for aggregated data
        grand_total_aggregated = aggregated_df.select_dtypes(include=['number']).sum().to_frame().T
        grand_total_aggregated.index = ['Grand Total']

        # Round values to 2 decimal places
        grand_total_aggregated = grand_total_aggregated.round(2)

        # Format values to two decimal places as strings
        grand_total_aggregated = grand_total_aggregated.applymap(lambda x: f'{x:.2f}')
        
        st.dataframe(aggregated_df, height=600, use_container_width=True)

        st.write("Grand Total")
        grand_total_aggregated_style = grand_total_aggregated.style.set_properties(
            **{'text-align': 'left', 'white-space': 'nowrap', 'overflow': 'hidden', 'text-overflow': 'ellipsis'}
        )
        st.write(grand_total_aggregated_style.to_html(), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)  # Add space above the download button

        # Allow CSV download for aggregated data
        aggregated_df_with_total = pd.concat([aggregated_df, grand_total_aggregated])
        csv_data_aggregated = convert_df_to_csv(aggregated_df_with_total)
        st.download_button(label="Download Aggregated Data as CSV", data=csv_data_aggregated, file_name='aggregated_data.csv', mime='text/csv')
   
        st.write("Attendance - Booked Data")
        renamed_columns = [
            'Event Date', 'Item', 'Venue', 'Department', 'Source',
            'Network', 'Booking Status', 'Net Attendance', 'Net Value'
        ]
        filtered_df = df[renamed_columns]

        # Calculate grand total row dynamically
        grand_total = filtered_df.select_dtypes(include=['number']).sum().to_frame().T
        grand_total.index = ['Grand Total']

        # Round values to 2 decimal places
        grand_total = grand_total.round(2)

        # Format values to two decimal places as strings
        grand_total = grand_total.applymap(lambda x: f'{x:.2f}')
        
        # Display data without grand total row in full height
        st.dataframe(filtered_df, height=600, use_container_width=True)  

        # Display grand total row separately with fixed column widths
        st.write("Grand Total")
        grand_total_style = grand_total.style.set_properties(
            **{'text-align': 'left', 'white-space': 'nowrap', 'overflow': 'hidden', 'text-overflow': 'ellipsis'}
        )
        st.write(grand_total_style.to_html(), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)  # Add space above the download button

        # Allow CSV download
        filtered_df_with_total = pd.concat([filtered_df, grand_total])
        csv_data = convert_df_to_csv(filtered_df_with_total)
        st.download_button(label="Download Attendance vs Booked Data as CSV", data=csv_data, file_name='attendance_vs_booked_data.csv', mime='text/csv')

    with chart_tab:
        fig_attendance = px.line(chart_data_attendance, x='Month', y='Net Attendance', color='Item', title='Attendance Over Time',
                                 labels={'Month': 'Date', 'Net Attendance': 'Net Attendance'}, markers=True)
        st.plotly_chart(fig_attendance, use_container_width=True)
        
        fig_value = px.line(chart_data_value, x='Month', y='Net Value', color='Item', title='Net Value Over Time',
                            labels={'Month': 'Date', 'Net Value': 'Net Value'}, markers=True)
        st.plotly_chart(fig_value, use_container_width=True)

else:
    st.error("Failed to retrieve data.")
