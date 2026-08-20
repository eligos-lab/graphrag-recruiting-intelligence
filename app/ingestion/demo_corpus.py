"""Deterministic, fictional candidates used for a useful local demo."""

from typing import Any

_PROFILES = (
    ("Senior Backend Engineer", "fintech", ("Python", "Postgres", "Kafka"), ("AWS", "Kubernetes")),
    ("Platform Engineer", "cloud", ("Python", "Terraform", "Linux"), ("Kubernetes", "GCP")),
    ("Data Engineer", "retail", ("Python", "SQL", "Spark"), ("Airflow", "Databricks")),
    ("ML Engineer", "healthtech", ("Python", "PyTorch", "MLOps"), ("MLflow", "Kubernetes")),
    (
        "Security Engineer",
        "cybersecurity",
        ("Python", "Threat Modeling", "SIEM"),
        ("AWS", "Terraform"),
    ),
)
_NAMES = (
    "Alex Morgan",
    "Sofia Ivanova",
    "Daniel Kim",
    "Maya Patel",
    "Leo Martin",
    "Elena Smirnova",
    "Noah Williams",
    "Anya Volkova",
    "Sam Chen",
    "Olivia Brown",
)
_LOCATIONS = (
    ("Berlin", "Germany"),
    ("Warsaw", "Poland"),
    ("London", "United Kingdom"),
    ("Amsterdam", "Netherlands"),
    ("Lisbon", "Portugal"),
)


def demo_candidate_records() -> list[dict[str, Any]]:
    """Return 50 fictional, varied resumes; no real people or contact details."""
    records: list[dict[str, Any]] = []
    for index in range(50):
        title, domain, skills, technologies = _PROFILES[index % len(_PROFILES)]
        name = _NAMES[index % len(_NAMES)]
        city, country = _LOCATIONS[index % len(_LOCATIONS)]
        level = "Senior" if index % 3 else "Lead"
        full_name = f"{name} {index + 1:02d}"
        records.append(
            {
                "id": f"demo-{index + 1:03d}",
                "full_name": full_name,
                "location": city,
                "country": country,
                "current_title": title,
                "years_experience": 4 + (index % 12),
                "summary": (
                    f"Fictional demo profile: {level.lower()} {title.lower()} "
                    f"building reliable {domain} products."
                ),
                "skills": list(skills),
                "technologies": list(technologies),
                "domains": [domain],
                "experience": [
                    {
                        "company": f"Demo {domain.title()} Labs",
                        "title": title,
                        "domains": [domain],
                        "technologies": list(technologies),
                    }
                ],
                "projects": [
                    {
                        "name": f"{domain.title()} Delivery Platform",
                        "description": f"A fictional {domain} system for the local demo.",
                        "technologies": list(technologies),
                        "domains": [domain],
                    }
                ],
            }
        )
    return records
