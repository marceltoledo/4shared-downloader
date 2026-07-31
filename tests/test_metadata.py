import json

from app.core.metadata import MetadataRecord, append_metadata


def _record(filename="clip.mp4"):
    return MetadataRecord(
        filename=filename,
        folder_id="F6YhfbPq",
        account_url="https://www.4shared.com/folder/F6YhfbPq/FolderName.html",
        detail_url="https://www.4shared.com/video/abc/clip.html",
        dest_path="/data/downloads/F6YhfbPq/clip.mp4",
        size_bytes=12345,
        extension=".mp4",
        category="video",
        downloaded_at="2026-07-31T12:00:00+00:00",
    )


def test_append_metadata_creates_file_and_parent_dir(tmp_path):
    metadata_file = tmp_path / "nested" / "metadata.jsonl"
    append_metadata(metadata_file, _record())

    assert metadata_file.exists()
    lines = metadata_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["filename"] == "clip.mp4"
    assert parsed["dest_path"] == "/data/downloads/F6YhfbPq/clip.mp4"


def test_append_metadata_appends_without_truncating(tmp_path):
    metadata_file = tmp_path / "metadata.jsonl"
    append_metadata(metadata_file, _record("first.mp4"))
    append_metadata(metadata_file, _record("second.mp4"))

    lines = metadata_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    filenames = [json.loads(line)["filename"] for line in lines]
    assert filenames == ["first.mp4", "second.mp4"]
