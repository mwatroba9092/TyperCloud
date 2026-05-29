FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker.py .

# --- SecurityContext: kontener nie dziala jako root ---
RUN useradd -m appuser
USER appuser

CMD ["python", "worker.py"]
