import json
from pathlib import Path

from app.ingestion.parsers.structured import StructuredFieldMapping, StructuredResumeParser
from app.ingestion.schemas import DocumentType, SourceDocument
from app.ingestion.sources import CsvResumeSource, JsonResumeSource


def test_csv_source_and_parser_create_canonical_resume(tmp_path: Path) -> None:
    path = tmp_path / "candidates.csv"
    path.write_text(
        "id,full_name,country,skills,technologies,years_experience\n"
        "candidate-1,Ada Lovelace,UK,Python; PostgreSQL,AWS; Kubernetes,8\n",
        encoding="utf-8",
    )

    document = next(CsvResumeSource(path, source_name="fixture-csv").iter_documents())
    resume = StructuredResumeParser().parse(document)

    assert document.external_id == "candidate-1"
    assert resume.skills == ["Python", "PostgreSQL"]
    assert resume.technologies == ["AWS", "Kubernetes"]
    assert resume.years_experience == 8


def test_json_source_supports_records_wrapper_and_nested_sections(tmp_path: Path) -> None:
    path = tmp_path / "candidates.json"
    path.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "id": "candidate-2",
                        "full_name": "Grace Hopper",
                        "country": "United States",
                        "experience": [{"company": "US Navy", "title": "Rear Admiral"}],
                        "projects": [{"name": "Compiler", "technologies": ["COBOL"]}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    document = next(JsonResumeSource(path, source_name="fixture-json").iter_documents())
    resume = StructuredResumeParser().parse(document)

    assert resume.experience[0].company == "US Navy"
    assert resume.projects[0].technologies == ["COBOL"]


def test_parser_supports_dataset_specific_nested_field_mapping() -> None:
    document = SourceDocument(
        source="custom",
        external_id="candidate-3",
        document_type=DocumentType.JSON,
        raw_text="{}",
        payload={"profile": {"display_name": "Margaret Hamilton", "nation": "US"}},
    )
    parser = StructuredResumeParser(
        StructuredFieldMapping(
            full_name="profile.display_name",
            country="profile.nation",
        )
    )

    resume = parser.parse(document)

    assert resume.full_name == "Margaret Hamilton"
    assert resume.country == "US"
