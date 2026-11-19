import json
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atcctl.freq import FrequencyError, parse_frequency  # noqa: E402
from atcctl.receiver import Receiver  # noqa: E402
from atcctl.server import App, make_handler  # noqa: E402


# ---------------- 주파수 ----------------
@pytest.mark.parametrize("inp,hz", [
    ("121.5", 121_500_000),
    ("118.100 MHz", 118_100_000),
    (118100000, 118_100_000),
    ("118.005", 118_000_000),   # 8.33 채널 이름 -> 실제 주파수
    ("118.010", 118_008_333),
    ("118.015", 118_016_667),
    ("243.0", 243_000_000),     # UHF 군 비상
])
def test_parse_frequency(inp, hz):
    assert parse_frequency(inp).hz == hz


@pytest.mark.parametrize("bad", ["abc", "100.0", "150.0", "1090", ""])
def test_parse_frequency_rejects(bad):
    with pytest.raises(FrequencyError):
        parse_frequency(bad)


def test_band_restriction():
    with pytest.raises(FrequencyError):
        parse_frequency("243.0", allowed_bands=("vhf",))


# ---------------- 수신기 파이프라인 ----------------
def test_default_pipeline_commands():
    r = Receiver({"id": "a", "device": "AIR1", "frequency": "119.1", "gain": 35, "squelch": 20})
    rtl, ff = r.build_commands()
    assert rtl[:6] == ["rtl_fm", "-d", "AIR1", "-M", "am", "-f"]
    assert "119100000" in rtl
    assert rtl[rtl.index("-g") + 1] == "35"
    assert rtl[rtl.index("-l") + 1] == "20"
    assert ff[0] == "ffmpeg" and "libmp3lame" in ff


def test_auto_gain_omits_flag():
    r = Receiver({"id": "a", "frequency": "121.5", "gain": "auto"})
    assert "-g" not in r.build_commands()[0]


FAKE = f"{sys.executable} -c \"import sys,time\nwhile True: sys.stdout.buffer.write(b'{{freq_hz}}'+b'x'*2000); sys.stdout.flush(); time.sleep(0.05)\""


def test_receiver_streams_and_retunes():
    r = Receiver({"id": "a", "frequency": "121.5", "command": FAKE})
    r.start()
    try:
        q = r.subscribe()
        assert b"121500000" in q.get(timeout=5)
        r.tune(frequency="118.1")
        assert r.status()["frequency_mhz"] == "118.100"
        deadline = time.time() + 5
        while time.time() < deadline:
            if b"118100000" in q.get(timeout=5):
                break
        else:
            pytest.fail("재튜닝 후 새 주파수 데이터 없음")
        assert r.running
    finally:
        r.stop()
    assert not r.running


def test_tune_validation():
    r = Receiver({"id": "a", "frequency": "121.5", "command": FAKE})
    with pytest.raises(ValueError):
        r.tune(gain=99)
    with pytest.raises(FrequencyError):
        r.tune(frequency="88.1")
    r.stop()


# ---------------- HTTP 서버 ----------------
@pytest.fixture
def server(tmp_path):
    adsb = tmp_path / "aircraft.json"
    adsb.write_text(json.dumps({"now": 1, "messages": 42, "aircraft": [
        {"hex": "71c123", "flight": "KAL123  ", "alt_baro": 35000, "lat": 37.5, "lon": 126.8, "type": "adsb_icao", "seen": 0.5},
        {"hex": "71c999", "squawk": "1200", "type": "mode_s", "seen": 2},
    ]}))
    cfg = {"token": "secret", "adsb_json": str(adsb),
           "receivers": [{"id": "atc1", "frequency": "121.5", "command": FAKE}]}
    app = App(cfg, tmp_path)
    app.start_all()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    httpd.daemon_threads = True
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    app.stop_all()


def req(url, method="GET", body=None, token="secret"):
    r = urllib.request.Request(url, method=method,
                               data=json.dumps(body).encode() if body is not None else None)
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def test_auth_required(server, monkeypatch):
    monkeypatch.setenv("ATCCTL_QUIET", "1")
    with pytest.raises(urllib.error.HTTPError) as e:
        req(server + "/api/receivers", token=None)
    assert e.value.code == 401


def test_tune_over_http(server, monkeypatch):
    monkeypatch.setenv("ATCCTL_QUIET", "1")
    st, data = req(server + "/api/receivers/atc1/tune", "POST", {"frequency": "119.100", "squelch": 30})
    assert data["frequency_mhz"] == "119.100" and data["squelch"] == 30
    with pytest.raises(urllib.error.HTTPError) as e:
        req(server + "/api/receivers/atc1/tune", "POST", {"frequency": "500"})
    assert e.value.code == 400


def test_stream_over_http(server, monkeypatch):
    monkeypatch.setenv("ATCCTL_QUIET", "1")
    with urllib.request.urlopen(server + "/stream/atc1.mp3?token=secret", timeout=5) as resp:
        assert resp.headers["Content-Type"] == "audio/mpeg"
        assert len(resp.read(4096)) > 0


def test_presets_and_adsb(server, monkeypatch):
    monkeypatch.setenv("ATCCTL_QUIET", "1")
    _, p = req(server + "/api/presets", "PUT", [{"name": "Guard", "frequency": "121.5"}])
    assert p == [{"name": "Guard", "frequency": "121.5"}]
    _, a = req(server + "/api/adsb")
    assert a["total"] == 2 and a["with_position"] == 1 and a["mode_s_only"] == 1
    assert a["aircraft"][0]["flight"] == "KAL123"


def test_static_ui(server):
    with urllib.request.urlopen(server + "/", timeout=5) as resp:
        assert b"ATC" in resp.read()
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(server + "/../atcctl/server.py", timeout=5)
    assert e.value.code in (403, 404)
