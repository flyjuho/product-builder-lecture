"""ATC 원격 수신 제어 서버 (표준 라이브러리만 사용).

엔드포인트
  GET  /                              웹 UI
  GET  /api/receivers                 모든 수신기 상태
  POST /api/receivers/<id>/tune       {"frequency": "118.1", "gain": 40, "squelch": 50}
  POST /api/receivers/<id>/stop
  GET  /stream/<id>.mp3               실시간 오디오 (MP3)
  GET  /api/presets                   프리셋 목록
  PUT  /api/presets                   프리셋 전체 저장 [{"name":..,"frequency":..}]
  GET  /api/adsb                      readsb aircraft.json 요약 (ADS-B / Mode S)

인증: config의 "token"이 설정되어 있으면 `Authorization: Bearer <token>` 헤더 또는
`?token=<token>` 쿼리(오디오 태그용)가 필요하다.
"""

import argparse
import hmac
import json
import mimetypes
import os
import queue
import re
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .freq import FrequencyError
from .receiver import Receiver

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class App:
    def __init__(self, config: dict, config_dir: Path):
        self.config = config
        self.token = config.get("token") or os.environ.get("ATCCTL_TOKEN") or ""
        self.receivers = {r["id"]: Receiver(r) for r in config.get("receivers", [])}
        self.presets_path = config_dir / config.get("presets_file", "presets.json")
        self.adsb_json = Path(config.get("adsb_json", "/run/readsb/aircraft.json"))
        self.tar1090_url = config.get("tar1090_url", "/tar1090/")
        self._presets_lock = threading.Lock()

    def start_all(self):
        for r in self.receivers.values():
            try:
                r.start()
            except OSError as e:
                print(f"[{r.id}] 시작 실패: {e}", file=sys.stderr)

    def stop_all(self):
        for r in self.receivers.values():
            r.stop()

    # presets
    def load_presets(self) -> list:
        try:
            return json.loads(self.presets_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []

    def save_presets(self, presets: list):
        if not isinstance(presets, list) or not all(
            isinstance(p, dict) and "name" in p and "frequency" in p for p in presets
        ):
            raise ValueError("프리셋 형식: [{\"name\": str, \"frequency\": str}, ...]")
        with self._presets_lock:
            tmp = self.presets_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.presets_path)

    # ADS-B
    def adsb_summary(self) -> dict:
        try:
            data = json.loads(self.adsb_json.read_text())
        except FileNotFoundError:
            return {"available": False, "aircraft": [], "error": f"{self.adsb_json} 없음 (readsb 실행 확인)"}
        except json.JSONDecodeError:
            return {"available": False, "aircraft": [], "error": "aircraft.json 파싱 실패"}
        out = []
        for a in data.get("aircraft", []):
            out.append({
                "hex": a.get("hex"),
                "flight": (a.get("flight") or "").strip(),
                "squawk": a.get("squawk"),
                "alt": a.get("alt_baro"),
                "gs": a.get("gs"),
                "track": a.get("track"),
                "lat": a.get("lat"),
                "lon": a.get("lon"),
                "type": a.get("type"),  # adsb_icao / mode_s / mlat ...
                "rssi": a.get("rssi"),
                "seen": a.get("seen"),
                "messages": a.get("messages"),
            })
        out.sort(key=lambda x: (x["seen"] if x["seen"] is not None else 1e9))
        with_pos = sum(1 for a in out if a["lat"] is not None)
        return {
            "available": True,
            "now": data.get("now"),
            "messages": data.get("messages"),
            "total": len(out),
            "with_position": with_pos,
            "mode_s_only": len(out) - with_pos,
            "aircraft": out,
            "tar1090_url": self.tar1090_url,
        }


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "atcctl/1.0"

        def log_message(self, fmt, *args):
            if os.environ.get("ATCCTL_QUIET"):
                return
            super().log_message(fmt, *args)

        # ---------- helpers ----------
        def _json(self, obj, status=200):
            body = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _error(self, status, msg):
            self._json({"error": msg}, status)

        def _authorized(self) -> bool:
            if not app.token:
                return True
            auth = self.headers.get("Authorization", "")
            given = auth[7:] if auth.startswith("Bearer ") else ""
            if not given:
                given = parse_qs(urlparse(self.path).query).get("token", [""])[0]
            return hmac.compare_digest(given.encode(), app.token.encode())

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 65536:
                raise ValueError("요청 본문이 너무 큽니다")
            raw = self.rfile.read(n) if n else b"{}"
            return json.loads(raw or b"{}")

        def _receiver(self, rid):
            r = app.receivers.get(rid)
            if not r:
                self._error(404, f"수신기 없음: {rid}")
            return r

        # ---------- routes ----------
        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/" or not (path.startswith("/api/") or path.startswith("/stream/")):
                return self._static(path)
            if not self._authorized():
                return self._error(401, "인증 필요")
            if path == "/api/receivers":
                return self._json([r.status() for r in app.receivers.values()])
            if path == "/api/presets":
                return self._json(app.load_presets())
            if path == "/api/adsb":
                return self._json(app.adsb_summary())
            m = re.fullmatch(r"/stream/([\w-]+)\.mp3", path)
            if m:
                r = self._receiver(m.group(1))
                if r:
                    self._stream(r)
                return
            self._error(404, "not found")

        def do_POST(self):
            path = urlparse(self.path).path
            if not self._authorized():
                return self._error(401, "인증 필요")
            m = re.fullmatch(r"/api/receivers/([\w-]+)/(tune|stop|start)", path)
            if not m:
                return self._error(404, "not found")
            r = self._receiver(m.group(1))
            if not r:
                return
            try:
                if m.group(2) == "tune":
                    b = self._body()
                    st = r.tune(b.get("frequency"), b.get("gain"), b.get("squelch"))
                elif m.group(2) == "start":
                    r.start()
                    st = r.status()
                else:
                    r.stop()
                    st = r.status()
            except (FrequencyError, ValueError) as e:
                return self._error(400, str(e))
            except OSError as e:
                return self._error(500, f"SDR 실행 실패: {e}")
            self._json(st)

        def do_PUT(self):
            path = urlparse(self.path).path
            if not self._authorized():
                return self._error(401, "인증 필요")
            if path != "/api/presets":
                return self._error(404, "not found")
            try:
                app.save_presets(self._body())
            except (ValueError, json.JSONDecodeError) as e:
                return self._error(400, str(e))
            self._json(app.load_presets())

        def _stream(self, r: Receiver):
            q = r.subscribe()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Cache-Control", "no-cache, no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    try:
                        chunk = q.get(timeout=15)
                    except queue.Empty:
                        if not r.running:
                            break
                        continue
                    self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                r.unsubscribe(q)

        def _static(self, path):
            rel = "index.html" if path in ("", "/") else path.lstrip("/")
            target = (WEB_DIR / rel).resolve()
            if WEB_DIR not in target.parents and target != WEB_DIR / "index.html":
                return self._error(403, "forbidden")
            if not target.is_file():
                return self._error(404, "not found")
            body = target.read_bytes()
            ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    ap = argparse.ArgumentParser(description="ATC 원격 수신 제어 서버")
    ap.add_argument("-c", "--config", default="/etc/atcctl/config.json")
    ap.add_argument("--host", default=None)
    ap.add_argument("--port", type=int, default=None)
    args = ap.parse_args(argv)

    cfg_path = Path(args.config)
    cfg = load_config(cfg_path)
    app = App(cfg, cfg_path.parent)
    host = args.host or cfg.get("host", "0.0.0.0")
    port = args.port or int(cfg.get("port", 8080))

    if not app.token:
        print("경고: token 미설정 - 인터넷 노출 시 반드시 설정하세요.", file=sys.stderr)

    app.start_all()
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    httpd.daemon_threads = True
    print(f"atcctl listening on http://{host}:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop_all()
        httpd.server_close()


if __name__ == "__main__":
    main()
