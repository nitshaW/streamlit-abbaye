"""Authentication (username/password) + tenant resolution.

Credentials live in Snowflake DASHBOARD_USERS (bcrypt hashes; never plaintext):
    EMAIL, NAME, PASSWORD_HASH (NULL until set), CUSTOMER, INVITE_CODE, ACTIVE

Flows (all write the new bcrypt hash back to DASHBOARD_USERS.PASSWORD_HASH):
- Login: streamlit-authenticator verifies the entered password against the hash.
- First-login set-password: a user whose PASSWORD_HASH is NULL sets it (guarded
  by an optional INVITE_CODE the admin shares out-of-band).
- Change password: a signed-in user supplies current + new password.

The customer is resolved server-side from the authenticated email — never from
URL params or UI input.
"""
import os

import bcrypt
import streamlit as st
import streamlit_authenticator as stauth

from sf_session import get_session

USERS_TABLE = "SALES_ANALYTICS.PUBLIC.DASHBOARD_USERS"
MIN_PASSWORD_LEN = 10


def _access(key, default=None):
    try:
        return st.secrets["access"].get(key, default)
    except Exception:
        return default


@st.cache_data(ttl=300)
def _load_users():
    """Return (authenticator credentials for users WITH a password, {email: info})."""
    creds = {"usernames": {}}
    users = {}
    try:
        df = get_session().sql(
            f"SELECT EMAIL, NAME, PASSWORD_HASH, CUSTOMER, INVITE_CODE FROM {USERS_TABLE} "
            f"WHERE COALESCE(ACTIVE, TRUE)"
        ).to_pandas()
    except Exception:
        return creds, users  # table missing / unreachable -> no users
    for _, r in df.iterrows():
        email = str(r["EMAIL"]).strip().lower()
        if not email:
            continue
        pw_hash = r["PASSWORD_HASH"] or None
        users[email] = {
            "name": r["NAME"] or email,
            "customer": str(r["CUSTOMER"]).strip().lower() if r["CUSTOMER"] else None,
            "password_hash": pw_hash,
            "invite_code": str(r["INVITE_CODE"]).strip() if r["INVITE_CODE"] else None,
        }
        if pw_hash:  # only users who have set a password can log in
            creds["usernames"][email] = {"email": email, "name": r["NAME"] or email, "password": pw_hash}
    return creds, users


def _hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def _write_password(email, new_hash):
    """Persist a new bcrypt hash and clear any invite code, then refresh the cache."""
    email_e = email.replace("'", "''")
    hash_e = new_hash.replace("'", "''")  # bcrypt hashes contain no quotes, but be safe
    get_session().sql(
        f"UPDATE {USERS_TABLE} SET PASSWORD_HASH = '{hash_e}', INVITE_CODE = NULL "
        f"WHERE LOWER(EMAIL) = '{email_e}'"
    ).collect()
    _load_users.clear()


def _cookie_cfg():
    """Session-cookie settings: env vars win, then secrets.toml, then defaults."""
    try:
        ck = dict(st.secrets.get("cookie", {}))
    except Exception:
        ck = {}
    return (
        os.environ.get("COOKIE_NAME") or ck.get("name", "urvenue_dashboards"),
        os.environ.get("COOKIE_KEY") or ck.get("key", "change-me-in-secrets"),
        float(os.environ.get("COOKIE_EXPIRY_DAYS") or ck.get("expiry_days", 1)),
    )


def _build_authenticator(creds):
    name, key, expiry = _cookie_cfg()
    return stauth.Authenticate(creds, name, key, expiry, auto_hash=False)


def _set_password_form(users):
    with st.expander("First time here, or need to set a new password?"):
        st.caption("Use the email and invite code your administrator gave you.")
        email = st.text_input("Email", key="sp_email").strip().lower()
        code = st.text_input("Invite code (if provided)", key="sp_code").strip()
        p1 = st.text_input("New password", type="password", key="sp_p1")
        p2 = st.text_input("Confirm new password", type="password", key="sp_p2")
        if st.button("Set password", key="sp_btn"):
            u = users.get(email)
            if not u:
                st.error("Email not recognized. Contact your administrator.")
            elif u["password_hash"]:
                st.error("This account already has a password. Sign in above, or ask an admin to reset it.")
            elif u["invite_code"] and code != u["invite_code"]:
                st.error("Invalid invite code.")
            elif len(p1) < MIN_PASSWORD_LEN:
                st.error(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
            elif p1 != p2:
                st.error("Passwords do not match.")
            else:
                _write_password(email, _hash(p1))
                st.success("Password set. Please sign in above with your new password.")


def require_login():
    """Render the login form and block until authenticated.

    Returns the authenticator (for logout), or None under local dev bypass.
    """
    if _access("dev_bypass"):
        return None
    creds, users = _load_users()
    authenticator = _build_authenticator(creds)
    authenticator.login(
        location="main",
        max_login_attempts=5,
        fields={"Form name": "UrVenue Analytics — Sign in"},
    )
    status = st.session_state.get("authentication_status")
    if status is True:
        return authenticator
    if status is False:
        st.error("Incorrect email or password.")
    elif status is None:
        st.info("Sign in with your email and password to access your dashboards.")
    _set_password_form(users)
    st.stop()


def current_email():
    if _access("dev_bypass"):
        return None
    return (st.session_state.get("username") or "").strip().lower()


def resolve_tenant(email):
    """Return the customer key for this signed-in email, or None if unauthorized."""
    if _access("dev_bypass"):
        return _access("dev_tenant", "abbaye")
    _, users = _load_users()
    u = users.get((email or "").strip().lower())
    return u["customer"] if u else None


def account_sidebar(authenticator, email):
    """Sidebar: logout + a change-password form for the signed-in user."""
    if authenticator is not None:
        authenticator.logout(location="sidebar")
    if not email:
        return
    _, users = _load_users()
    u = users.get(email)
    with st.sidebar.expander("Change password"):
        cur = st.text_input("Current password", type="password", key="cp_cur")
        n1 = st.text_input("New password", type="password", key="cp_n1")
        n2 = st.text_input("Confirm new password", type="password", key="cp_n2")
        if st.button("Update password", key="cp_btn"):
            if not u or not u["password_hash"]:
                st.error("No password on file for this account.")
            elif not bcrypt.checkpw(cur.encode(), u["password_hash"].encode()):
                st.error("Current password is incorrect.")
            elif len(n1) < MIN_PASSWORD_LEN:
                st.error(f"Password must be at least {MIN_PASSWORD_LEN} characters.")
            elif n1 != n2:
                st.error("Passwords do not match.")
            else:
                _write_password(email, _hash(n1))
                st.success("Password updated.")
