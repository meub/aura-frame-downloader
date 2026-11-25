"""Tests for aura.core: API calls, error messages, and the download loop."""

import io
import json
import os

import pytest
import requests

import aura.core as core
from aura.exceptions import AuraError, DownloadCancelledError, LoginError, NetworkError, NoAssetsError
from helpers import FRAME_1, FakeSession, make_response

OFFLINE = "Couldn't reach Aura. Check your internet connection and try again."


# Frame IDs

@pytest.mark.parametrize("raw, expected", [
    (FRAME_1, FRAME_1),
    (f"  {FRAME_1}\n", FRAME_1),
    (f"https://app.auraframes.com/frame/{FRAME_1}", FRAME_1),
    (f"app.auraframes.com/frame/{FRAME_1}?tab=photos", FRAME_1),
    (FRAME_1.upper(), FRAME_1.upper()),
    ("  not-a-frame-id ", "not-a-frame-id"),
])
def test_normalize_frame_id(raw, expected):
    assert core.normalize_frame_id(raw) == expected


# Login

def login_responds(monkeypatch, result):
    def respond(self, method, url, **kwargs):
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(requests.Session, "request", respond)


def test_login_sets_auth_headers(monkeypatch):
    login_responds(monkeypatch, make_response(200, {"result": {"current_user": {"id": "u1", "auth_token": "t1"}}}))
    session = core.create_session("a@example.com", "pw")
    assert session.headers["X-User-Id"] == "u1"
    assert session.headers["X-Token-Auth"] == "t1"


def test_login_shows_auras_message_for_bad_credentials(monkeypatch):
    # Aura answers a wrong email/password with HTTP 475 and a JSON message.
    login_responds(monkeypatch, make_response(475, {"error": True, "message": "The email or password was incorrect."}))
    with pytest.raises(LoginError, match=r"^Login failed: The email or password was incorrect\.$"):
        core.create_session("a@example.com", "wrong")


def test_login_without_message_points_at_an_outage(monkeypatch):
    login_responds(monkeypatch, make_response(503, "<html>Service Unavailable</html>", "text/html"))
    with pytest.raises(LoginError, match="HTTP 503. Aura may be having problems"):
        core.create_session("a@example.com", "pw")


def test_login_offline_raises_network_error(monkeypatch):
    login_responds(monkeypatch, requests.ConnectionError("Max retries exceeded"))
    with pytest.raises(NetworkError, match=OFFLINE):
        core.create_session("a@example.com", "pw")


# Frame list

def test_get_frames_keeps_id_name_and_count():
    session = FakeSession(make_response(200, {"frames": [
        {"id": FRAME_1, "name": "Living Room", "num_assets": 4922, "brightness": 5},
        {"id": "f2", "name": None},
    ], "user_pending_tokens": []}))
    assert core.get_frames(session) == [
        {"id": FRAME_1, "name": "Living Room", "num_assets": 4922},
        {"id": "f2", "name": "Unnamed frame", "num_assets": None},
    ]
    assert session.calls[0]["url"] == core.FRAMES_URL
    assert session.calls[0]["timeout"] == core.REQUEST_TIMEOUT_SECONDS


@pytest.mark.parametrize("response", [
    make_response(200, "<html>", "text/html"),
    make_response(401, {"error": True, "message": "Request Unauthenticated"}),
])
def test_get_frames_rejects_unexpected_responses(response):
    with pytest.raises(AuraError, match="unexpected response"):
        core.get_frames(FakeSession(response))


@pytest.mark.parametrize("error", [
    requests.ConnectionError("dns"), requests.Timeout("read timed out"), requests.exceptions.SSLError("cert"),
])
def test_api_calls_turn_connection_failures_into_network_error(error):
    with pytest.raises(NetworkError, match=OFFLINE):
        core.get_frames(FakeSession(error))
    with pytest.raises(NetworkError, match=OFFLINE):
        core.get_frame_assets(FakeSession(error), FRAME_1)


# Frame assets

def test_get_frame_assets_uses_the_id_from_a_pasted_url():
    session = FakeSession(make_response(200, {"assets": [{"id": "a"}]}))
    assert core.get_frame_assets(session, f"https://app.auraframes.com/frame/{FRAME_1}") == [{"id": "a"}]
    assert f"/frames/{FRAME_1}/assets.json" in session.calls[0]["url"]


def test_get_frame_assets_html_page_is_a_clear_error():
    # A frame ID with "/" in it used to surface as "Expecting value: line 1 column 1 (char 0)".
    with pytest.raises(NoAssetsError, match=r"unexpected response \(HTTP 404\)\. Check that the Frame ID"):
        core.get_frame_assets(FakeSession(make_response(404, "<!DOCTYPE html>", "text/html")), "bad/id")


def test_get_frame_assets_not_found_names_the_frame_id():
    with pytest.raises(NoAssetsError, match=r"could not load this frame: Not found \(HTTP 404\)"):
        core.get_frame_assets(FakeSession(make_response(404, {"error": True, "message": "Not found"})), FRAME_1)


def test_get_frame_assets_saves_the_raw_response(tmp_path):
    path = tmp_path / "aura-assets.json"
    core.get_frame_assets(FakeSession(make_response(200, {"assets": []})), FRAME_1, save_raw_response_path=str(path))
    assert json.loads(path.read_text()) == {"assets": []}


# Download loop

def asset(index, **extra):
    item = {"id": f"a{index}", "taken_at": f"2024-01-{index + 1:02d}T10:20:30Z", "user_id": "u", "file_name": f"p{index}.jpg"}
    item.update(extra)
    return item


