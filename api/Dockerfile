FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies in layered stages to avoid BuildKit memory crashes
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --default-timeout=1000 --no-cache-dir \
    fastapi uvicorn pydantic sqlalchemy httpx websockets redis

RUN pip install --default-timeout=1000 --no-cache-dir \
    pandas numpy joblib scikit-learn xgboost lightgbm imbalanced-learn shap

# Copy source directories
COPY api/ /app/api
COPY model/ /app/model
COPY data/ /app/data

EXPOSE 8000

# Run FastAPI app
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
