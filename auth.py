"""Authentication (username/password) + tenant resolution.

Credentials live in the Snowflake DASHBOARD_USERS table (bcrypt password hashes
only — never plaintext). streamlit-authenticator renders the login form and
verifies the entered password against the stored hash; the same row carries the
user's CUSTOMER, which drives tenant routing (see tenants.py).

The customer is derived from the authenticated username server-side — never from
URL params or UI input.
"""
import streamlit as st
import streamlit_authenticator as stauth

from sf_session import get_session

USERS_TABLE = "SALES_ANALYTICS.PUBLIC.DASHBOARD_USERS"


def _access(key, default=None):
    try:
        return st.secrets["access"].get(key, default)
    except Exception:
        return default


@st.cache_data(ttl=300)
def _load_users():
    """Return (credentials dict for streamlit-authenticator, {email: customer})."""
    creds = {"usernames": {}}
    tenant_by_user = {}
    try:
        df = get_session().sql(
            f"SELECT EMAIL, NAME, PASSWORD_HASH, CUSTOMER FROM {USERS_TABLE} "
            f"WHERE COALESCE(ACTIVE, TRUE)"
        ).to_pandas()
    except Exception:
        return creds, tenant_by_user  # table missing / unreachable -> no users
    for _, r in df.iterrows():
        email = str(r["EMAIL"]).strip().lower()
        if not email or not r["PASSWORD_HASH"]:
            continue
        creds["usernames"][email] = {
            "email": email,
            "name": r["NAME"] or email,
            "password": r["PASSWORD_HASH"],   # bcrypt hash
        }
        tenant_by_user[email] = str(r["CUSTOMER"]).strip().lower()
    return creds, tenant_by_user


def _build_authenticator():
    creds, _ = _load_users()
    ck = st.secrets.get("cookie", {})
    return stauth.Authenticate(
        creds,
        ck.get("name", "urvenue_dashboards"),
        ck.get("key", "change-me-in-secrets"),
        float(ck.get("expiry_days", 1)),
        auto_hash=False,   # passwords are already bcrypt-hashed in Snowflake
    )


def require_login():
    """Render the login form and block until authenticated.

    Returns the authenticator (so the caller can render a logout button), or
    None under local dev bypass.
    """
    if _access("dev_bypass"):
        return None
    authenticator = _build_authenticator()
    authenticator.login(
        location="main",
        max_login_attempts=5,
        fields={"Form name": "UrVenue Analytics — Sign in"},
    )
    status = st.session_state.get("authentication_status")
    if status is False:
        st.error("Incorrect email or password.")
        st.stop()
    if status is None:
        st.info("Please sign in with your email and password to access your dashboards.")
        st.stop()
    return authenticator


def current_email():
    if _access("dev_bypass"):
        return None
    return (st.session_state.get("username") or "").strip().lower()


def resolve_tenant(email):
    """Return the customer key for this signed-in email, or None if unauthorized."""
    if _access("dev_bypass"):
        return _access("dev_tenant", "abbaye")
    _, tenant_by_user = _load_users()
    return tenant_by_user.get((email or "").strip().lower())
