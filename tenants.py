"""Tenant registry — loaded from Snowflake DASHBOARD_CUSTOMERS.

Each customer row declares its data source (PREFIX), page set (PAGES), and
per-page template params (EMAIL_CONFIG). Falls back to a small in-code registry
when the table is unavailable (e.g. local dev before the table exists).
"""
import json

import streamlit as st

from sf_session import get_session

CUSTOMERS_TABLE = "SALES_ANALYTICS.PUBLIC.DASHBOARD_CUSTOMERS"

PAGE_TITLES = {
    "product_performance": "Product Performance",
    "book_date": "Book Date",
    "event_date": "Event Date",
    "email_campaigns": "Email Campaigns",
    "guest_portal": "Guest Portal",
    "audience": "Audience",
}

# Local/dev fallback used only if DASHBOARD_CUSTOMERS is missing or empty.
_FALLBACK = {
    "abbaye": {
        "label": "Abbaye des Vaux-de-Cernay",
        "prefix": "ABBAYE",
        "pages": ["product_performance", "book_date", "event_date", "email_campaigns",
                  "guest_portal", "audience"],
        "email": {
            "table": "ABBAYE_MANDRILL_NOTIFICATIONS",
            "tag_field": "NOTIFICATION_TAG",
            "subject_field": "DATA_SUBJECT",
            "subject_match": "Abbaye des Vaux-de-Cernay",
            "buckets": [["days:15", "Automatic Emails 15 days"], ["days:0", "Guest Portal (0 days)"]],
        },
        # GA4 via the Snowflake Connector for Google Analytics (per-grain views).
        "ga4": {
            "database": "GOOGLE_ANALYTICS_AGGREGATE_DATA_DEST_DB",
            "schema": "GOOGLE_ANALYTICS_AGGREGATE_DATA_DEST_SCHEMA",
            "report": "ABBAYE_PARIS",   # -> ABBAYE_PARIS_GA4_DAILY / _EVENTS / _ITEMS / ...
        },
    },
    "rimrock": {
        "label": "Rimrock Banff",
        "prefix": "RIMROCK",
        "pages": ["product_performance", "book_date", "event_date", "email_campaigns"],
        "email": {
            "table": "RIMROCK_MANDRILL_NOTIFICATION_VIEW",
            "tag_field": "EXTRA",
            "subject_field": "SUBJECT",
            "subject_match": "Get the most out of your time at Rimrock Banff",
            "buckets": [["days:30", "30 days"], ["days:60", "60 days"], ["days:90", "90 days"]],
        },
    },
}


def _as_obj(v):
    """Snowflake ARRAY/VARIANT columns come back as JSON strings via to_pandas."""
    if v is None:
        return None
    if isinstance(v, (list, dict)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return v


@st.cache_data(ttl=300)
def load_tenants():
    # GA4_CONFIG is optional — retry without it so an older table still loads.
    df = None
    for extra in (", GA4_CONFIG", ""):
        try:
            df = get_session().sql(
                f"SELECT CUSTOMER, LABEL, PREFIX, PAGES, EMAIL_CONFIG{extra} "
                f"FROM {CUSTOMERS_TABLE} WHERE COALESCE(ACTIVE, TRUE)"
            ).to_pandas()
            break
        except Exception:
            df = None
    if df is None or df.empty:
        return dict(_FALLBACK)
    tenants = {}
    for _, r in df.iterrows():
        cust = str(r["CUSTOMER"]).strip().lower()
        tenants[cust] = {
            "label": r["LABEL"] or cust,
            "prefix": str(r["PREFIX"]).strip().upper(),
            "pages": _as_obj(r["PAGES"]) or [],
            "email": _as_obj(r["EMAIL_CONFIG"]) or {},
            "ga4": _as_obj(r["GA4_CONFIG"]) if "GA4_CONFIG" in df.columns else None,
        }
    return tenants
