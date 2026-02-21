FROM python:3.11-slim

WORKDIR /app

# System deps for lxml, psycopg2, hdbscan
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ libpq-dev libxml2-dev libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy models
ARG SPACY_MODEL_EN=en_core_web_sm
ARG SPACY_MODEL_RU=ru_core_news_sm
RUN python -m spacy download ${SPACY_MODEL_EN} && \
    python -m spacy download ${SPACY_MODEL_RU}

COPY . .

RUN addgroup --system app && adduser --system --ingroup app app
RUN mkdir -p /data/uploads && chown -R app:app /data/uploads
USER app

# Start both health server and worker consumer
CMD ["python", "-m", "app.main"]
