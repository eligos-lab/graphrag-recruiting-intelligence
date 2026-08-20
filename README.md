# GraphRAG Recruiting Intelligence

Evidence-first AI-система для поиска и анализа кандидатов по заранее загруженному корпусу.
LLM не является базой знаний: факты о кандидатах будут поступать только из PostgreSQL,
pgvector и Neo4j.

## Текущий статус

Реализованы **Phase 1–2**:

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

PDF/LLM extraction, embeddings, Neo4j, Redis и Celery намеренно отложены до соответствующих
фаз.

## Структура

```text
app/
├── api/                         # FastAPI routers и HTTP handlers
├── domain/                      # Независимые бизнес-сущности
├── ingestion/                   # Sources, parsing, normalization, pipeline
├── infrastructure/database/     # SQLAlchemy models, engine, sessions
├── repositories/                # Ingestion persistence operations
├── schemas/                     # Pydantic API contracts
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

Проверки:

```bash
pytest
ruff check .
ruff format --check .
mypy app
```

## Архитектурные решения Phase 1–2

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
- Размер embeddings, LLM providers и graph repositories не вводятся раньше Phase 3–5.

## Следующая фаза

Phase 3 добавит section-aware chunks, provider abstraction для embeddings, таблицу vectors с
настраиваемой размерностью и pgvector index. Она не входит в текущую реализацию.