class Stream(io.BytesIO):
    """A download body that can drop the connection partway through."""

    def __init__(self, data, drop_after=None):
        super().__init__(data)
        self.drop_after = drop_after

    def read(self, *args):
        if self.drop_after is not None and self.tell() >= self.drop_after:
            raise requests.ConnectionError("connection dropped")
        return super().read(4)


@pytest.fixture
def frame(monkeypatch):
    """Fake the login and asset list; returns a dict whose 'assets' and 'photo' entries each test sets."""
    state = {"assets": [], "photo": lambda index: "ok", "requested": []}
    monkeypatch.setattr(core, "create_session", lambda email, password: None)
    monkeypatch.setattr(core, "get_frame_assets", lambda session, frame_id, save_raw_response_path=None: state["assets"])

    def fake_get(url, stream=False, timeout=None):
        assert timeout == core.REQUEST_TIMEOUT_SECONDS
        index = int(url.rsplit("/p", 1)[1].split(".")[0]) if "/p" in url else -1
        state["requested"].append(url)
        kind = state["photo"](index)
        if kind == "down":
            raise requests.ConnectionError("Max retries exceeded")
        if kind == "404":
            return make_response(404, "404 page not found", "text/plain")
        if kind == "drop":
            return make_response(200, raw=Stream(b"0123456789abcdef", drop_after=8), content_type="image/jpeg")
        return make_response(200, raw=Stream(b"JPEGDATA"), content_type="image/jpeg")

    monkeypatch.setattr(core.requests, "get", fake_get)
    return state


def run(tmp_path, **options):
    return core.download_photos_from_aura("e", "p", "f", str(tmp_path), **options)


def test_downloads_photos_and_skips_them_next_time(frame, tmp_path):
    frame["assets"] = [asset(0), asset(1)]
    assert run(tmp_path) == (2, 0, 0, 2)
    assert sorted(os.listdir(tmp_path)) == ["2024-01-01T10-20-30Z_a0.jpg", "2024-01-02T10-20-30Z_a1.jpg"]
    assert (tmp_path / "2024-01-01T10-20-30Z_a0.jpg").read_bytes() == b"JPEGDATA"
    assert run(tmp_path) == (0, 2, 0, 2)


def test_error_pages_are_not_saved_as_photos(frame, tmp_path):
    # imgproxy answers a missing photo with a small text/plain 404, which used to be saved as the .jpg.
    frame["assets"] = [asset(0), asset(1)]
    frame["photo"] = lambda index: "404" if index == 0 else "ok"
    assert run(tmp_path) == (1, 0, 1, 2)
    assert os.listdir(tmp_path) == ["2024-01-02T10-20-30Z_a1.jpg"]


def test_interrupted_download_is_finished_on_the_next_run(frame, tmp_path):
    frame["assets"] = [asset(0)]
    frame["photo"] = lambda index: "drop"
    assert run(tmp_path) == (0, 0, 1, 1)
    assert os.listdir(tmp_path) == ["2024-01-01T10-20-30Z_a0.jpg.part"]

    frame["photo"] = lambda index: "ok"
    assert run(tmp_path) == (1, 0, 0, 1)
    assert os.listdir(tmp_path) == ["2024-01-01T10-20-30Z_a0.jpg"]


def test_live_photo_downloads_still_and_video(frame, tmp_path):
    frame["assets"] = [asset(0, video_url="https://video.invalid/v0.mov", video_file_name="v0.mov")]
    assert run(tmp_path) == (2, 0, 0, 1)
    assert sorted(os.listdir(tmp_path)) == ["2024-01-01T10-20-30Z_a0.jpg", "2024-01-01T10-20-30Z_a0.mov"]


def test_videos_only_skips_stills(frame, tmp_path):
    frame["assets"] = [asset(0, video_url="https://video.invalid/v0.mov", video_file_name="v0.mov"), asset(1)]
    assert run(tmp_path, videos_only=True) == (1, 0, 0, 2)
    assert os.listdir(tmp_path) == ["2024-01-01T10-20-30Z_a0.mov"]


def test_organize_by_year(frame, tmp_path):
    frame["assets"] = [asset(0), asset(1, taken_at="2019-07-04T00:00:00Z")]
    run(tmp_path, organize_by_year=True)
    assert sorted(os.listdir(tmp_path)) == ["2019", "2024"]


def test_count_only_downloads_nothing(frame, tmp_path):
    frame["assets"] = [asset(0), asset(1), asset(2)]
    assert run(tmp_path, count_only=True) == (0, 0, 0, 3)
    assert frame["requested"] == []


def test_cancel_stops_the_download(frame, tmp_path):
    frame["assets"] = [asset(0), asset(1)]
    with pytest.raises(DownloadCancelledError):
        run(tmp_path, cancel_check=lambda: True)
    assert frame["requested"] == []


def test_lost_connection_stops_after_five_failures_in_a_row(frame, tmp_path):
    frame["assets"] = [asset(i) for i in range(20)]
    frame["photo"] = lambda index: "ok" if index < 3 else "down"
    with pytest.raises(NetworkError, match="Lost the connection to Aura"):
        run(tmp_path)
    assert len(frame["requested"]) == 3 + core.MAX_CONSECUTIVE_NETWORK_FAILURES


def test_short_connection_blips_do_not_stop_the_download(frame, tmp_path):
    frame["assets"] = [asset(i) for i in range(20)]
    frame["photo"] = lambda index: "down" if index in (2, 3, 4, 5, 10, 11, 12, 13) else "ok"
    assert run(tmp_path) == (12, 0, 8, 20)


def test_server_errors_do_not_count_as_a_lost_connection(frame, tmp_path):
    # A 404 means the server answered, so it resets the run of connection failures.
    frame["assets"] = [asset(i) for i in range(20)]
    frame["photo"] = lambda index: "404" if index % 2 else "down"
    assert run(tmp_path) == (0, 0, 20, 20)
