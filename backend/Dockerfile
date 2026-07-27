FROM python:3.10-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Upgrade pip and install lightweight CPU-only PyTorch
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Copy requirements and install Python packages
COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase and Alembic migrations
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini

# Create data & static directories for persistence
RUN mkdir -p /app/scripts /app/static/reports /app/faiss_data

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head || true; uvicorn app.main:app --host 0.0.0.0 --port 8000"]
