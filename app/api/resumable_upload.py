"""Resumable video upload for large files (>50 MB)."""

from __future__ import annotations
import os
from typing import Callable

from app.api.client import MetaApiClient

CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB chunks


class ResumableVideoUpload:
    """
    Implements Meta's 3-phase resumable video upload:
      1. start  — initialize session, get upload_session_id + video_id
      2. transfer — upload chunks, track offsets
      3. finish  — finalize upload
    """

    def __init__(
        self,
        client: MetaApiClient,
        path: str,
        title: str = "",
        progress_callback: Callable[[int], None] | None = None,
    ):
        self.client = client
        self.path = path
        self.title = title or os.path.basename(path)
        self.progress_callback = progress_callback
        self.file_size = os.path.getsize(path)

    def run(self) -> str:
        """Execute the full upload and return the video ID."""
        upload_session_id, video_id, start_offset = self._start()
        self._transfer(upload_session_id, start_offset)
        self._finish(upload_session_id)
        return video_id

    def _start(self) -> tuple[str, str, int]:
        result = self.client.post(
            f"{self.client.account_path}/advideos",
            data={
                "upload_phase": "start",
                "file_size": str(self.file_size),
            },
            video=True,
        )
        return (
            result["upload_session_id"],
            result["video_id"],
            int(result["start_offset"]),
        )

    def _transfer(self, upload_session_id: str, start_offset: int) -> None:
        with open(self.path, "rb") as f:
            offset = start_offset
            while offset < self.file_size:
                f.seek(offset)
                chunk = f.read(CHUNK_SIZE)
                end_offset = offset + len(chunk)

                result = self.client.post(
                    f"{self.client.account_path}/advideos",
                    data={
                        "upload_phase": "transfer",
                        "upload_session_id": upload_session_id,
                        "start_offset": str(offset),
                        "end_offset": str(end_offset),
                    },
                    files={
                        "video_file_chunk": ("chunk", chunk, "application/octet-stream")
                    },
                    video=True,
                )

                offset = int(result["start_offset"])
                pct = int(offset / self.file_size * 90)  # reserve last 10% for finish
                if self.progress_callback:
                    self.progress_callback(pct)

    def _finish(self, upload_session_id: str) -> None:
        self.client.post(
            f"{self.client.account_path}/advideos",
            data={
                "upload_phase": "finish",
                "upload_session_id": upload_session_id,
                "title": self.title,
            },
            video=True,
        )
        if self.progress_callback:
            self.progress_callback(95)
