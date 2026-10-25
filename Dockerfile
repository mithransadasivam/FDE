# One image for the API and the Streamlit screen. The API key is never in the image: it comes from the environment at run time.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt && python -m spacy download en_core_web_sm

COPY tower ./tower
COPY ui ./ui
COPY scripts ./scripts
COPY data/*.csv data/*.json ./data/
COPY docs ./docs
COPY governance ./governance
COPY pytest.ini ./

RUN useradd --create-home tower && mkdir -p /app/state /app/logs /app/reports && chown -R tower /app
USER tower

ENV TOWER_DB=/app/state/tower.db
EXPOSE 8000 8501
HEALTHCHECK --interval=15s --timeout=4s --retries=5 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status == 200 else 1)"
CMD ["uvicorn", "tower.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
