"""SDR 1대 = 수신 채널 1개. rtl_fm(AM 복조) -> ffmpeg(MP3) 파이프라인을 관리하고
인코딩된 오디오를 접속한 모든 청취자에게 분배한다.

주파수/게인/스퀠치 변경 시 파이프라인을 재시작한다(약 0.5~1초 끊김).
"""

import queue
import shlex
import subprocess
import threading
import time

from .freq import Frequency, parse_frequency

CHUNK = 1024


class Receiver:
    def __init__(self, cfg: dict):
        self.id = cfg["id"]
        self.name = cfg.get("name", self.id)
        self.device = str(cfg.get("device", "0"))  # rtl-sdr 시리얼 또는 인덱스
        self.ppm = int(cfg.get("ppm", 0))
        self.gain = cfg.get("gain", "auto")
        self.squelch = int(cfg.get("squelch", 0))
        self.bitrate = cfg.get("bitrate", "32k")
        self.allowed_bands = tuple(cfg.get("bands", ["vor", "vhf", "uhf"]))
        # 테스트/대체 SDR용: {freq_hz} 등 치환 가능한 단일 명령어
        self.command_override = cfg.get("command")
        self.freq: Frequency = parse_frequency(cfg.get("frequency", "121.5"), self.allowed_bands)

        self._lock = threading.RLock()
        self._procs: list[subprocess.Popen] = []
        self._reader: threading.Thread | None = None
        self._listeners: set[queue.Queue] = set()
        self._generation = 0
        self.started_at: float | None = None
        self.last_error: str | None = None

    # ---------- 파이프라인 ----------
    def build_commands(self) -> list[list[str]]:
        params = {
            "freq_hz": self.freq.hz,
            "freq_mhz": self.freq.label(),
            "device": self.device,
            "gain": self.gain,
            "squelch": self.squelch,
            "ppm": self.ppm,
            "bitrate": self.bitrate,
        }
        if self.command_override:
            return [shlex.split(self.command_override.format(**params))]

        rtl = [
            "rtl_fm", "-d", self.device, "-M", "am",
            "-f", str(self.freq.hz), "-s", "12k", "-r", "12k",
            "-p", str(self.ppm), "-l", str(self.squelch), "-E", "dc",
        ]
        if str(self.gain) != "auto":
            rtl += ["-g", str(self.gain)]
        rtl.append("-")
        ff = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "s16le", "-ar", "12000", "-ac", "1", "-i", "-",
            "-af", "highpass=f=200,lowpass=f=3500",
            "-ar", "22050", "-c:a", "libmp3lame", "-b:a", self.bitrate,
            "-f", "mp3", "-",
        ]
        return [rtl, ff]

    def start(self):
        with self._lock:
            self._stop_locked()
            cmds = self.build_commands()
            procs = []
            stdin = None
            try:
                for i, cmd in enumerate(cmds):
                    p = subprocess.Popen(
                        cmd, stdin=stdin, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, bufsize=0,
                    )
                    if stdin is not None:
                        stdin.close()  # 이전 프로세스 stdout은 다음 프로세스가 소유
                    stdin = p.stdout if i < len(cmds) - 1 else None
                    procs.append(p)
            except OSError as e:
                for p in procs:
                    p.kill()
                self.last_error = f"실행 실패: {e}"
                raise
            self._procs = procs
            self._generation += 1
            self.started_at = time.time()
            self.last_error = None
            gen = self._generation
            self._reader = threading.Thread(
                target=self._pump, args=(procs[-1], gen), daemon=True
            )
            self._reader.start()

    def _pump(self, proc: subprocess.Popen, gen: int):
        while True:
            data = proc.stdout.read(CHUNK)
            if not data:
                break
            for q in list(self._listeners):
                try:
                    q.put_nowait(data)
                except queue.Full:
                    pass  # 느린 클라이언트는 프레임 드롭
        with self._lock:
            if gen == self._generation and self._procs:
                self.last_error = f"파이프라인 종료 (exit={proc.poll()})"

    def _stop_locked(self):
        for p in self._procs:
            if p.poll() is None:
                p.terminate()
        for p in self._procs:
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
        self._procs = []

    def stop(self):
        with self._lock:
            self._generation += 1
            self._stop_locked()

    @property
    def running(self) -> bool:
        return bool(self._procs) and all(p.poll() is None for p in self._procs)

    # ---------- 제어 ----------
    def tune(self, frequency=None, gain=None, squelch=None) -> dict:
        with self._lock:
            if frequency is not None:
                self.freq = parse_frequency(frequency, self.allowed_bands)
            if gain is not None:
                if str(gain) != "auto":
                    g = float(gain)
                    if not 0 <= g <= 50:
                        raise ValueError("gain은 0~50 dB 또는 'auto'")
                    gain = g
                self.gain = gain
            if squelch is not None:
                s = int(squelch)
                if not 0 <= s <= 1000:
                    raise ValueError("squelch는 0~1000")
                self.squelch = s
            self.start()
            return self.status()

    def status(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "device": self.device,
            "frequency_mhz": self.freq.label(),
            "frequency_hz": self.freq.hz,
            "band": self.freq.band,
            "gain": self.gain,
            "squelch": self.squelch,
            "running": self.running,
            "listeners": len(self._listeners),
            "started_at": self.started_at,
            "error": self.last_error,
        }

    # ---------- 청취자 ----------
    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=256)
        self._listeners.add(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        self._listeners.discard(q)
