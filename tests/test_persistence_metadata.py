from app.infrastructure.database import models  # noqa: F401
from app.infrastructure.database.base import Base


def test_phase_one_tables_are_registered() -> None:
    expected_tables = {
        "companies",
        "company_domains",
        "domains",
        "people",
        "person_companies",
        "person_domains",
        "person_projects",
        "person_skills",
        "person_technologies",
        "person_universities",
        "project_domains",
        "project_technologies",
        "projects",
        "raw_documents",
        "skill_aliases",
        "skills",
        "technologies",
        "universities",
    }

    assert set(Base.metadata.tables) == expected_tables


def test_person_university_relationship_targets_correct_entities() -> None:
    table = Base.metadata.tables["person_universities"]
    foreign_key_targets = {foreign_key.target_fullname for foreign_key in table.foreign_keys}

    assert foreign_key_targets == {"people.id", "universities.id"}
