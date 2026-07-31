from app.core.filters import CrawlOptions, categorize_extension, matches


def test_matches_with_no_filters_accepts_everything():
    assert matches("movie.mp4", CrawlOptions())


def test_matches_name_filter_is_case_insensitive_substring():
    opts = CrawlOptions(name_filter="Vacation")
    assert matches("my_VACATION_video.mp4", opts)
    assert not matches("holiday.mp4", opts)


def test_matches_name_filter_none_accepts_everything():
    assert matches("anything.mp4", CrawlOptions(name_filter=None))


def test_matches_name_filter_empty_string_accepts_everything():
    assert matches("anything.mp4", CrawlOptions(name_filter=""))


def test_matches_file_type_all_accepts_any_extension():
    opts = CrawlOptions(file_type="all")
    assert matches("song.mp3", opts)
    assert matches("photo.jpg", opts)
    assert matches("noext", opts)


def test_matches_file_type_video_accepts_only_video_extensions():
    opts = CrawlOptions(file_type="video")
    assert matches("clip.mp4", opts)
    assert matches("clip.MKV", opts)
    assert not matches("song.mp3", opts)
    assert not matches("photo.jpg", opts)


def test_matches_file_type_audio_accepts_only_audio_extensions():
    opts = CrawlOptions(file_type="audio")
    assert matches("song.mp3", opts)
    assert matches("song.FLAC", opts)
    assert not matches("clip.mp4", opts)


def test_matches_combines_name_and_type_filters():
    opts = CrawlOptions(name_filter="party", file_type="video")
    assert matches("party.mp4", opts)
    assert not matches("party.mp3", opts)
    assert not matches("holiday.mp4", opts)


def test_categorize_extension_video():
    assert categorize_extension(".mp4") == "video"
    assert categorize_extension(".MOV") == "video"


def test_categorize_extension_audio():
    assert categorize_extension(".mp3") == "audio"


def test_categorize_extension_unknown_is_other():
    assert categorize_extension(".txt") == "other"
    assert categorize_extension("") == "other"
