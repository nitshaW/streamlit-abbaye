"""Shared Snowflake session helper for the dashboard pages.

Auth model:
- When deployed *inside* Snowflake (Streamlit-in-Snowflake), reuse the
  active session.
- Locally / in a container, build a Snowpark session from
  ``.streamlit/secrets.toml``. Supports key-pair (JWT) auth via
  ``private_key_file`` (preferred) or password auth via ``password``.
"""
import os

import streamlit as st
from snowflake.snowpark import Session

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_private_key_bytes(key_path):
    """Load a PEM private key and return DER/PKCS8 bytes for the connector."""
    from cryptography.hazmat.primitives import serialization

    if not os.path.isabs(key_path):
        key_path = os.path.join(_HERE, key_path)
    with open(key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None)
    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


@st.cache_resource
def get_session():
    # Running inside Snowflake? Reuse the active session.
    try:
        from snowflake.snowpark.context import get_active_session

        return get_active_session()
    except Exception:
        pass

    cfg = st.secrets["snowflake"]
    pars = {
        "account": cfg["account"],
        "user": cfg["user"],
        "role": cfg["role"],
        "warehouse": cfg["warehouse"],
        "database": cfg["database"],
        "schema": cfg.get("schema", "PUBLIC"),
        "client_session_keep_alive": True,
    }
    if cfg.get("private_key_file"):
        pars["private_key"] = _load_private_key_bytes(cfg["private_key_file"])
    elif cfg.get("password"):
        pars["password"] = cfg["password"]
    return Session.builder.configs(pars).create()
