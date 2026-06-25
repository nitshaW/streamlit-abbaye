import os
import sys

import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from auth import require_auth

st.set_page_config(layout="wide")
require_auth()
st.title("Abbaye Data Analytics")
st.info("Select one of the charts from the sidebar")

