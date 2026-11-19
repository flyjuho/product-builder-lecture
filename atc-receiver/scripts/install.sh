#!/usr/bin/env bash
# 라즈베리파이 OS (Bookworm, 64-bit 권장) 설치 스크립트
#   sudo ./scripts/install.sh
# 설치 항목:
#   1) rtl-sdr 드라이버/도구, ffmpeg  (ATC 음성 수신)
#   2) readsb  (ADS-B / Mode S / Mode A/C 디코더, 시리얼 '1090' 동글 사용)
#   3) tar1090 (ADS-B 웹 지도, http://<pi>/tar1090)
#   4) atcctl  (원격 주파수 조정 + 오디오 스트리밍, http://<pi>:8080)
#   5) (선택) Tailscale - 포트포워딩 없이 인터넷 원격 접속
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then echo "sudo로 실행하세요." >&2; exit 1; fi
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ADSB_SERIAL="${ADSB_SERIAL:-1090}"
INSTALL_TAILSCALE="${INSTALL_TAILSCALE:-ask}"

echo "==> 1/5 패키지 설치"
apt-get update
apt-get install -y rtl-sdr ffmpeg python3 wget curl ca-certificates

echo "==> DVB-T 커널 드라이버 블랙리스트 (RTL-SDR 점유 방지)"
cat >/etc/modprobe.d/blacklist-rtlsdr.conf <<'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
blacklist rtl2832_sdr
EOF
modprobe -r dvb_usb_rtl28xxu rtl2832_sdr rtl2832 2>/dev/null || true

echo "==> 2/5 readsb 설치 (ADS-B / Mode S)"
if ! command -v readsb >/dev/null; then
  bash -c "$(wget -nv -O - https://github.com/wiedehopf/adsb-scripts/raw/master/readsb-install.sh)"
fi
# readsb가 시리얼 1090 동글만 사용하도록 고정 (ATC 동글과 충돌 방지)
if [ -f /etc/default/readsb ]; then
  sed -i "s|^RECEIVER_OPTIONS=.*|RECEIVER_OPTIONS=\"--device ${ADSB_SERIAL} --device-type rtlsdr --gain auto --ppm 0\"|" /etc/default/readsb
  systemctl restart readsb || true
fi

echo "==> 3/5 tar1090 설치 (ADS-B 웹 지도)"
if [ ! -d /usr/local/share/tar1090 ]; then
  bash -c "$(wget -nv -O - https://github.com/wiedehopf/tar1090/raw/master/install.sh)"
fi

echo "==> 4/5 atcctl 설치"
id atcctl >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin -G plugdev atcctl
install -d /opt/atcctl /etc/atcctl
cp -r "$SRC_DIR/atcctl" "$SRC_DIR/web" /opt/atcctl/
if [ ! -f /etc/atcctl/config.json ]; then
  TOKEN="$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"
  sed "s|CHANGE-ME-long-random-string|$TOKEN|" "$SRC_DIR/config.example.json" >/etc/atcctl/config.json
  echo "    접속 토큰: $TOKEN   (/etc/atcctl/config.json 에 저장됨)"
fi
[ -f /etc/atcctl/presets.json ] || cp "$SRC_DIR/presets.example.json" /etc/atcctl/presets.json
chown -R atcctl:atcctl /etc/atcctl
chmod 600 /etc/atcctl/config.json
install -m 644 "$SRC_DIR/systemd/atcctl.service" /etc/systemd/system/atcctl.service
systemctl daemon-reload
systemctl enable --now atcctl

echo "==> 5/5 원격 접속 (Tailscale)"
if [ "$INSTALL_TAILSCALE" = "ask" ]; then
  read -r -p "Tailscale을 설치할까요? [Y/n] " ans || ans=y
  [[ "${ans:-y}" =~ ^[Nn] ]] && INSTALL_TAILSCALE=no || INSTALL_TAILSCALE=yes
fi
if [ "$INSTALL_TAILSCALE" = "yes" ]; then
  command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
  echo "    다음 명령으로 로그인하세요:  sudo tailscale up --ssh"
fi

echo
echo "설치 완료."
echo "  - SDR 확인        : rtl_test -t   (시리얼 1090 / AIR1 / AIR2 가 보여야 함)"
echo "  - ATC 제어 UI     : http://$(hostname -I | awk '{print $1}'):8080"
echo "  - ADS-B 지도      : http://$(hostname -I | awk '{print $1}')/tar1090"
echo "  - 로그            : journalctl -u atcctl -f   /   journalctl -u readsb -f"
