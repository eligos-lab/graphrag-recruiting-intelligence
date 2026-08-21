# ruff: noqa: E501, RUF001
"""Deterministic, fictional but resume-shaped candidates for local demos."""

from typing import Any

_PROFILES = (
    ("Senior Python Backend Engineer", "fintech", ("Python", "PostgreSQL", "Kafka"), ("FastAPI", "Docker", "Kubernetes")),
    ("Platform Engineer", "cloud", ("Python", "Terraform", "Linux"), ("Kubernetes", "GCP", "Argo CD")),
    ("Data Engineer", "retail", ("Python", "SQL", "Spark"), ("Airflow", "ClickHouse", "Databricks")),
    ("ML Engineer", "healthtech", ("Python", "PyTorch", "MLOps"), ("MLflow", "Kubernetes", "Docker")),
    ("Security Engineer", "cybersecurity", ("Python", "Threat Modeling", "SIEM"), ("AWS", "Terraform", "Kubernetes")),
)
_NAMES = (
    "Анна Воронцова", "Илья Морозов", "София Белова", "Даниил Орлов", "Мария Жукова",
    "Артём Соколов", "Елена Крылова", "Никита Волков", "Полина Лебедева", "Максим Громов",
)
_LOCATIONS = (
    ("Москва", "Россия"), ("Санкт-Петербург", "Россия"), ("Казань", "Россия"),
    ("Екатеринбург", "Россия"), ("Новосибирск", "Россия"),
)
_COMPANIES = ("МТС", "Яндекс", "Ozon", "VK", "Альфа-Банк", "Авито", "Т-Банк")
_TRAITS = (
    "Коммуникативный и внимательный к договорённостям: спокойно объясняет сложные решения бизнесу и команде.",
    "Ответственный инженер: доводит задачи до результата, заранее сообщает о рисках и держит слово.",
    "Формальный и аккуратный в процессах: документирует решения, соблюдает SLA и любит прозрачные правила.",
    "Самостоятельный и доброжелательный: умеет давать обратную связь и поддерживать коллег в сложных релизах.",
    "Ориентирован на результат: декомпозирует неопределённые задачи и проверяет гипотезы через метрики.",
)


def demo_candidate_records() -> list[dict[str, Any]]:
    """Return 50 varied, fictional profiles without real contact details."""
    records: list[dict[str, Any]] = []
    for index in range(50):
        title, domain, skills, technologies = _PROFILES[index % len(_PROFILES)]
        city, country = _LOCATIONS[index % len(_LOCATIONS)]
        company = _COMPANIES[index % len(_COMPANIES)]
        previous_company = _COMPANIES[(index + 3) % len(_COMPANIES)]
        traits = _TRAITS[index % len(_TRAITS)]
        years = 3 + index % 11
        records.append(
            {
                "id": f"demo-{index + 1:03d}",
                "full_name": _NAMES[index % len(_NAMES)],
                "location": city,
                "country": country,
                "age": 22 + index % 18,
                "current_title": title,
                "years_experience": years,
                "summary": (
                    f"О себе: {traits} {years} лет в разработке {domain}-продуктов. "
                    "Предпочитает командную работу, понятные процессы и качественный результат."
                ),
                "skills": list(skills),
                "technologies": list(technologies),
                "domains": [domain],
                "experience": [
                    {
                        "company": company,
                        "title": title,
                        "start_date": f"{2021 + index % 3}-03",
                        "end_date": None,
                        "description": (
                            f"Развивает {domain}-платформу, участвует в планировании, "
                            "ревью кода и коммуникации с продуктовой командой."
                        ),
                        "domains": [domain],
                        "technologies": list(technologies),
                    },
                    {
                        "company": previous_company,
                        "title": "Software Engineer",
                        "start_date": f"{2018 + index % 3}-06",
                        "end_date": f"{2021 + index % 3}-02",
                        "description": (
                            "Работал над внутренними сервисами, автоматизацией процессов "
                            "и надёжностью поставки изменений."
                        ),
                        "domains": [domain],
                        "technologies": list(technologies[:2]),
                    },
                ],
                "projects": [
                    {
                        "name": f"{domain.title()} Delivery Platform",
                        "description": (
                            "Сервисная платформа с наблюдаемостью, документацией и "
                            "предсказуемыми процессами выпуска."
                        ),
                        "technologies": list(technologies),
                        "domains": [domain],
                    }
                ],
            }
        )
    return records
