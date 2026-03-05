FROM python:3.10-slim-bullseye

WORKDIR /app

# Install system dependencies
RUN set -eux; \
    for i in 1 2 3 4 5; do \
      apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 && break; \
      if [ "$i" -eq 5 ]; then exit 1; fi; \
      rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*; \
      sleep 5; \
    done; \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p /tmp/uploads /tmp/outputs

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
