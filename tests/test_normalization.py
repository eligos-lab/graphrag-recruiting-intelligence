from app.ingestion.normalization import EntityNameNormalizer, normalize_name, normalized_identity


def test_normalize_name_handles_case_punctuation_and_whitespace() -> None:
    assert normalize_name("  Postgre-SQL!!! ") == "postgre sql"


def test_aliases_resolve_to_same_canonical_entity() -> None:
    normalizer = EntityNameNormalizer()

    postgres = normalizer.canonicalize("Postgres")
    postgre_sql = normalizer.canonicalize("Postgre SQL")

    assert postgres.canonical_name == "PostgreSQL"
    assert postgres.normalized_name == postgre_sql.normalized_name == "postgresql"


def test_identity_requires_country_to_avoid_weak_name_only_matching() -> None:
    assert normalized_identity("Ada Lovelace", None) is None
    assert normalized_identity(" Ada  Lovelace ", "United Kingdom") == (
        "ada lovelace|united kingdom"
    )
