import pytest

from app.core.paths import InvalidDestDirError, resolve_dest_root


def test_resolve_dest_root_returns_default_when_none(tmp_path):
    default = tmp_path / "downloads"
    assert resolve_dest_root(None, default) == default


def test_resolve_dest_root_returns_default_when_empty_string(tmp_path):
    default = tmp_path / "downloads"
    assert resolve_dest_root("", default) == default


def test_resolve_dest_root_creates_missing_directory(tmp_path):
    default = tmp_path / "downloads"
    custom = tmp_path / "custom" / "nested"
    result = resolve_dest_root(str(custom), default)

    assert result == custom.resolve()
    assert custom.is_dir()


def test_resolve_dest_root_raises_for_unwritable_target(tmp_path):
    # A plain file where a directory is expected: mkdir() raises FileExistsError,
    # which is the realistic "can't create/write to this path" failure mode.
    blocked = tmp_path / "not_a_dir"
    blocked.write_text("blocking file")

    with pytest.raises(InvalidDestDirError):
        resolve_dest_root(str(blocked / "sub"), tmp_path / "default")
