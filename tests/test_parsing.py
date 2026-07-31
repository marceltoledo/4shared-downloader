from app.core.parsing import (
    parse_file_cards,
    parse_next_page,
    parse_subfolder_cards,
    parse_total_pages,
)

FOLDER_PAGE_HTML = """
<html><body>
  <div class="jsCardItem file">
    <div class="jsFileName">photo.jpg</div>
    <a class="jsGoFile" href="/file/abc123/photo.jpg"></a>
  </div>
  <div class="jsCardItem file">
    <div class="jsFileName">notes.txt</div>
    <a class="jsGoFile" href="/file/def456/notes.txt"></a>
  </div>
  <div class="jsCardItem file">
    <div class="jsFileName">clip.mp4</div>
    <a class="jsGoFile" href="https://www.4shared.com/file/ghi789/clip.mp4"></a>
  </div>
  <div class="dir-card">
    <a class="jsFolderLink" href="/folder/xyz999/Subfolder.html">
      <div class="dir-name">Subfolder</div>
    </a>
  </div>
  <input class="jsNextPageLink" value="/folder/abc123/Page2.html">
  <input class="jsPagesTotalCount" value="3">
</body></html>
"""


def test_parse_file_cards_returns_all_file_types_and_fixes_relative_urls():
    files = parse_file_cards(FOLDER_PAGE_HTML)
    names = [f[0] for f in files]
    assert "photo.jpg" in names
    assert "clip.mp4" in names
    assert "notes.txt" in names  # no file-type restriction

    photo_url = dict(files)["photo.jpg"]
    assert photo_url == "https://www.4shared.com/file/abc123/photo.jpg"

    notes_url = dict(files)["notes.txt"]
    assert notes_url == "https://www.4shared.com/file/def456/notes.txt"

    clip_url = dict(files)["clip.mp4"]
    assert clip_url == "https://www.4shared.com/file/ghi789/clip.mp4"


def test_parse_subfolder_cards_extracts_name_and_absolute_url():
    folders = parse_subfolder_cards(FOLDER_PAGE_HTML)
    assert folders == [("Subfolder", "https://www.4shared.com/folder/xyz999/Subfolder.html")]


def test_parse_next_page_fixes_relative_url():
    assert parse_next_page(FOLDER_PAGE_HTML) == "https://www.4shared.com/folder/abc123/Page2.html"


def test_parse_next_page_returns_none_when_absent():
    assert parse_next_page("<html><body>no pagination here</body></html>") is None


def test_parse_total_pages_reads_value():
    assert parse_total_pages(FOLDER_PAGE_HTML) == 3


def test_parse_total_pages_defaults_to_one_when_missing():
    assert parse_total_pages("<html><body>no pagination here</body></html>") == 1
