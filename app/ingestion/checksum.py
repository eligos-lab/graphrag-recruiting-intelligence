from hashlib import sha256


def normalize_raw_text(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.replace("\r\n", "\n").split("\n")).strip()


def document_checksum(raw_text: str) -> str:
    return sha256(normalize_raw_text(raw_text).encode("utf-8")).hexdigest()
