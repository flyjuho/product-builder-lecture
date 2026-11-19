# ATC / ADS-B 원격 수신 시스템 (Raspberry Pi)

안테나 **1개**와 RTL-SDR 수신기 **여러 대**로

- **항공 무선(ATC) 음성 청취** — VHF 118–137 MHz (25 kHz / 8.33 kHz 채널), VOR/ATIS 108–118 MHz, UHF 군용 225–400 MHz
- **인터넷을 통한 원격 주파수 조정** — 웹 UI / REST API, 무선 네트워크(Wi-Fi/LTE) + Tailscale
- **ADS-B / Mode S / Mode A·C 수집** — readsb + tar1090 지도

을 라즈베리파이 한 대에서 동시에 수행합니다.

---

## 1. 전체 구성

```
                      ┌──────────────────────────────┐
  광대역 안테나        │        Raspberry Pi 5          │
 (디스콘 25–1300MHz)   │                                │
        │             │  readsb ──► /run/readsb/*.json │──► tar1090 지도 (:80/tar1090)
   저손실 동축          │    ▲ SDR "1090"                │
        │             │                                │
 [광대역 LNA + 바이어스T]│  atcctl (Python, :8080)        │
        │             │    ├─ rtl_fm ─► ffmpeg ─► MP3 ─┼──► 청취 스트림 /stream/atc1.mp3
  ┌─[4분배기]─┐         │    │    ▲ SDR "AIR1"           │
  │   │   │   │       │    └─ rtl_fm ─► ffmpeg ─► MP3 ─┼──► 청취 스트림 /stream/atc2.mp3
  │   │   │   └ (예비)  │         ▲ SDR "AIR2"           │
  │   │   └ FM노치+에어밴드BPF ─► RTL-SDR "AIR2"          │
  │   └──── FM노치+에어밴드BPF ─► RTL-SDR "AIR1"          │
  └──────── 1090MHz SAW 필터 ──► RTL-SDR "1090"          │
                      │  Wi-Fi / LTE ──► Tailscale ─────┼──► 원격지 스마트폰/PC
                      └──────────────────────────────┘
```

- 수신기 하나당 하나의 역할: `1090`(ADS-B), `AIR1`, `AIR2`(ATC 음성). 동글 EEPROM에 시리얼을 써서 **꽂는 순서와 무관하게** 역할이 고정됩니다.
- ATC 수신기를 더 늘리려면 분배기 포트를 늘리고 `config.json`의 `receivers`에 항목을 추가하면 됩니다.

## 2. 하드웨어 (BOM)

> 단계별 구축 순서, 추천 브랜드·가격·구매처는 **[docs/hardware-guide.md](docs/hardware-guide.md)** 를 참고하세요.
> (권장 신호 순서: 안테나 → 낙뢰보호 → **FM 노치 → LNA** → 분배기 → 분기별 대역 필터 → SDR)

| 구분 | 권장 품목 | 비고 |
|---|---|---|
| 컴퓨터 | Raspberry Pi 5 (4GB↑) 또는 Pi 4 | 공식 27W 전원, 방열 케이스 |
| 저장장치 | microSD 32GB (A2) 또는 USB SSD | 장기 운용 시 SSD 권장 |
| 안테나 | 광대역 **디스콘** (25–1300 MHz) | 한 안테나로 VHF/UHF/1090 커버. 최대한 높고 트인 곳 |
| 동축 | LMR-400 / 5D-FB 등 저손실 | 1090 MHz에서 손실이 크므로 짧게 |
| LNA | 광대역 LNA (바이어스-T 급전) | 안테나 쪽에 설치 → 분배 손실 보상 |
| 분배기 | 2/4분배 (Wilkinson, 5–2500 MHz) | 2분배 ≈ -3.5 dB, 4분배 ≈ -7 dB. **DC 패스 포트 1개** 있으면 LNA 급전 용이 |
| ADS-B 필터 | 1090 MHz SAW 필터 | 또는 필터 내장 동글(1090 전용 동글) 사용 |
| ATC 필터 | **FM 방송 노치(88–108 MHz)** + 에어밴드 BPF(118–137) | 근처 FM 방송국의 강한 신호로 인한 혼변조 방지 — 사실상 필수 |
| SDR | RTL-SDR v3/v4 × 3 (이상) | TCXO 내장 제품 권장(주파수 오차↓) |
| USB 허브 | **유전원** USB 허브 | 동글 3개 이상이면 Pi USB 전력 부족 |

