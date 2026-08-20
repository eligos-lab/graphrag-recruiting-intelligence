# GraphRAG Recruiting Intelligence

Evidence-first AI-система для поиска и анализа кандидатов по заранее загруженному корпусу.
LLM не является базой знаний: факты о кандидатах будут поступать только из PostgreSQL,
pgvector и Neo4j.

## Текущий статус

Реализованы **Phase 1–3**:

- FastAPI-приложение и versioned API;
- async SQLAlchemy 2 и PostgreSQL;
- независимые доменные сущности и отдельные ORM-модели;
- основные relational-сущности и связи knowledge graph;
- Alembic и первая миграция;
- проверка доступности API и базы данных;
- Docker Compose для API и PostgreSQL (образ уже совместим с будущим pgvector);
- pytest, Ruff и mypy;
- canonical resume schema для structured datasets;
- адаптеры CSV, JSON и JSONL;
- raw document layer с checksum и исходным текстом;
- deterministic normalization и aliases для PostgreSQL/AWS/Kubernetes и других имён;
- entity resolution по source identity, checksum и безопасному normalized identity;
- idempotent persistence кандидатов и связанных сущностей;
- CLI для ingestion и синтетический dataset.
- semantic/section-aware chunking по summary, experience, projects, education и skills;
- evidence metadata с ID кандидата, документа и связанных компаний;
- vendor-neutral `EmbeddingProvider` и рабочий OpenAI adapter;
- batched embeddings с проверкой количества, размерности и конечности значений;
- таблица `document_chunks`, pgvector и HNSW cosine index;
- идемпотентный embedding pipeline, не вызывающий API для неизменённых чанков;
- CLI для генерации и обновления embeddings.

PDF/LLM extraction, query understanding, retrieval, Neo4j, Redis и Celery намеренно отложены
до соответствующих фаз.

## Структура

```text
app/
├── api/                         # FastAPI routers и HTTP handlers
├── domain/                      # Независимые бизнес-сущности
├── ingestion/                   # Sources, parsing, chunking и pipelines
├── infrastructure/database/     # SQLAlchemy models, engine, sessions
├── llm/                         # Vendor-neutral contracts и adapters
├── repositories/                # Ingestion и chunk persistence operations
├── schemas/                     # Pydantic API contracts
├── services/                    # Embedding orchestration и validation
├── config.py                    # Typed environment settings
└── main.py                      # Application factory
alembic/                         # Database migrations
tests/                           # Unit/API/metadata tests
compose.yaml                     # Local API + PostgreSQL environment
Dockerfile
pyproject.toml
```

## Запуск через Docker

Требуются Docker и Docker Compose v2.

```bash
docker compose up --build
```

После старта:

- OpenAPI: <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/v1/health>

API-контейнер применяет `alembic upgrade head` перед запуском Uvicorn.

Загрузка синтетического набора данных в PostgreSQL:

```bash
docker compose run --rm api sh -c \
  "alembic upgrade head && python -m app.ingestion.cli /data/sample_candidates.json \
  --source-name sample"
```

Команда возвращает JSON-отчёт с количеством созданных, обновлённых, пропущенных и ошибочных
документов. Повторный запуск не создаёт дубли.

Для embeddings скопируйте `.env.example` в локальный `.env`, задайте там
`GRAPHRAG_EMBEDDING_API_KEY`, затем запустите:

```bash
docker compose run --rm api sh -c \
  "alembic upgrade head && python -m app.ingestion.embed_cli"
```

Повторный запуск пропускает документы, если содержимое чанков и embedding model не изменились.
Ключ не сохраняется в БД и не должен попадать в Git.

Остановка с сохранением данных:

```bash
docker compose down
```

## Локальная разработка

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
cp .env.example .env       # Windows PowerShell: Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Локальный ingestion после применения миграций:

```bash
python -m app.ingestion.cli data/sample_candidates.json --source-name sample
```

Генерация embeddings после ingestion:

```bash
# Сначала задайте GRAPHRAG_EMBEDDING_API_KEY в .env
python -m app.ingestion.embed_cli
```

Проверки:

```bash
pytest
ruff check .
ruff format --check .
mypy app
```

## Архитектурные решения Phase 1–3

- UUID используются как стабильные идентификаторы для последующей синхронизации с графом.
- Domain dataclasses не зависят от SQLAlchemy; persistence-модели находятся в infrastructure.
- `(source, source_id)` уникален для человека и закладывает основу idempotent ingestion.
- Связи knowledge graph представлены явными many-to-many таблицами, без Neo4j driver calls.
- `GET /api/v1/health` возвращает `503/degraded`, если PostgreSQL недоступен.
- Raw document уникален по `(source, external_id)`, а checksum отсекает копии между sources.
- Normalized identity используется только при наличии country и единственном совпадении;
  name-only matching запрещён как слишком рискованный.
- Alias сохраняется отдельно от canonical skill, поэтому исходные варианты не теряются.
- Обновление кандидата объединяет знания из загруженных документов. Удаление устаревших
  связей потребует provenance на relationship edges в будущем расширении модели.
- Чанки сохраняют semantic section и evidence metadata; фиксированная нарезка всего резюме
  по N символов не используется.
- Бизнес-логика зависит от `EmbeddingProvider`, а OpenAI изолирован в infrastructure adapter.
- Размерность embeddings задаётся конфигурацией и согласована между provider validation,
  ORM-моделью и Alembic migration.
- HNSW индекс использует cosine distance; фактические данные кандидатов остаются в PostgreSQL.
- Тестовый deterministic provider существует только в automated tests и не выдаётся за AI.

## Следующая фаза

Phase 4 добавит Pydantic-схему `CandidateSearchIntent`, преобразование natural-language запроса
через validated structured output, безопасный query planner, structured PostgreSQL filtering и
pgvector retrieval с evidence-ссылками.
