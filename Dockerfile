FROM python:3.11-slim

# Set working directory for copying, etc
WORKDIR /app

# Copy over requirements
COPY requirements.txt /app

# Install dependencies
RUN apt-get update \
    && apt-get install -y build-essential \
    && pip install -r requirements.txt \
    && pip cache purge \
    && apt-get purge -y --auto-remove build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy over server script
COPY server.py /app

# Run application
EXPOSE 8675
CMD ["python", "/app/server.py"]
