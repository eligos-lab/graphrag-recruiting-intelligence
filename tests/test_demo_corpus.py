from app.ingestion.demo_corpus import demo_candidate_records


def test_demo_corpus_contains_fifty_individual_resumes() -> None:
    records = demo_candidate_records()

    assert len(records) == 50
    assert len({record["full_name"] for record in records}) == 50
    assert len({record["summary"] for record in records}) == 50
    assert all(record["age"] for record in records)
    assert all(len(record["experience"]) >= 2 for record in records)