> UHF 군용 대역(225–400 MHz)까지 듣고 싶다면 해당 분기에는 에어밴드 BPF 대신 FM 노치만 두거나, 별도 분배 포트를 UHF용으로 할당하세요.

### 단일 안테나 운용 팁
1. **LNA는 분배기 앞**에 둡니다. 분배·케이블 손실 이후에 증폭하면 잡음지수가 나빠집니다.
2. LNA 이득이 너무 크면 SDR이 포화됩니다. 각 SDR의 게인을 30–40 dB부터 시작해 낮춰보세요.
3. 사용하지 않는 분배기 포트는 **50Ω 더미 로드**로 종단합니다.
4. 1090 분기에만 SAW 필터를 넣고, ATC 분기에는 FM 노치를 넣으면 서로 간섭이 크게 줄어듭니다.

## 3. 설치

```bash
# Raspberry Pi OS Bookworm (64-bit) 기준
git clone <this repo> && cd <repo>/atc-receiver

# (1) 동글 시리얼 기록 — 반드시 한 개씩만 꽂고 실행
sudo apt-get install -y rtl-sdr
sudo ./scripts/set-sdr-serial.sh 1090   # ADS-B 동글
sudo ./scripts/set-sdr-serial.sh AIR1   # ATC 동글 1
sudo ./scripts/set-sdr-serial.sh AIR2   # ATC 동글 2

# (2) 전체 설치 (readsb, tar1090, atcctl, Tailscale)
sudo ./scripts/install.sh
```

설치가 끝나면 접속 토큰이 출력됩니다(`/etc/atcctl/config.json`의 `token`).

| 서비스 | 주소 |
|---|---|
| ATC 제어 / 청취 UI | `http://<pi>:8080` |
| ADS-B 지도 | `http://<pi>/tar1090` |

## 4. 네트워크 & 원격 접속

### 4-1. 무선 네트워크 연결 (Pi)
```bash
# Wi-Fi (Bookworm은 NetworkManager 사용)
sudo nmcli dev wifi connect "<SSID>" password "<비밀번호>"
nmcli -f NAME,AUTOCONNECT con show          # 자동 연결 확인

# 여러 AP 등록 시 우선순위
sudo nmcli con modify "<SSID>" connection.autoconnect-priority 10
```
- 현장에 인터넷이 없으면 **LTE 라우터(또는 USB LTE 모뎀)** 에 Pi를 Wi-Fi로 연결합니다.
- Wi-Fi 절전으로 끊기는 경우: `sudo iw wlan0 set power_save off`

### 4-2. 인터넷 원격 접속 — Tailscale (권장)
포트포워딩·공인 IP 없이, LTE의 CGNAT 환경에서도 동작합니다.
```bash
sudo tailscale up --ssh
tailscale ip -4        # 예: 100.x.y.z
```
원격 기기(스마트폰/PC)에도 Tailscale을 설치하고 같은 계정으로 로그인한 뒤
`http://100.x.y.z:8080` 으로 접속합니다. `tailscale ssh`로 원격 관리도 가능합니다.

> 공유기 포트포워딩으로 8080을 직접 인터넷에 여는 것은 권장하지 않습니다. 꼭 필요하다면
> HTTPS 리버스 프록시(Caddy 등) 뒤에 두고 강력한 토큰을 사용하세요.

## 5. 원격 주파수 조정

### 웹 UI
- 수신기 카드마다 **주파수 / 게인 / 스퀠치** 입력 → `변경`
- `▶ 청취`로 브라우저에서 실시간 청취 (튜닝하면 자동 재접속)
- 자주 쓰는 주파수는 **프리셋**으로 저장
- 같은 페이지 하단에 **ADS-B / Mode S 항공기 목록** (비상 스쿽 7500/7600/7700 강조)

