FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app
RUN pip install -r requirements.txt

COPY server.py /app

EXPOSE 8675
CMD ["python", "/app/server.py"]
