FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

RUN mkdir -p /app/data
EXPOSE 8766

CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8766"]
