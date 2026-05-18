"""Base Meta Marketing API client."""

from __future__ import annotations
import time
import logging

import requests

log = logging.getLogger(__name__)

# Retry configuration
_MAX_RETRIES = 3
_RETRY_BACKOFF = (5, 15, 30)  # seconds between retries
_RETRYABLE_CODES = {80004, 613, 2}  # rate-limit & transient API errors


class MetaApiError(Exception):
    """Raised when the Meta API returns an error."""

    def __init__(self, message: str, code: int = 0, subcode: int = 0):
        super().__init__(message)
        self.code = code
        self.subcode = subcode


class MetaApiClient:
    BASE_URL = "https://graph.facebook.com"
    VIDEO_URL = "https://graph-video.facebook.com"

    def __init__(
        self, access_token: str, ad_account_id: str, api_version: str = "v25.0"
    ):
        self.access_token = access_token
        self.ad_account_id = ad_account_id.lstrip("act_")  # normalize
        self.api_version = api_version
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "MetaSetupTool/1.0"})

    @property
    def account_path(self) -> str:
        return f"act_{self.ad_account_id}"

    def _url(self, path: str, video: bool = False) -> str:
        base = self.VIDEO_URL if video else self.BASE_URL
        return f"{base}/{self.api_version}/{path}"

    def _check_response(self, response: requests.Response) -> dict:
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            return {}

        if "error" in data:
            err = data["error"]
            msg = err.get("message", "Unknown API error")
            # Append user-facing detail when available (helps debugging)
            user_msg = err.get("error_user_msg") or err.get("error_user_title")
            if user_msg and user_msg != msg:
                msg = f"{msg} — {user_msg}"
            raise MetaApiError(
                message=msg,
                code=err.get("code", 0),
                subcode=err.get("error_subcode", 0),
            )
        response.raise_for_status()
        return data

    def _request_with_retry(self, method: str, url: str, **kwargs) -> dict:
        """Execute an HTTP request with retry/backoff for rate-limit errors."""
        last_error: MetaApiError | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self._session.request(method, url, **kwargs)
                return self._check_response(response)
            except MetaApiError as e:
                if e.code not in _RETRYABLE_CODES or attempt >= _MAX_RETRIES:
                    raise
                last_error = e
                wait = _RETRY_BACKOFF[attempt]
                log.warning(
                    "Rate-limited (code %d), retrying in %ds (attempt %d/%d)",
                    e.code,
                    wait,
                    attempt + 1,
                    _MAX_RETRIES,
                )
                time.sleep(wait)
        raise last_error  # type: ignore[misc]  # unreachable, keeps type-checker happy

    def get(self, path: str, params: dict | None = None) -> dict:
        p = {"access_token": self.access_token, **(params or {})}
        return self._request_with_retry("GET", self._url(path), params=p, timeout=30)

    def post(
        self, path: str, data: dict | None = None, files=None, video: bool = False
    ) -> dict:
        payload = {"access_token": self.access_token, **(data or {})}
        url = self._url(path, video=video)
        return self._request_with_retry(
            "POST", url, data=payload, files=files, timeout=120
        )

    def post_json(self, path: str, json_data: dict | None = None) -> dict:
        params = {"access_token": self.access_token}
        return self._request_with_retry(
            "POST", self._url(path), params=params, json=json_data or {}, timeout=60
        )
