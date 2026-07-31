import json

from app.core.metadata import MetadataRecord, append_metadata, read_recorded_filenames


def test_append_metadata_writes_json_lines(tmp_path):
    metadata_file = tmp_path / "downloads" / "rPORWech" / "metadata.jsonl"

    append_metadata(
        metadata_file,
        MetadataRecord(
            filename="Gil Gomes 1 (1).mp3",
            folder_id="rPORWech",
            account_url="https://www.4shared.com/folder/rPORWech/_online.html",
            detail_url="https://www.4s.io/mp3/abc/Gil_Gomes_1__1_.html",
            media_url="https://dc.xyz/file.mp3",
            dest_path=str(tmp_path / "downloads" / "rPORWech" / "Gil Gomes 1 (1).mp3"),
            size_bytes=123,
            downloaded_at="2026-07-31T18:00:00+00:00",
        ),
    )

    append_metadata(
        metadata_file,
        MetadataRecord(
            filename="Gil Gomes 1 (2).mp3",
            folder_id="rPORWech",
            account_url="https://www.4shared.com/folder/rPORWech/_online.html",
            detail_url="https://www.4s.io/mp3/def/Gil_Gomes_1__2_.html",
            media_url="https://dc.xyz/file2.mp3",
            dest_path=str(tmp_path / "downloads" / "rPORWech" / "Gil Gomes 1 (2).mp3"),
            size_bytes=456,
            downloaded_at="2026-07-31T18:01:00+00:00",
        ),
    )

    lines = metadata_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["filename"] == "Gil Gomes 1 (1).mp3"
    assert second["filename"] == "Gil Gomes 1 (2).mp3"


def test_read_recorded_filenames_ignores_invalid_lines(tmp_path):
    metadata_file = tmp_path / "metadata.jsonl"
    metadata_file.write_text(
        '{"filename":"a.mp3"}\nnot-json\n{"filename":"b.mp3"}\n{"x":1}\n',
        encoding="utf-8",
    )

    assert read_recorded_filenames(metadata_file) == {"a.mp3", "b.mp3"}