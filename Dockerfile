# UrVenue multi-tenant analytics dashboard.
# Built on the shared Streamlit base image in GCP Artifact Registry:
#   us-central1-docker.pkg.dev/urvenue-social/urvenue-streamlit/base:v1.0
#
# Secrets are NEVER baked into the image — infra mounts them at runtime (see below).
FROM us-central1-docker.pkg.dev/urvenue-social/urvenue-streamlit/base:v1.0

WORKDIR /app

# App dependencies on top of the base (Streamlit auth, Snowflake connector/snowpark,
# bcrypt, and cryptography <43). Installing the pinned set from
# requirements.txt guarantees the versions the app was verified against win.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code + the committed Streamlit config.
# NOT copied: .streamlit/secrets.toml and *.pem (see .dockerignore) — mounted at runtime.
COPY Main.py auth.py tenants.py views.py sf_session.py ./
COPY scripts ./scripts
COPY .streamlit/config.toml ./.streamlit/config.toml

# Credentials are provided at runtime — NEVER baked into the image. Two options
# (env vars win over secrets.toml for any given setting):
#
#  A) INF-200 pattern — env vars + a mounted key (matches the shared base):
#       SNOWFLAKE_ACCOUNT/_USER/_ROLE/_WAREHOUSE/_DATABASE/_SCHEMA
#       key mounted read-only at /run/secrets/rsa_key.p8
#         (or SNOWFLAKE_PRIVATE_KEY_PATH; SNOWFLAKE_PRIVATE_KEY_PASSPHRASE if encrypted)
#       COOKIE_KEY (session-cookie signing secret), optional COOKIE_NAME/COOKIE_EXPIRY_DAYS
#     docker run -p 8501:8501 --env-file /secure/app.env \
#       -v /secure/rsa_key.p8:/run/secrets/rsa_key.p8:ro  <image>
#
#  B) Mounted secrets.toml (as local dev):
#     docker run -p 8501:8501 \
#       -v /secure/secrets.toml:/app/.streamlit/secrets.toml:ro \
#       -v /secure/svc_reports_key_1.pem:/app/svc_reports_key_1.pem:ro  <image>
#
# In production do NOT set dev_bypass — login is required.

EXPOSE 8501

# Liveness via Streamlit's health endpoint (python — no curl dependency assumed).
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health').read()" || exit 1

# 0.0.0.0 so the container is reachable behind the proxy (config.toml also sets port+headless).
CMD ["streamlit", "run", "Main.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