### REST API
```bash
TOKEN=...; PI=100.x.y.z
# 상태
curl -H "Authorization: Bearer $TOKEN" http://$PI:8080/api/receivers
# 주파수 변경 (8.33 kHz 채널명 그대로 입력 가능: 예 "132.105")
curl -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"frequency":"118.100","gain":38,"squelch":40}' \
     http://$PI:8080/api/receivers/atc1/tune
# 청취 (VLC, mpv 등)
mpv "http://$PI:8080/stream/atc1.mp3?token=$TOKEN"
# ADS-B 요약
curl -H "Authorization: Bearer $TOKEN" http://$PI:8080/api/adsb
```

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/receivers` | 전체 수신기 상태 |
| POST | `/api/receivers/<id>/tune` | `frequency`, `gain`(0–50 또는 `auto`), `squelch`(0–1000) |
| POST | `/api/receivers/<id>/start` · `/stop` | 수신 시작/중지 |
| GET | `/stream/<id>.mp3` | 실시간 MP3 오디오 |
| GET/PUT | `/api/presets` | 프리셋 조회/저장 |
| GET | `/api/adsb` | readsb `aircraft.json` 요약 |

## 6. ADS-B / Mode S
- **readsb**가 시리얼 `1090` 동글로 DF17/18(ADS-B), DF4/5/20/21(Mode S 감시·Comm-B), DF11, Mode A/C를 디코딩합니다.
- 위치가 없는 항공기(ADS-B 미장착, Mode S 응답만)는 UI에 "Mode S 전용"으로 집계됩니다. 이런 항공기의 위치를 얻으려면 MLAT 네트워크 피딩이 필요합니다(선택).
- 데이터 위치: `/run/readsb/aircraft.json` (1초 갱신). 원시 Beast 출력은 TCP 30005, SBS(BaseStation)는 30003 포트 — 다른 프로그램/DB로 수집할 때 사용합니다.
  ```bash
  nc localhost 30003 | tee -a ~/sbs-$(date +%F).csv     # 간단 로그 수집 예시
  ```

## 7. 설정 파일 (`/etc/atcctl/config.json`)

```jsonc
{
  "port": 8080,
  "token": "긴-랜덤-문자열",
  "adsb_json": "/run/readsb/aircraft.json",
  "receivers": [
    { "id": "atc1", "name": "관제탑", "device": "AIR1",
      "frequency": "118.100", "gain": 40, "squelch": 0, "ppm": 0,
      "bitrate": "32k", "bands": ["vor", "vhf", "uhf"] }
  ]
}
```
- `device`: 동글 시리얼(권장) 또는 인덱스
- `ppm`: 동글 주파수 오차 보정값 (TCXO 동글은 0)
- `squelch`: 0이면 항상 열림. 잡음이 심하면 20–80 범위에서 조정
- 수신기 추가 = 동글 추가 + 시리얼 기록 + `receivers` 항목 추가 → `sudo systemctl restart atcctl`

## 8. 문제 해결

| 증상 | 확인 |
|---|---|
| `usb_claim_interface error -6` | DVB 드라이버 블랙리스트 후 재부팅, 동일 동글을 readsb와 atcctl이 같이 쓰지 않는지 확인 |
| 동글이 간헐적으로 사라짐 | 유전원 USB 허브 사용, `dmesg -w` 확인 |
| ATC가 지글거리고 엉뚱한 소리 | FM 노치 필터 장착, 게인 낮추기 |
| 주파수가 살짝 어긋남 | `ppm` 보정 (`rtl_test -p`로 측정) |
| 원격 접속 불가 | `tailscale status`, `systemctl status atcctl`, `journalctl -u atcctl -f` |

## 9. 개발 / 테스트

```bash
cd atc-receiver
python3 -m pytest -q tests          # SDR 없이 실행 (가짜 파이프라인 사용)
python3 -m atcctl -c config.json    # 로컬 실행
```
외부 의존성 없이 Python 표준 라이브러리만 사용합니다. 런타임에 `rtl_fm`, `ffmpeg`가 필요합니다.

## 10. 법적 유의사항
항공 무선 수신과 관련된 규정은 국가마다 다릅니다. 한국의 경우 **전파법**과 **통신비밀보호법**에 따라
수신한 통신 내용을 타인에게 누설하거나 녹음·공개 재전송하는 행위가 제한될 수 있습니다.
본 시스템은 **개인 청취 목적**으로 설계되었으며, 접근 토큰과 Tailscale로 본인만 접속하도록 운용하세요.
운용 전 관련 법령을 반드시 확인하시기 바랍니다.
