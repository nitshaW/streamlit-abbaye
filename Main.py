"""Multi-tenant entrypoint / router.

Flow: username/password sign-in (streamlit-authenticator, creds in Snowflake)
-> resolve the customer from the authenticated email -> build that customer's
dashboard set from the tenant registry -> st.navigation runs the page, scoped
to that customer's data. Unauthorized emails get an access-denied page.
"""
import os
import sys

import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from auth import require_login, current_email, resolve_tenant
from tenants import TENANTS, PAGE_TITLES
import views

st.set_page_config(layout="wide", page_title="UrVenue Analytics")

authenticator = require_login()          # renders login form; stops until authenticated
email = current_email()
tenant_key = resolve_tenant(email)

if not tenant_key or tenant_key not in TENANTS:
    st.title("Access denied")
    st.write("Your account isn't authorized for any dashboard. Please contact your administrator.")
    if authenticator is not None:
        authenticator.logout(location="main")
    st.stop()

cfg = TENANTS[tenant_key]

with st.sidebar:
    st.subheader(cfg["label"])
    if email:
        st.caption(email)
    if authenticator is not None:
        authenticator.logout(location="sidebar")


def _page(page_key):
    render = views.PAGES[page_key]
    return lambda: render(cfg)


pages = [
    st.Page(_page(pk), title=PAGE_TITLES.get(pk, pk), url_path=pk)
    for pk in cfg["pages"] if pk in views.PAGES
]
st.navigation(pages).run()
