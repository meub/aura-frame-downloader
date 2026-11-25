"""Fake HTTP objects and IDs shared by the tests."""

import io
import json

import requests

FRAME_1 = "11111111-1111-4111-8111-111111111111"
FRAME_2 = "22222222-2222-4222-8222-222222222222"
FRAME_3 = "33333333-3333-4333-8333-333333333333"


def make_response(status, body=b"", content_type="application/json", raw=None):
    """A requests.Response with the given status and body, or a raw stream for streamed downloads."""
    if isinstance(body, (dict, list)):
        body = json.dumps(body).encode()
    elif isinstance(body, str):
        body = body.encode()
    response = requests.models.Response()
    response.status_code = status
    response.reason = "TEST"
    response.url = "https://example.invalid/"
    response.headers["Content-Type"] = content_type
    response._content = body if raw is None else False
    response.raw = raw if raw is not None else io.BytesIO(body)
    return response


class FakeSession:
    """Stands in for an authenticated requests.Session; returns or raises `result` for every call."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def request(self, method, url, timeout=None, **kwargs):
        self.calls.append({"method": method, "url": url, "timeout": timeout, **kwargs})
        if isinstance(self.result, Exception):
            raise self.result
        return self.result
