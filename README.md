# GraphRAG Recruiting Intelligence

Evidence-first AI-система для поиска и анализа кандидатов по заранее загруженному корпусу.
LLM не является базой знаний: факты о кандидатах будут поступать только из PostgreSQL,
pgvector и Neo4j.

## Текущий статус

Реализован только **Phase 1**:

- FastAPI-приложение и versioned API;
- async SQLAlchemy 2 и PostgreSQL;
- независимые доменные сущности и отдельные ORM-модели;
- основные relational-сущности и связи knowledge graph;
- Alembic и первая миграция;
- проверка доступности API и базы данных;
- Docker Compose для API и PostgreSQL (образ уже совместим с будущим pgvector);
- pytest, Ruff и mypy.

Ingestion, embeddings, Neo4j, Redis, Celery и LLM-интеграции намеренно отложены до
соответствующих фаз.

## Структура

```text
app/
├── api/                         # FastAPI routers и HTTP handlers
├── domain/                      # Независимые бизнес-сущности
├── infrastructure/database/     # SQLAlchemy models, engine, sessions
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

Проверки:

```bash
pytest
ruff check .
ruff format --check .
mypy app
```

## Архитектурные решения Phase 1

- UUID используются как стабильные идентификаторы для последующей синхронизации с графом.
- Domain dataclasses не зависят от SQLAlchemy; persistence-модели находятся в infrastructure.
- `(source, source_id)` уникален для человека и закладывает основу idempotent ingestion.
- Связи knowledge graph представлены явными many-to-many таблицами, без Neo4j driver calls.
- `GET /api/v1/health` возвращает `503/degraded`, если PostgreSQL недоступен.
- Размер embeddings, LLM providers и graph repositories не вводятся раньше Phase 3–5.

## Следующая фаза

Phase 2 добавит canonical resume schema, raw documents, CSV/JSON adapters, нормализацию,
alias resolution, persistence pipeline и тесты idempotency. Она не входит в текущую реализацию.
