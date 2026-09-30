from __future__ import annotations

import os
import json
from typing import Any
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_SERVER_URL = "http://127.0.0.1:8000"
CONFIG_FILE = Path(__file__).resolve().parent / "api_config.json"
REQUEST_TIMEOUT = (3.05, 10.0)

_session = requests.Session()
_session.mount(
    "http://",
    HTTPAdapter(
        max_retries=Retry(
            total=2,
            connect=0,
            read=0,
            status=2,
            backoff_factor=0.25,
            status_forcelist=(502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
    ),
)
_session.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=2,
            connect=0,
            read=0,
            status=2,
            backoff_factor=0.25,
            status_forcelist=(502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            raise_on_status=False,
        )
    ),
)
_bearer_token: str | None = None


class APIClientError(RuntimeError):
    """An API request failed or the server could not be reached."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def server_url() -> str:
    configured = os.getenv("HV_LABEL_SERVER_URL", "").strip()
    if not configured and CONFIG_FILE.exists():
        try:
            with CONFIG_FILE.open(encoding="utf-8") as file:
                config = json.load(file)
            configured = str(config.get("server_url", "")).strip()
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            raise APIClientError(f"Could not read API server configuration {CONFIG_FILE}: {exc}") from exc
    configured = configured or DEFAULT_SERVER_URL
    if not configured.startswith(("http://", "https://")):
        raise APIClientError("HV_LABEL_SERVER_URL must start with http:// or https://.")
    return configured.rstrip("/")


def set_bearer_token(token: str | None) -> None:
    global _bearer_token
    _bearer_token = token or None


def request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    bearer: bool = True,
) -> Any:
    from common.auth.machine_lock import get_machine_hash

    headers = {"X-Machine-Hash": get_machine_hash()}
    if bearer and _bearer_token:
        headers["Authorization"] = f"Bearer {_bearer_token}"

    url = f"{server_url()}/{path.lstrip('/')}"
    try:
        response = _session.request(
            method.upper(),
            url,
            headers=headers,
            params=params,
            json=json,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise APIClientError(
            f"Could not reach the HV Label Printer server at {server_url()}: {exc}"
        ) from exc

    if not response.ok:
        try:
            detail = response.json().get("detail", response.text)
        except (ValueError, AttributeError):
            detail = response.text
        raise APIClientError(
            f"HV Label Printer server returned HTTP {response.status_code}: {detail}",
            status_code=response.status_code,
        )
    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise APIClientError("HV Label Printer server returned invalid JSON.") from exc


def get(path: str, *, params: dict[str, Any] | None = None) -> Any:
    return request("GET", path, params=params)


def post(path: str, payload: dict[str, Any]) -> Any:
    return request("POST", path, json=payload)


def patch(path: str, payload: dict[str, Any]) -> Any:
    return request("PATCH", path, json=payload)


def put(path: str, payload: dict[str, Any]) -> Any:
    return request("PUT", path, json=payload)


def delete(path: str) -> Any:
    return request("DELETE", path)


def get_all(path: str, *, page_size: int = 500) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = get(path, params={"limit": page_size, "offset": offset})
        if not isinstance(page, list):
            raise APIClientError("HV Label Printer server returned an invalid log response.")
        results.extend(page)
        if len(page) < page_size:
            return results
        offset += len(page)
