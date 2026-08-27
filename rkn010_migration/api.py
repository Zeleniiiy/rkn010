from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests


class CurlResponse:
    def __init__(self, status_code: int, body: bytes):
        self.status_code = status_code
        self.text = body.decode("utf-8-sig", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


class CurlSession:
    """Small requests-compatible session using Windows curl/Schannel.

    Authentication headers are passed through curl's stdin config so JWT and
    cookies never appear in the process command line.
    """

    def __init__(self, executable: str = "curl.exe") -> None:
        self.executable = executable
        self.headers: dict[str, str] = {}
        self.trust_env = False
        self.verify: bool | str = True

    @staticmethod
    def _config_value(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", " ")

    def request(self, method: str, url: str, **kwargs: Any) -> CurlResponse:
        timeout = int(kwargs.get("timeout") or 60)
        data = kwargs.get("data")
        config = "\n".join(
            f'header = "{self._config_value(name)}: {self._config_value(str(value))}"'
            for name, value in self.headers.items()
        ) + "\n"
        with tempfile.TemporaryDirectory(prefix="rkn010-curl-") as directory:
            temp = Path(directory)
            response_path = temp / "response.bin"
            command = [
                self.executable,
                "--config", "-",
                "--compressed",
                "--silent",
                "--show-error",
                "--max-time", str(timeout),
                "--request", method,
                "--url", url,
                "--output", str(response_path),
                "--write-out", "%{http_code}",
            ]
            if self.verify is False:
                command.append("--insecure")
            elif isinstance(self.verify, str):
                command.extend(["--cacert", self.verify])
            if data is not None:
                request_path = temp / "request.bin"
                request_path.write_bytes(data if isinstance(data, bytes) else str(data).encode("utf-8"))
                command.extend(["--data-binary", f"@{request_path}"])
            result = subprocess.run(
                command,
                input=config,
                text=True,
                capture_output=True,
                timeout=timeout + 5,
                check=False,
            )
            if result.returncode != 0:
                raise requests.RequestException(result.stderr.strip() or f"curl exit code {result.returncode}")
            try:
                status_code = int(result.stdout.strip())
            except ValueError as exc:
                raise requests.RequestException("curl did not return an HTTP status") from exc
            body = response_path.read_bytes() if response_path.exists() else b""
            return CurlResponse(status_code, body)


class ApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, data: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.data = data


def _read(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig").strip()


def _extract_token(raw: str) -> str:
    clean = re.sub(r"^\s*bearer\s+", "", raw.strip(), flags=re.IGNORECASE)
    match = re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", clean)
    return match.group(0) if match else clean


def _normalise_cookie(raw: str) -> str:
    header = re.search(r"(?im)^\s*cookie\s*:\s*(.+)$", raw)
    value = header.group(1) if header else raw
    return re.sub(r"^\s*cookie\s*:\s*", "", value, flags=re.IGNORECASE).replace("\r", " ").replace("\n", " ").strip()


class PgsClient:
    def __init__(
        self,
        base_url: str,
        *,
        token_file: Path | None = None,
        cookie_file: Path | None = None,
        timeout: int = 60,
        verify_tls: bool | str | Path = True,
        transport: str = "requests",
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token_file = token_file
        self.cookie_file = cookie_file
        self.timeout = timeout
        if session is not None:
            self.session = session
        elif transport == "curl":
            self.session = CurlSession()
        elif transport == "requests":
            self.session = requests.Session()
        else:
            raise ValueError(f"Unknown HTTP transport: {transport}")
        self.session.trust_env = False
        self.session.verify = str(verify_tls) if isinstance(verify_tls, Path) else verify_tls
        self.session.headers.update(
            {
                "Accept": "application/hal+json",
                "Content-Type": "application/json",
                "User-Agent": "rkn010-migration/1.0",
            }
        )
        self.reload_auth()

    def reload_auth(self) -> None:
        self.session.headers.pop("token", None)
        self.session.headers.pop("Authorization", None)
        self.session.headers.pop("Cookie", None)
        token = _extract_token(_read(self.token_file))
        cookie = _normalise_cookie(_read(self.cookie_file))
        if token:
            self.session.headers["token"] = token
            self.session.headers["Authorization"] = f"Bearer {token}"
        if cookie:
            self.session.headers["Cookie"] = cookie

    def request(self, method: str, path: str, *, body: Any = None, retry_auth: bool = True) -> Any:
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self.session.request(
                    method,
                    url,
                    data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt == 2:
                    raise ApiError(f"Network error for {method} {path}: {exc}") from exc
                time.sleep(0.5 * (attempt + 1))
                continue
            if response.status_code in (401, 403) and retry_auth and attempt == 0:
                self.reload_auth()
                continue
            if response.status_code >= 500 and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            try:
                data = response.json() if response.text else None
            except ValueError:
                data = response.text
            if 200 <= response.status_code < 300:
                return data
            raise ApiError(
                f"HTTP {response.status_code} for {method} {path}",
                status_code=response.status_code,
                data=data,
            )
        raise ApiError(f"Request failed for {method} {path}: {last_error}")

    def search(self, collection: str, body: dict[str, Any]) -> dict[str, Any]:
        result = self.request("POST", f"/api/v1/search/{collection}", body=body)
        return result if isinstance(result, dict) else {"content": []}

    def find(self, collection: str, main_id: str) -> dict[str, Any]:
        result = self.request(
            "GET",
            f"/api/v1/find/{collection}?mainId={quote(str(main_id), safe='')}",
        )
        if not isinstance(result, dict):
            raise ApiError(f"Unexpected find response for {collection}/{main_id}")
        return result

    def create(self, collection: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.request("POST", f"/api/v1/create/{collection}", body=payload)
        if not isinstance(result, dict):
            raise ApiError(f"Unexpected create response for {collection}", data=result)
        return result

    def update(self, collection: str, document: dict[str, Any]) -> dict[str, Any]:
        main_id = document.get("_id")
        guid = document.get("guid")
        if not main_id or not guid:
            raise ApiError(f"Cannot update {collection}: _id/guid missing")
        path = (
            f"/api/v1/update/{collection}?mainId={quote(str(main_id), safe='')}"
            f"&guid={quote(str(guid), safe='')}"
        )
        result = self.request("PUT", path, body=document)
        return result if isinstance(result, dict) else document

    def delete(self, document: dict[str, Any]) -> None:
        main_id = document.get("_id")
        guid = document.get("guid")
        collection = document.get("parentEntries")
        if not main_id or not guid or not collection:
            raise ApiError("Cannot delete: _id/guid/parentEntries missing")
        path = (
            f"/api/v1/delete/{collection}?mainId={quote(str(main_id), safe='')}"
            f"&guid={quote(str(guid), safe='')}"
        )
        try:
            self.request("DELETE", path)
        except ApiError as exc:
            if exc.status_code != 404:
                raise

    def auth_test(self) -> None:
        self.search(
            "organizations",
            {
                "search": {"search": []},
                "size": 1,
            },
        )


def search_conditions(*conditions: dict[str, Any]) -> dict[str, Any]:
    return {"search": {"search": list(conditions)}, "size": 2}
