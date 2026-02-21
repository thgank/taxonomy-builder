# Taxonomy Builder

Автоматическое / полуавтоматическое построение таксономии предметной области по коллекции документов.

## Архитектура

```
┌─────────────────┐     ┌──────────┐     ┌─────────────────┐
│   API Service   │────▶│ RabbitMQ │────▶│ Worker Service  │
│  (Spring Boot)  │     └──────────┘     │    (Python)     │
│   port: 8080    │                      │  port: 8081     │
└────────┬────────┘                      └────────┬────────┘
         │                                        │
         └──────────┐    ┌────────────────────────┘
                    ▼    ▼
               ┌──────────────┐
               │  PostgreSQL  │
               │  port: 5432  │
               └──────────────┘
```

### Компоненты

| Сервис | Технологии | Описание |
|--------|-----------|----------|
| **api-service** | Java 21, Spring Boot 3.4, JPA, Flyway | REST API, управление коллекциями, документами, задачами, таксономиями |
| **worker-service** | Python 3.11, pika, spaCy, sentence-transformers | Парсинг документов, NLP, извлечение терминов, построение таксономии |
| **PostgreSQL 16** | | Хранение данных |
| **RabbitMQ 3.13** | | Асинхронная очередь задач |

### Пайплайн обработки

```
Upload docs → IMPORT → NLP → TERMS → BUILD → READY
              (parse)  (lang) (TF-IDF  (Hearst +
                        detect  TextRank) Embeddings)
```

## Быстрый старт

### Предварительные требования

- Docker и Docker Compose
- (опционально) Java 21 + Maven для локальной разработки API
- (опционально) Python 3.11+ для локальной разработки воркера

### Запуск

```bash
# 1. Клонировать и перейти в директорию
cd taxonomy

# 2. Скопировать конфигурацию
cp .env.example .env

# 3. Запустить все сервисы
docker compose up --build -d

# 4. Проверить статус
docker compose ps
docker compose logs -f
```

Сервисы будут доступны:

| Сервис | URL |
|--------|-----|
| API | http://localhost:8080 |
| Swagger UI | http://localhost:8080/swagger-ui.html |
| RabbitMQ UI | http://localhost:15672 (taxonomy/rabbit_secret) |
| Worker Health | http://localhost:8081/health |

## API — Примеры запросов

> Все запросы требуют заголовок `X-API-Key: dev-api-key-change-me`

### 1. Создать коллекцию

```bash
curl -X POST http://localhost:8080/api/collections \
  -H "X-API-Key: dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Финансы",
    "description": "Документы по финансовой тематике"
  }'
```

Ответ:
```json
{
  "id": "a1b2c3d4-...",
  "name": "Финансы",
  "description": "Документы по финансовой тематике",
  "createdAt": "2026-02-19T10:00:00Z",
  "documentCount": 0
}
```

### 2. Загрузить документы

```bash
curl -X POST "http://localhost:8080/api/collections/{COLLECTION_ID}/documents:upload" \
  -H "X-API-Key: dev-api-key-change-me" \
  -F "files=@report1.pdf" \
  -F "files=@report2.docx" \
  -F "files=@article.txt"
```

### 3. Запустить полный пайплайн

```bash
curl -X POST "http://localhost:8080/api/collections/{COLLECTION_ID}/jobs" \
  -H "X-API-Key: dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "FULL_PIPELINE",
    "params": {
      "method_term_extraction": "both",
      "method_taxonomy": "hybrid",
      "max_terms": 200,
      "min_freq": 2,
      "similarity_threshold": 0.55,
      "chunk_size": 1000
    }
  }'
```

### 4. Проверить статус задачи

```bash
curl "http://localhost:8080/api/jobs/{JOB_ID}" \
  -H "X-API-Key: dev-api-key-change-me"
```

Ответ:
```json
{
  "id": "...",
  "collectionId": "...",
  "taxonomyVersionId": "...",
  "type": "FULL_PIPELINE",
  "status": "RUNNING",
  "progress": 45,
  "createdAt": "...",
  "startedAt": "..."
}
```

### 5. Посмотреть события задачи

```bash
curl "http://localhost:8080/api/jobs/{JOB_ID}/events" \
  -H "X-API-Key: dev-api-key-change-me"
```

### 6. Получить дерево таксономии

```bash
curl "http://localhost:8080/api/taxonomies/{TAX_VERSION_ID}/tree" \
  -H "X-API-Key: dev-api-key-change-me"
```

Ответ:
```json
{
  "taxonomyVersionId": "...",
  "roots": [
    {
      "conceptId": "...",
      "label": "finance",
      "score": 0.95,
      "children": [
        {
          "conceptId": "...",
          "label": "banking",
          "score": 0.87,
          "children": [...]
        }
      ]
    }
  ]
}
```

### 7. Поиск термина

```bash
curl "http://localhost:8080/api/taxonomies/{TAX_ID}/concepts/search?q=bank" \
  -H "X-API-Key: dev-api-key-change-me"
```

### 8. Карточка термина (с evidence)

```bash
curl "http://localhost:8080/api/taxonomies/{TAX_ID}/concepts/{CONCEPT_ID}" \
  -H "X-API-Key: dev-api-key-change-me"
```

Ответ:
```json
{
  "id": "...",
  "canonical": "commercial bank",
  "surfaceForms": ["commercial bank", "commercial banks"],
  "lang": "en",
  "score": 0.82,
  "parents": [
    {"id": "...", "canonical": "bank", "edgeScore": 0.91}
  ],
  "children": [
    {"id": "...", "canonical": "savings bank", "edgeScore": 0.75}
  ],
  "occurrences": [
    {
      "chunkId": "...",
      "documentId": "...",
      "snippet": "...a commercial bank provides financial services...",
      "confidence": 0.8
    }
  ]
}
```

