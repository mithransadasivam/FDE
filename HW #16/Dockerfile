# Day 15: the chatbot service as a container image.
#
#   docker build -t helpdesk-chatbot .
#   docker run --rm -p 8000:8000 -e CHAT_FAKE=1 helpdesk-chatbot      (the fake chatbot)
#   docker compose up -d --build                                      (the real one, with Phoenix)
#
# Build the index on your laptop first (python -m scripts.build_index_vision): the image copies
# data/, including the index in data/chroma. Secrets never go into the image: the API key arrives
# as an environment variable when the container starts (from .env, through docker-compose.yml).

# 1. Start from a small, official Python image, pinned to one version
FROM python:3.12-slim

# 2. Python settings for containers: no .pyc files, print logs straight away
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 3. Install the libraries first: Docker reuses this layer until requirements-api.txt changes
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# 4. Then copy the code and the data (the index), which change more often
COPY app/ app/
COPY data/ data/

# 5. Run as an ordinary user, not root
RUN useradd --create-home chatbot && mkdir -p logs cache && chown -R chatbot /app
USER chatbot

EXPOSE 8000

# 6. Docker asks /health every 30 seconds; three failures in a row mark the container unhealthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)"

# 7. Start the API on all network interfaces, so the port can be published outside the container
CMD ["uvicorn", "app.api:api", "--host", "0.0.0.0", "--port", "8000"]
