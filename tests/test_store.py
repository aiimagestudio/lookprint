from pathlib import Path

from lookprint.store import copy_files


def _mk(path: Path, content: bytes = b"image") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_plain_copy_with_caption(tmp_path):
    src = _mk(tmp_path / "src" / "a.png", b"one")
    cap = _mk(tmp_path / "src" / "a.txt", b"caption text")
    dst = tmp_path / "dst"
    written = copy_files([src], dst)
    assert (dst / "a.png").read_bytes() == b"one"
    assert (dst / "a.txt").read_bytes() == b"caption text"
    assert str(dst / "a.png") in written and str(dst / "a.txt") in written
    assert src.exists() and cap.exists()  # 原图不动


def test_same_content_skipped(tmp_path):
    src = _mk(tmp_path / "src" / "a.png", b"same")
    dst = tmp_path / "dst"
    _mk(dst / "a.png", b"same")
    assert copy_files([src], dst) == []
    assert list(dst.glob("*")) == [dst / "a.png"]


def test_name_collision_renamed(tmp_path):
    src = _mk(tmp_path / "src" / "a.png", b"new content")
    dst = tmp_path / "dst"
    _mk(dst / "a.png", b"existing")
    written = copy_files([src], dst)
    assert (dst / "a.png").read_bytes() == b"existing"
    assert (dst / "a_1.png").read_bytes() == b"new content"
    assert str(dst / "a_1.png") in written


def test_repeated_add_is_idempotent(tmp_path):
    src = _mk(tmp_path / "src" / "a.png", b"img")
    dst = tmp_path / "dst"
    assert len(copy_files([src], dst)) == 1
    assert copy_files([src], dst) == []
    assert copy_files([src], dst) == []
    assert [p.name for p in dst.glob("*")] == ["a.png"]


def test_caption_follows_renamed_stem(tmp_path):
    src = _mk(tmp_path / "src" / "a.png", b"new")
    _mk(tmp_path / "src" / "a.txt", b"cap")
    dst = tmp_path / "dst"
    _mk(dst / "a.png", b"old")
    copy_files([src], dst)
    assert (dst / "a_1.png").read_bytes() == b"new"
    assert (dst / "a_1.txt").read_bytes() == b"cap"


def test_caption_takes_image_stem(tmp_path):
    # 图片落到 b_1；b_1.txt 是孤儿 caption（没有对应图片），随新图覆盖
    src = _mk(tmp_path / "src" / "b.png", b"img-b")
    _mk(tmp_path / "src" / "b.txt", b"cap-b")
    dst = tmp_path / "dst"
    _mk(dst / "b.png", b"old")
    _mk(dst / "b_1.txt", b"orphan")
    copy_files([src], dst)
    assert (dst / "b_1.png").read_bytes() == b"img-b"
    assert (dst / "b_1.txt").read_bytes() == b"cap-b"
