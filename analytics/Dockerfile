FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY analytics/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY collector/collect_news.py /app/collect_news.py
COPY analytics /app/analytics
CMD ["python", "-m", "analytics.pipeline"]