### 9. Экспорт таксономии

```bash
# JSON
curl "http://localhost:8080/api/taxonomies/{TAX_ID}:export?format=json" \
  -H "X-API-Key: dev-api-key-change-me"

# CSV
curl "http://localhost:8080/api/taxonomies/{TAX_ID}:export?format=csv" \
  -H "X-API-Key: dev-api-key-change-me" \
  -o taxonomy.csv
```

### 10. Ручное редактирование (semi-auto)

```bash
# Добавить ребро
curl -X POST "http://localhost:8080/api/taxonomies/{TAX_ID}/edges" \
  -H "X-API-Key: dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "parentConceptId": "...",
    "childConceptId": "...",
    "relation": "is_a",
    "score": 1.0
  }'

# Обновить score / пометить approved
curl -X PATCH "http://localhost:8080/api/taxonomies/{TAX_ID}/edges/{EDGE_ID}" \
  -H "X-API-Key: dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"score": 0.95, "approved": true}'

# Удалить ребро
curl -X DELETE "http://localhost:8080/api/taxonomies/{TAX_ID}/edges/{EDGE_ID}" \
  -H "X-API-Key: dev-api-key-change-me"
```

## Методы построения таксономии

### Извлечение терминов

| Метод | Описание |
|-------|----------|
| **TF-IDF** | Статистический: TF-IDF по noun phrases и n-grams (1–3), фильтрация по частоте |
| **TextRank** | Граф-based: co-occurrence graph + PageRank итерации |
| **both** (default) | Взвешенное объединение обоих методов (α=0.6 для TF-IDF) |

### Построение иерархии

| Метод | Описание |
|-------|----------|
| **hearst** | Rule-based: Hearst patterns ("X such as Y", "такие как" и др.) |
| **embedding** | Sentence embeddings + HDBSCAN кластеризация + parent selection |
| **hybrid** (default) | Комбинация обоих методов с дедупликацией |

### Пост-обработка

- Удаление циклов (DFS cycle detection + разрыв слабейших рёбер)
- Ограничение глубины (`max_depth`, default=6)
- Дедупликация терминов (rapidfuzz, threshold=85%)
- Версионирование: каждая сборка = новая `taxonomy_version`

## Конфигурация

Все параметры передаются через `params` при создании задачи и сохраняются в `taxonomy_versions.parameters`:

| Параметр | Тип | Default | Описание |
|----------|-----|---------|----------|
| `method_term_extraction` | string | `both` | `tfidf` / `textrank` / `both` |
| `method_taxonomy` | string | `hybrid` | `hearst` / `embedding` / `hybrid` |
| `max_terms` | int | `500` | Максимальное число терминов |
| `min_freq` | int | `2` | Минимальная частота термина |
| `similarity_threshold` | float | `0.55` | Порог cosine similarity для embedding |
| `fuzz_threshold` | int | `85` | Порог rapidfuzz для дедупликации |
| `chunk_size` | int | `1000` | Размер чанка в символах |
| `max_depth` | int | `6` | Максимальная глубина дерева |

## Структура проекта

```
taxonomy/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
│
├── api-service/                     # Java Spring Boot API
│   ├── Dockerfile
│   ├── pom.xml
│   └── src/main/
│       ├── java/com/taxonomy/api/
│       │   ├── TaxonomyApiApplication.java
│       │   ├── config/              # Security, RabbitMQ, OpenAPI
│       │   ├── controller/          # REST controllers
│       │   ├── dto/                 # Request/Response DTOs
│       │   ├── entity/              # JPA entities + enums
│       │   ├── exception/           # Error handling
│       │   ├── messaging/           # RabbitMQ publisher
│       │   ├── repository/          # JPA repositories
│       │   └── service/             # Business logic
│       └── resources/
│           ├── application.yml
│           └── db/migration/        # Flyway SQL migrations
│
└── worker-service/                  # Python workers
    ├── Dockerfile
    ├── requirements.txt
    ├── app/
    │   ├── main.py                  # Entry point
    │   ├── config.py                # Configuration
    │   ├── db.py                    # SQLAlchemy models
    │   ├── logger.py                # JSON structured logging
    │   ├── consumer.py              # RabbitMQ consumer
    │   ├── health.py                # FastAPI health endpoint
    │   ├── job_helper.py            # Job status updates
    │   └── pipeline/
    │       ├── ingestion.py         # PDF/DOCX/HTML/TXT → chunks
    │       ├── nlp.py               # Language detection
    │       ├── term_extraction.py   # TF-IDF + TextRank
    │       └── taxonomy_builder.py  # Hearst + Embeddings
    └── tests/
        ├── test_ingestion.py
        ├── test_term_extraction.py
        └── test_taxonomy_builder.py
```

## Запуск тестов

### Java API

```bash
cd api-service
mvn test
```

### Python Workers

```bash
cd worker-service
pip install -r requirements.txt
pytest tests/ -v
```

## Языковая поддержка

| Язык | NLP (spaCy) | Hearst Patterns | Embedding |
|------|-------------|-----------------|-----------|
| English | ✅ `en_core_web_sm` | ✅ | ✅ (multilingual) |
| Русский | ✅ `ru_core_news_sm` | ✅ | ✅ (multilingual) |
| Қазақ | ⚠️ токенизация только | ⚠️ ограниченно | ✅ (multilingual) |

## Лицензия

Проект разработан в рамках диссертационного исследования.
# taxonomy-builder
