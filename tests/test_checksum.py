from app.ingestion.checksum import document_checksum, normalize_raw_text


def test_checksum_ignores_line_endings_and_trailing_whitespace() -> None:
    windows_text = "SUMMARY  \r\nPython\r\n"
    unix_text = "SUMMARY\nPython"

    assert normalize_raw_text(windows_text) == unix_text
    assert document_checksum(windows_text) == document_checksum(unix_text)
