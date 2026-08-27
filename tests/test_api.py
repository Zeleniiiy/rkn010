from __future__ import annotations

import json

import pytest

from rkn010_migration.api import ApiError, PgsClient


class Response:
    def __init__(self, status_code=200, data=None):
        self.status_code = status_code
        self._data = data
        self.text = "" if data is None else json.dumps(data)

    def json(self):
        return self._data


class Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.trust_env = True
        self.verify = True
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def test_loads_token_and_only_cookie_header_line(tmp_path):
    token = tmp_path / "token.md"
    cookie = tmp_path / "cookie.md"
    token.write_text("Bearer eyJabc.def.ghi", encoding="utf-8")
    cookie.write_text("GET / HTTP/1.1\nCookie: A=1; B=2\nHost: example", encoding="utf-8")
    session = Session([Response(data={"content": []})])
    client = PgsClient("https://example", token_file=token, cookie_file=cookie, session=session)
    assert session.headers["token"] == "eyJabc.def.ghi"
    assert session.headers["Authorization"] == "Bearer eyJabc.def.ghi"
    assert session.headers["Cookie"] == "A=1; B=2"
    client.search("organizations", {"search": []})
    sent = json.loads(session.calls[0][2]["data"].decode("utf-8"))
    assert sent == {"search": []}


def test_retries_server_error_and_accepts_second_response():
    session = Session([Response(500, {"error": "temporary"}), Response(200, {"content": []})])
    client = PgsClient("https://example", session=session)
    assert client.search("organizations", {"search": []}) == {"content": []}
    assert len(session.calls) == 2


def test_update_requires_id_and_guid():
    client = PgsClient("https://example", session=Session([]))
    with pytest.raises(ApiError):
        client.update("RKN010_Records", {"status": "active"})
