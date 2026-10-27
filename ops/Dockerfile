# One image for the API and the MCP server (docker compose runs it twice with different commands).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr ffmpeg libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/app

COPY requirements.txt .
RUN pip install -r requirements.txt && python -m spacy download en_core_web_sm

COPY app ./app
COPY mcp_server ./mcp_server
COPY scripts ./scripts
COPY templates ./templates
COPY starter_kit ./starter_kit
COPY ops/entrypoint.sh ./ops/entrypoint.sh
RUN chmod +x ./ops/entrypoint.sh && mkdir -p /data

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 CMD curl -fsS http://localhost:8000/health || exit 1
ENTRYPOINT ["./ops/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
