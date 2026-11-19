#!/usr/bin/env bash
# RTL-SDR 동글에 고유 시리얼을 기록한다. (동글을 "한 개만" 꽂은 상태에서 실행)
#   sudo ./set-sdr-serial.sh 1090   # ADS-B/Mode S 용
#   sudo ./set-sdr-serial.sh AIR1   # 항공 VHF 채널 1
#   sudo ./set-sdr-serial.sh AIR2   # 항공 VHF 채널 2
set -euo pipefail
SERIAL="${1:?사용법: $0 <시리얼(예: 1090, AIR1)>}"

COUNT=$(rtl_test -t 2>&1 | grep -c "^  [0-9]*:" || true)
if [ "$COUNT" -ne 1 ]; then
  echo "오류: 동글이 정확히 1개만 연결되어 있어야 합니다 (현재 $COUNT 개)." >&2
  exit 1
fi

for svc in readsb atcctl; do systemctl stop "$svc" 2>/dev/null || true; done
echo "시리얼을 '$SERIAL' 로 기록합니다…"
rtl_eeprom -d 0 -s "$SERIAL"
echo "완료. 동글을 뺐다가 다시 꽂은 뒤 'rtl_test -t' 로 확인하세요."
