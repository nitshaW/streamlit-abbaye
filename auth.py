"""Authentication gate for the dashboard.

Uses Streamlit's native OIDC auth (st.login / st.user, requires Streamlit >= 1.42
and Authlib). Sign-in is via the Google OIDC provider configured in the
``[auth]`` section of .streamlit/secrets.toml. Authorization is an email
allowlist in the ``[access]`` section.

Call require_auth() at the top of every page (right after st.set_page_config).
"""
import streamlit as st


def _allowed_emails():
    try:
        emails = st.secrets["access"]["allowed_emails"]
    except Exception:
        emails = []
    return {str(e).strip().lower() for e in emails}


def require_auth():
    """Block the page until the visitor is signed in AND on the allowlist."""
    # 1. Not signed in → show login and stop.
    if not getattr(st.user, "is_logged_in", False):
        st.title("🔒 Sign in required")
        st.write("Please sign in with your Google account to access this dashboard.")
        st.button("Log in with Google", type="primary", on_click=st.login)
        st.stop()

    # 2. Signed in → authorize against the allowlist (empty list = allow any signed-in user).
    email = (st.user.email or "").lower()
    allowed = _allowed_emails()
    if allowed and email not in allowed:
        st.error(f"Access denied for {st.user.email}. Contact an administrator to request access.")
        st.button("Log out", on_click=st.logout)
        st.stop()

    # 3. Authorized → expose identity + logout in the sidebar, then let the page render.
    with st.sidebar:
        st.caption(f"Signed in as {st.user.email}")
        st.button("Log out", on_click=st.logout)
