"""Multi-tenant entrypoint / router.

Flow: username/password sign-in (streamlit-authenticator, creds in Snowflake
DASHBOARD_USERS) -> resolve the customer from the authenticated email -> load
that customer's config from Snowflake DASHBOARD_CUSTOMERS -> st.navigation runs
the page, scoped to that customer's data. Unauthorized emails get access-denied.
"""
import os
import sys

import streamlit as st

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from auth import require_login, current_email, resolve_tenant, account_sidebar
from tenants import load_tenants, PAGE_TITLES
import views

st.set_page_config(layout="wide", page_title="UrVenue Analytics")

authenticator = require_login()          # renders login form; stops until authenticated
email = current_email()
tenants = load_tenants()
tenant_key = resolve_tenant(email)
cfg = tenants.get(tenant_key) if tenant_key else None

if not cfg:
    st.title("Access denied")
    st.write("Your account isn't authorized for any dashboard. Please contact your administrator.")
    if authenticator is not None:
        authenticator.logout(location="main")
    st.stop()

with st.sidebar:
    st.subheader(cfg["label"])
    if email:
        st.caption(email)
account_sidebar(authenticator, email)    # logout + change-password


def _page(page_key):
    render = views.PAGES[page_key]
    return lambda: render(cfg)


pages = [
    st.Page(_page(pk), title=PAGE_TITLES.get(pk, pk), url_path=pk)
    for pk in cfg["pages"] if pk in views.PAGES
]
st.navigation(pages).run()
