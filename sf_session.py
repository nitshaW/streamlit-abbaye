"""Shared Snowflake session helper for the dashboard pages.

Auth model (first match wins):
1. Streamlit-in-Snowflake — reuse the active session.
2. Hosted container (INF-200 pattern) — config from environment variables
   (``SNOWFLAKE_ACCOUNT``/``_USER``/``_ROLE``/``_WAREHOUSE``/``_DATABASE``/``_SCHEMA``)
   and a key-pair private key mounted read-only at ``SNOWFLAKE_PRIVATE_KEY_PATH``
   (default ``/run/secrets/rsa_key.p8``), optionally passphrase-protected via
   ``SNOWFLAKE_PRIVATE_KEY_PASSPHRASE``.
3. Local dev — ``.streamlit/secrets.toml`` ``[snowflake]`` section
   (``private_key_file`` for key-pair, or ``password``).

Environment variables always take precedence over ``secrets.toml`` for the same
setting, so the same image runs locally and in the container without code changes.
"""
import os

import streamlit as st
from snowflake.snowpark import Session

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_KEY_PATH = "/run/secrets/rsa_key.p8"   # INF-200 mount point


def _secrets():
    """The [snowflake] secrets section, or {} if no secrets.toml is present."""
    try:
        return dict(st.secrets.get("snowflake", {}))
    except Exception:
        return {}


def _val(env_key, sec, sec_key, default=None):
    """Env var wins, then secrets.toml, then default."""
    return os.environ.get(env_key) or sec.get(sec_key) or default


def _load_private_key_bytes(key_path, passphrase=None):
    """Load a PEM private key (optionally passphrase-protected) -> DER/PKCS8 bytes."""
    from cryptography.hazmat.primitives import serialization

    if not os.path.isabs(key_path):
        key_path = os.path.join(_HERE, key_path)
    pw = passphrase.encode() if passphrase else None
    with open(key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=pw)
    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _resolve_key_path(sec):
    """Key path: env var, then secrets.toml, then the mounted default if it exists."""
    return (
        os.environ.get("SNOWFLAKE_PRIVATE_KEY_PATH")
        or sec.get("private_key_file")
        or (_DEFAULT_KEY_PATH if os.path.exists(_DEFAULT_KEY_PATH) else None)
    )


@st.cache_resource
def get_session():
    # 1. Running inside Snowflake? Reuse the active session.
    try:
        from snowflake.snowpark.context import get_active_session

        return get_active_session()
    except Exception:
        pass

    sec = _secrets()
    account = _val("SNOWFLAKE_ACCOUNT", sec, "account")
    user = _val("SNOWFLAKE_USER", sec, "user")
    if not account or not user:
        raise RuntimeError(
            "Snowflake config missing: set SNOWFLAKE_ACCOUNT/SNOWFLAKE_USER "
            "(and key/password) via env vars or .streamlit/secrets.toml."
        )

    pars = {
        "account": account,
        "user": user,
        "role": _val("SNOWFLAKE_ROLE", sec, "role"),
        "warehouse": _val("SNOWFLAKE_WAREHOUSE", sec, "warehouse"),
        "database": _val("SNOWFLAKE_DATABASE", sec, "database"),
        "schema": _val("SNOWFLAKE_SCHEMA", sec, "schema", "PUBLIC"),
        "client_session_keep_alive": True,
    }

    key_path = _resolve_key_path(sec)
    password = _val("SNOWFLAKE_PASSWORD", sec, "password")
    if key_path:  # key-pair (JWT) preferred
        passphrase = _val("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", sec, "private_key_passphrase")
        pars["private_key"] = _load_private_key_bytes(key_path, passphrase)
    elif password:
        pars["password"] = password
    else:
        raise RuntimeError(
            "No Snowflake credential: provide a key-pair (SNOWFLAKE_PRIVATE_KEY_PATH / "
            "/run/secrets/rsa_key.p8 / secrets private_key_file) or a password."
        )

    return Session.builder.configs({k: v for k, v in pars.items() if v is not None}).create()
