FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py auth.py ./
COPY .streamlit ./.streamlit
COPY img ./img

EXPOSE 8501

# --- SecurityContext: kontener nie dziala jako root ---
RUN useradd -m appuser
USER appuser

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
