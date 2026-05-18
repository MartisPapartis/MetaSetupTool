"""Utilities for inspecting local media files."""

from __future__ import annotations
import os
import struct

from PIL import Image


def get_image_dimensions(path: str) -> tuple[int, int]:
    """Return (width, height) for an image file using Pillow."""
    with Image.open(path) as img:
        return img.size  # (width, height)


def get_video_dimensions(path: str) -> tuple[int, int]:
    """Return (width, height) by parsing the MP4/MOV container header.

    Walks the top-level boxes looking for moov → trak → tkhd which stores
    the track display width and height as 16.16 fixed-point values.
    No external tools required — works with any MP4/MOV file.
    """
    with open(path, "rb") as f:
        return _parse_mp4_dimensions(f)


def _read_box_header(f) -> tuple[int, bytes] | None:
    """Read one ISO BMFF box header; return (size, type) or None at EOF."""
    raw = f.read(8)
    if len(raw) < 8:
        return None
    size = struct.unpack(">I", raw[:4])[0]
    box_type = raw[4:8]
    if size == 1:
        # 64-bit extended size
        ext = f.read(8)
        if len(ext) < 8:
            return None
        size = struct.unpack(">Q", ext)[0]
        size -= 8  # already consumed the extra 8 bytes
    elif size == 0:
        # Box extends to EOF — treat as very large
        size = 2 ** 62
    return size, box_type


def _parse_mp4_dimensions(f) -> tuple[int, int]:
    """Walk moov → trak → tkhd and extract display width/height."""
    file_start = f.tell()
    f.seek(0, 2)
    file_size = f.tell()
    f.seek(file_start)

    moov_offset = _find_box(f, b"moov", file_start, file_size)
    if moov_offset is None:
        raise RuntimeError("No moov box found — not a valid MP4/MOV file")

    # Walk trak boxes inside moov
    moov_end = _box_end(f, moov_offset)
    trak_start = moov_offset + 8
    while trak_start < moov_end:
        trak_offset = _find_box(f, b"trak", trak_start, moov_end)
        if trak_offset is None:
            break
        trak_end = _box_end(f, trak_offset)

        tkhd_offset = _find_box(f, b"tkhd", trak_offset + 8, trak_end)
        if tkhd_offset is not None:
            w, h = _read_tkhd_dimensions(f, tkhd_offset)
            if w > 0 and h > 0:
                return w, h

        trak_start = trak_end

    raise RuntimeError("Could not find video track dimensions in MP4 file")


def _find_box(f, box_type: bytes, start: int, end: int) -> int | None:
    """Scan forward from start, returning the offset of the first box with box_type."""
    f.seek(start)
    pos = start
    while pos < end:
        hdr = _read_box_header(f)
        if hdr is None:
            return None
        size, btype = hdr
        if btype == box_type:
            return pos
        # Skip to next box
        next_pos = pos + size
        if next_pos <= pos:
            return None
        pos = next_pos
        f.seek(pos)
    return None


def _box_end(f, box_offset: int) -> int:
    """Return the byte offset just past the end of the box at box_offset."""
    f.seek(box_offset)
    raw = f.read(8)
    size = struct.unpack(">I", raw[:4])[0]
    if size == 1:
        ext = f.read(8)
        size = struct.unpack(">Q", ext)[0]
    return box_offset + size


def _read_tkhd_dimensions(f, tkhd_offset: int) -> tuple[int, int]:
    """Parse a tkhd box and return (width, height) as integers.

    ISO 14496-12 tkhd layout after the 8-byte box header:
      version(1) + flags(3)
      version 0: creation_time(4) modification_time(4) track_id(4) reserved(4) duration(4)
      version 1: creation_time(8) modification_time(8) track_id(4) reserved(4) duration(8)
      reserved(8) layer(2) alternate_group(2) volume(2) reserved(2) matrix(36)
      width(4) height(4)  ← 16.16 fixed-point
    """
    f.seek(tkhd_offset + 8)  # skip size(4) + type(4)
    version = struct.unpack("B", f.read(1))[0]
    f.read(3)  # flags

    if version == 1:
        f.read(8 + 8 + 4 + 4 + 8)  # creation(8)+modification(8)+track_id(4)+reserved(4)+duration(8)
    else:
        f.read(4 + 4 + 4 + 4 + 4)  # creation(4)+modification(4)+track_id(4)+reserved(4)+duration(4)

    f.read(8 + 2 + 2 + 2 + 2 + 36)  # reserved(8)+layer(2)+alt_group(2)+volume(2)+reserved(2)+matrix(36)

    raw = f.read(8)
    if len(raw) < 8:
        return 0, 0
    w_fixed, h_fixed = struct.unpack(">II", raw)
    return w_fixed >> 16, h_fixed >> 16


_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".wmv", ".flv"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def get_media_dimensions(path: str) -> tuple[int, int]:
    """Return (width, height) for any supported image or video file.

    Raises ValueError for unsupported extensions.
    Raises RuntimeError / OSError when the file cannot be read.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in _IMAGE_EXTENSIONS:
        return get_image_dimensions(path)
    if ext in _VIDEO_EXTENSIONS:
        return get_video_dimensions(path)
    raise ValueError(f"Unsupported media extension '{ext}' for file: {path}")
