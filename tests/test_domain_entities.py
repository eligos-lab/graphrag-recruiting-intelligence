from uuid import UUID

from app.domain import Person


def test_person_gets_uuid_identity() -> None:
    person = Person(full_name="Ada Lovelace", source="fixture", source_id="ada-1")

    assert isinstance(person.id, UUID)
    assert person.full_name == "Ada Lovelace"
