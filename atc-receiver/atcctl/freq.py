"""항공 주파수 파싱/검증 유틸리티.

지원 대역 (모두 AM 음성):
  - VHF 항공대역 : 118.000 ~ 136.990 MHz (25 kHz / 8.33 kHz 채널)
  - VOR/ATIS      : 108.000 ~ 117.975 MHz (일부 ATIS 음성 방송)
  - UHF 군용 항공 : 225.000 ~ 399.975 MHz
"""

from dataclasses import dataclass

BANDS_MHZ = {
    "vor": (108.000, 117.975),
    "vhf": (118.000, 136.990),
    "uhf": (225.000, 399.975),
}


class FrequencyError(ValueError):
    pass


@dataclass(frozen=True)
class Frequency:
    hz: int

    @property
    def mhz(self) -> float:
        return self.hz / 1e6

    @property
    def band(self) -> str:
        for name, (lo, hi) in BANDS_MHZ.items():
            if lo * 1e6 - 1 <= self.hz <= hi * 1e6 + 1:
                return name
        return "unknown"

    def label(self) -> str:
        return f"{self.mhz:.3f}"


def channel_name_to_hz(mhz: float) -> int:
    """8.33 kHz 채널 '이름'(예: 118.005)을 실제 반송파 주파수로 변환.

    8.33 kHz 채널은 25 kHz 블록마다 .x05/.x10/.x15 (+ .x00 = 25k 채널과 동일)
    로 표기되지만 실제 주파수는 25k 블록 시작점 + n * 8.333 kHz 이다.
    """
    khz = round(mhz * 1000)
    block = khz - (khz % 25)
    offset = khz % 25
    mapping = {0: 0, 5: 0, 10: 1, 15: 2, 20: None}
    n = mapping.get(offset)
    if n is None:
        # .x20 등 8.33 채널 이름이 아닌 값 -> 그대로 사용 (25k 그리드 외)
        return khz * 1000
    return block * 1000 + round(n * 25000 / 3)


def parse_frequency(value, allowed_bands=("vor", "vhf", "uhf")) -> Frequency:
    """'121.5', '121.500', 121500000, '118.005' 등을 받아 Frequency 반환."""
    if isinstance(value, str):
        value = value.strip().lower().replace("mhz", "").strip()
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise FrequencyError(f"주파수 형식이 올바르지 않습니다: {value!r}")

    if num > 1e5:  # Hz 단위로 들어온 경우
        hz = int(round(num))
    else:
        hz = channel_name_to_hz(num)

    f = Frequency(hz)
    if f.band not in allowed_bands:
        ranges = ", ".join(
            f"{BANDS_MHZ[b][0]:.3f}-{BANDS_MHZ[b][1]:.3f}" for b in allowed_bands
        )
        raise FrequencyError(f"허용 범위를 벗어났습니다 ({f.label()} MHz). 허용: {ranges}")
    return f
