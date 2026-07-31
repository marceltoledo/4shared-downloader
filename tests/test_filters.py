from app.core.filters import CrawlOptions, matches


def test_matches_without_filters_accepts_every_filename():
    assert matches("movie.mp4", CrawlOptions())
    assert matches("document.pdf", CrawlOptions())


def test_matches_filename_filter_is_case_insensitive():
    options = CrawlOptions(name_filter="Vacation")

    assert matches("my_VACATION_video.mp4", options)
    assert not matches("holiday.mp4", options)


def test_matches_video_filter_accepts_only_video_extensions():
    options = CrawlOptions(file_type="video")

    assert matches("clip.MKV", options)
    assert not matches("song.mp3", options)
    assert not matches("photo.jpg", options)


def test_matches_audio_filter_accepts_only_audio_extensions():
    options = CrawlOptions(file_type="audio")

    assert matches("song.FLAC", options)
    assert not matches("clip.mp4", options)


def test_matches_combines_filename_and_type_filters():
    options = CrawlOptions(name_filter="party", file_type="video")

    assert matches("party.mp4", options)
    assert not matches("party.mp3", options)
    assert not matches("holiday.mp4", options)