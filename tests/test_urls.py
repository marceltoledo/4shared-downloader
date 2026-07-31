from app.core.urls import folder_id_from_url, normalize_url


def test_normalize_url_new_style_unchanged():
    url = "https://www.4shared.com/folder/F6YhfbPq/FolderName.html"
    assert normalize_url(url) == url


def test_normalize_url_old_style_unchanged():
    url = "https://www.4shared.com/folder/xy-o4oZ4/_online.html"
    assert normalize_url(url) == url


def test_normalize_url_strips_query_and_hash():
    url = "https://www.4shared.com/folder/F6YhfbPq/_online.html?ref=abc#note"
    assert normalize_url(url) == "https://www.4shared.com/folder/F6YhfbPq/_online.html"


def test_normalize_url_fixes_double_slash_after_domain():
    url = "https://www.4shared.com//folder/F6YhfbPq/_online.html"
    assert normalize_url(url) == "https://www.4shared.com/folder/F6YhfbPq/_online.html"


def test_normalize_url_splits_doubled_urls_on_one_line():
    joined = "https://www.4shared.com/folder/F6YhfbPq/_online.htmlhttps://www.evil.com/x"
    assert normalize_url(joined) == "https://www.4shared.com/folder/F6YhfbPq/_online.html"


def test_normalize_url_strips_surrounding_whitespace():
    url = "  https://www.4shared.com/folder/F6YhfbPq/_online.html  \n"
    assert normalize_url(url) == "https://www.4shared.com/folder/F6YhfbPq/_online.html"


def test_folder_id_from_url_new_style():
    assert folder_id_from_url("https://www.4shared.com/folder/F6YhfbPq/FolderName.html") == "F6YhfbPq"


def test_folder_id_from_url_old_style():
    assert folder_id_from_url("https://www.4shared.com/folder/xy-o4oZ4/_online.html") == "xy-o4oZ4"


def test_folder_id_from_url_fallback_for_non_matching_input():
    assert folder_id_from_url("not-a-4shared-url") == "not-a-4shared-url"
