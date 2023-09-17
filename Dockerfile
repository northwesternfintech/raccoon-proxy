FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y build-essential

WORKDIR /app

COPY requirements.txt /app
RUN pip install -r requirements.txt

COPY server.py /app

EXPOSE 8675
CMD ["python", "/app/server.py"]
