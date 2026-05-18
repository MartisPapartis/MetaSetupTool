"""Image and video upload to Meta Ads Manager."""

from __future__ import annotations
import os
import time
from typing import Callable

from app.api.client import MetaApiClient
from app.api.resumable_upload import ResumableVideoUpload

# Files larger than this threshold use resumable upload
RESUMABLE_THRESHOLD_BYTES = 1 * 1024 * 1024  # 1 MB
VIDEO_POLL_INTERVAL = 5  # seconds between status polls
VIDEO_POLL_TIMEOUT = 300  # seconds max wait for encoding


def upload_image(client: MetaApiClient, path: str) -> str:
    """Upload an image file and return its image hash."""
    filename = os.path.basename(path)
    with open(path, "rb") as f:
        files = {filename: (filename, f, _mime_for(path))}
        result = client.post(f"{client.account_path}/adimages", files=files)

    images = result.get("images", {})
    if not images:
        raise RuntimeError(f"Image upload returned no hash for {filename}")
    # Key is the filename
    image_data = next(iter(images.values()))
    return image_data["hash"]


def upload_video(
    client: MetaApiClient,
    path: str,
    title: str = "",
    progress_callback: Callable[[int], None] | None = None,
) -> tuple[str, str]:
    """Upload a video file and return (video_id, thumbnail_url) after encoding."""
    file_size = os.path.getsize(path)

    if file_size >= RESUMABLE_THRESHOLD_BYTES:
        video_id = _upload_video_resumable(client, path, title, progress_callback)
    else:
        video_id = _upload_video_simple(client, path, title)

    thumbnail_url = _wait_for_video_ready(client, video_id, progress_callback)
    return video_id, thumbnail_url


def _upload_video_simple(client: MetaApiClient, path: str, title: str) -> str:
    filename = os.path.basename(path)
    data = {"title": title or filename}
    with open(path, "rb") as f:
        files = {"source": (filename, f, _mime_for(path))}
        result = client.post(
            f"{client.account_path}/advideos", data=data, files=files, video=True
        )
    return result["id"]


def _upload_video_resumable(
    client: MetaApiClient,
    path: str,
    title: str,
    progress_callback: Callable[[int], None] | None,
) -> str:
    uploader = ResumableVideoUpload(client, path, title, progress_callback)
    return uploader.run()


def _wait_for_video_ready(
    client: MetaApiClient,
    video_id: str,
    _progress_callback: Callable[[int], None] | None,
) -> str:
    """Poll until the video finishes encoding; return its thumbnail URL."""
    deadline = time.time() + VIDEO_POLL_TIMEOUT
    while time.time() < deadline:
        data = client.get(video_id, params={"fields": "status,picture"})
        status = data.get("status", {})
        video_status = status.get("video_status", "")
        if video_status == "ready":
            return data.get("picture", "")
        if video_status == "error":
            msg = status.get("error", {}).get("message", "Unknown encoding error")
            raise RuntimeError(f"Video encoding failed: {msg}")
        time.sleep(VIDEO_POLL_INTERVAL)

    raise TimeoutError(
        f"Video {video_id} did not finish encoding within {VIDEO_POLL_TIMEOUT}s"
    )


def _mime_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".mp4": "video/mp4",
        ".mov": "video/quicktime",
        ".avi": "video/avi",
        ".mkv": "video/x-matroska",
        ".m4v": "video/x-m4v",
        ".wmv": "video/x-ms-wmv",
        ".flv": "video/x-flv",
    }
    return mime_map.get(ext, "application/octet-stream")
