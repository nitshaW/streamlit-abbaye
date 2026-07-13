# UrVenue multi-tenant analytics dashboard.
# Built on the shared Streamlit base image in GCP Artifact Registry:
#   us-central1-docker.pkg.dev/urvenue-social/urvenue-streamlit/base:v1.0
#
# Secrets are NEVER baked into the image — infra mounts them at runtime (see below).
FROM us-central1-docker.pkg.dev/urvenue-social/urvenue-streamlit/base:v1.0

WORKDIR /app

# App dependencies on top of the base (Streamlit auth, Snowflake connector/snowpark,
# bcrypt, and the pinned cryptography==42.0.8). Installing the pinned set from
# requirements.txt guarantees the versions the app was verified against win.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code + the committed Streamlit config.
# NOT copied: .streamlit/secrets.toml and *.pem (see .dockerignore) — mounted at runtime.
COPY Main.py auth.py tenants.py views.py sf_session.py ./
COPY scripts ./scripts
COPY .streamlit/config.toml ./.streamlit/config.toml

# Runtime-mounted secrets (provided by infra — never in the image):
#   /app/.streamlit/secrets.toml   [snowflake] [cookie] [access]  (dev_bypass OFF in prod)
#   /app/svc_reports_key_1.pem     key-pair private key referenced by secrets.toml
# Example:
#   docker run -p 8501:8501 \
#     -v /secure/secrets.toml:/app/.streamlit/secrets.toml:ro \
#     -v /secure/svc_reports_key_1.pem:/app/svc_reports_key_1.pem:ro  <image>

EXPOSE 8501

# Liveness via Streamlit's health endpoint (python — no curl dependency assumed).
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health').read()" || exit 1

# 0.0.0.0 so the container is reachable behind the proxy (config.toml also sets port+headless).
CMD ["streamlit", "run", "Main.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
