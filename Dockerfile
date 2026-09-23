FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY rayabot ./rayabot
COPY data/ai_datasets ./data/ai_datasets
COPY config.json main.py ./

RUN mkdir -p /app/data /app/logs
EXPOSE 8000
CMD ["python", "main.py"]
