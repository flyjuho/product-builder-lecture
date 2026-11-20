# 하드웨어 구축 가이드 — 단계별 구성 · 추천 장비 · 가격 · 구매처

> 조사 시점: 2026년 11월. 가격은 판매처 페이지 스냅샷 기준이며 수시로 바뀝니다. 원화 환산은 **1 USD ≈ 1,400원** 가정의 대략값입니다.
> **(추정)** 표시는 판매 페이지에서 가격을 확인하지 못해 일반 시세로 적은 값입니다.

> **SDR 단종 안내 (2026-11):** RTL-SDR Blog **V4는 2026년 5월 단종**(R828D 튜너 생산 종료), **V4L은 재고 한정**입니다. 제조사는 **V3(R860 튜너)를 계속 생산**한다고 밝혀, 이 문서는 V3 기준으로 바꿨습니다. 남은 V4 재고를 구하면 그대로 써도 됩니다. ([공지](https://www.rtl-sdr.com/rtl-sdr-blog-v4-end-of-line/))

---

## 0. 최종 목표 구성 (신호 흐름)

```
[디스콘 안테나] ──(짧은 저손실 동축)── [낙뢰보호기] ── [FM 노치 필터] ── [광대역 LNA]  ← 실외 방수함
                                                                          │ (바이어스-T 급전)
                                         실내 ───────── 저손실 동축 ─────────┘
                                                          │
                                                [바이어스-T 인젝터] (LNA 전원 공급)
                                                          │
                                                   [4분배기 5–2400MHz]
                         ┌──────────────────┬─────────────┴─────┬──────────────────┐
                 [1090 SAW 필터/프리앰프]  [에어밴드 BPF]      [에어밴드 BPF]       (예비: UHF 군용 → 50Ω 종단)
                         │                  │                   │
                 SDR "1090"            SDR "AIR1"           SDR "AIR2"
                         └──────── 유전원 USB 허브 ── Raspberry Pi 5 ── Wi-Fi/LTE ── Tailscale
```

**왜 이 순서인가**
1. **FM 노치를 LNA 앞에** — 근처 FM 방송(88–108 MHz)은 항공 신호보다 수십 dB 강합니다. LNA 뒤에 두면 LNA 자체가 포화되어 혼변조가 생기고, 그 뒤에서는 걸러낼 수 없습니다. FM 노치는 118 MHz 이상(항공·1090)에는 손실이 거의 없습니다.
2. **LNA는 안테나 바로 옆(분배기·케이블보다 앞)** — 4분배 손실(≈7 dB)과 케이블 손실을 증폭 전에 겪으면 잡음지수가 그만큼 나빠집니다.
3. **분배 후 각 분기에서 대역 필터** — ADS-B 분기는 1090 MHz만, ATC 분기는 118–137 MHz만 통과시켜 SDR끼리·대역끼리 간섭을 막습니다.

**손실 예산(대략)**: 4분배 −7 dB + 10 m 동축 @1090 MHz −2~3 dB(5D-FB 기준, 추정) + 커넥터 −1 dB ≈ **−10 dB**. LNA 이득 약 20 dB로 충분히 보상됩니다. 이득이 남아 SDR이 포화되면 SDR 게인을 낮추세요(오히려 LNA를 더 키우면 안 됩니다).

---

## 1단계 — 최소 구성으로 소프트웨어 검증 (실내, 하루)

목적: 라즈베리파이 + SDR 1대로 `atcctl`·`readsb`가 정상 동작하는지 먼저 확인. 이후 단계에서도 그대로 재사용하는 부품만 삽니다.

| 품목 | 추천 브랜드/모델 | 가격 | 구매처 |
|---|---|---|---|
| 컴퓨터 | **Raspberry Pi 5 8GB** | 177,518원 (VAT 포함) | [디바이스마트](https://www.devicemart.co.kr/goods/view?no=15392299), 엘레파츠, 아이씨뱅큐, [element14 KR](https://kr.element14.com/raspberry-pi/rpi5-8gb-single/rpi-5-board-2-4ghz-8gb-arm-cortex/dp/4256000), [RS코리아](https://kr.rs-online.com/web/p/raspberry-pi/0219255) |
| 전원 | Raspberry Pi 공식 27W USB-C PD 전원 | 약 2만원 (추정) | 위 국내 판매처 |
| 쿨러/케이스 | 공식 Active Cooler + 공식 케이스 | 약 1.5~2만원 (추정) | 위 국내 판매처 |
| 저장장치 | microSD 32–64GB A2 (Samsung PRO Plus, SanDisk Extreme) | 1~2만원 (추정) | 쿠팡/네이버 |
| SDR | **RTL-SDR Blog V3 (R860)** | 동글 약 $34.95 (공식 스토어) | [공식 스토어 rtl-sdr.com](https://www.rtl-sdr.com/), [공식 eBay](https://www.ebay.com/str/rtlsdrblog) |

- V3에 짧은 기본 안테나(또는 번들 다이폴)를 달아 창가에서 ATC·ADS-B를 각각 시험해 봅니다(1대로 번갈아).
- **1단계 예상 비용: 약 28~30만원**

> **짝퉁 주의**: 오픈마켓/해외 잡화몰(Fruugo 등)에 "for RTL SDR V3", "compatible" 등의 이름으로 올라온 상품은 정품이 아닐 수 있고 가격도 정품보다 비쌉니다(₩99,690~₩140,090 사례). **공식 스토어 또는 공식 eBay/AliExpress 공식점**에서 사세요.

---

## 2단계 — SDR 추가: ADS-B 전용 + ATC 다채널

| 역할 | 표준 추천 | 고급(성능 우선) | 가격 | 비고 |
|---|---|---|---|---|
| ADS-B / Mode S | RTL-SDR Blog V3 + **1090 필터 프리앰프** | **Airspy Mini** + 1090 필터 | V3 $35–40 / Airspy Mini $99 (세일 시 $79–84) | Airspy는 `airspy_adsb` 디코더로 RTL 대비 수신 메시지·거리가 확실히 좋음 |
| ATC 채널 1 | RTL-SDR Blog V3 | Airspy Mini | 동일 | V3도 1 PPM TCXO라 주파수 보정 거의 불필요 |
| ATC 채널 2 | RTL-SDR Blog V3 | RTL-SDR Blog V3 | $35–40 | 채널 늘릴 때마다 1대씩 추가 |

- **Airspy R2**($169, 세일 시 약 $135–144)는 대역폭 10 MHz가 장점이지만, 한 동글로 한 채널씩 듣는 이 시스템에선 Mini로 충분합니다. ([FlightAware 포럼 의견](https://discussions.flightaware.com/t/is-an-airspy-r2-worth-70-more-than-a-mini/94202))
- **FlightAware Pro Stick Plus**(1090 필터+LNA 내장 동글, 영국 £52.50)는 전용 1090 안테나에선 좋지만, **디스콘 같은 광대역 안테나에선 대역 외 신호로 포화되어 성능이 나빴다**는 리뷰가 있습니다. 단일 디스콘 구성에는 비추천. ([리뷰](https://www.rtl-sdr.com/flightaware-prostick-vs-flightaware-prostick-plus-review/))
- **2단계 예상 비용**: 표준(V3 ×2 추가) 약 11만원 / 고급(Airspy Mini ×2 + V3 ×1) 약 33만원 + 배송

**동글 시리얼 기록**: 새 동글을 하나씩 꽂고 `scripts/set-sdr-serial.sh 1090|AIR1|AIR2` 실행 (README 3장).

---

## 3단계 — 단일 안테나 + 분배 시스템 (실외 설치)

### 3-1. 안테나
| 추천 | 사양 | 가격 | 구매처 |
|---|---|---|---|
| **Diamond D-130J** (슈퍼 디스콘) | 25–1300 MHz 수신, 전장 1.7 m, 1 kg, 스테인리스 | $129.95–129.99 (미국), €139.90 (독일) | [DX Engineering](https://www.dxengineering.com/parts/dmn-d130j), [The Antenna Farm](https://theantennafarm.com/products/5015-diamond-d130j), [WiMo](https://www.wimo.com/fr/diamond-d-130j-discone-antenne), 국내 아마추어무선 용품점 |
| Diamond **D-130NJ** | 위와 동일, **N형 커넥터** | $149.95 | [ScannerMaster](https://scannermaster.com/D130NJ_Diamond_Super_Discone_Antenna_p/48-541857.htm) |

- **N형(D-130NJ) 추천** — 실외 방수·저손실 동축(LMR-400) 연결이 수월합니다.
- D-130J 기본 포함 RG-58 15 m 케이블은 1090 MHz에서 손실이 크므로(추정 −8 dB 이상) **사용하지 말고** 저손실 동축으로 교체하세요.
- 안테나는 무게·풍압(최대 지름 84 cm)을 고려해 견고한 마스트에, 주변보다 높고 트인 곳에 설치합니다. 1090 MHz는 가시거리 전파라 높이가 곧 수신 거리입니다.

### 3-2. 프런트엔드 (안테나 쪽, 방수함 안)
| 품목 | 추천 | 가격 | 구매처 |
|---|---|---|---|
| FM 노치 필터 | **RTL-SDR Blog Broadcast FM Band-Stop** (88–108 MHz 차단, SMA) | $16.95 (공식) / $17.95 (eBay) | [rtl-sdr.com](https://www.rtl-sdr.com/product/rtl-sdr-blog-broadcast-fm-band-stop-filter/), [eBay](https://www.ebay.com/itm/Broadcast-FM-Band-Stop-Filter-88-108-MHz-FM-Trap-by-RTL-SDR-Blog/282265486654) |
| 광대역 LNA | **RTL-SDR Blog Wideband LNA V2** (50 MHz–4 GHz, NF < 1 dB, 3–5 V 바이어스-T 급전) | $19.95 | [rtl-sdr.com](https://www.rtl-sdr.com/product/rtl-sdr-blog-wideband-lna-bias-tee-powered/) |
| (대안) FM노치+LNA 일체형 | GPIO Labs FM Notch + LNA (20 dB, 바이어스-T) | Tindie 페이지 확인 | [Tindie](https://www.tindie.com/products/gpio/fm-notch-filter-with-low-noise-amplifier-lna-3-ghz/) |
| 낙뢰보호기 | N형 동축 서지 어레스터 (DC 패스형 — LNA 급전 통과 필수) + 접지선 | 3~6만원 (추정) | 국내 무선용품점, 해외 DX Engineering 등 |
| 방수함 | IP65 이상 ABS 정션박스 + 방수 케이블 글랜드 | 1~2만원 (추정) | 쿠팡/네이버 |

> 낙뢰보호기는 **반드시 DC-pass 타입**이어야 LNA에 전원이 갑니다. 가스방전관(GDT)형 중 DC 블록형은 LNA 급전을 막습니다.

### 3-3. 동축 케이블
| 품목 | 추천 | 가격 |
|---|---|---|
| 메인 동축 (실외→실내) | **LMR-400** 또는 **5D-FB / 8D-FB** (N형 커넥터 압착 완제품 권장) | 5D-FB 완제품 10 m 약 3~5만원 (추정) |
| 실내 점퍼 | RG-316 / RG-174 SMA 점퍼 15–30 cm | 개당 3~5천원 (추정) |
| 어댑터 | N-SMA, SMA M-M/F-F 세트 | 1만원 내외 (추정) |

- **길이는 가능한 짧게.** 10 m를 넘으면 8D-FB/LMR-400을 쓰세요.

### 3-4. 실내 분배부
| 품목 | 추천 | 가격 | 비고 |
|---|---|---|---|
| 바이어스-T 인젝터 | USB 전원형 바이어스-T (GPIO Labs, Nooelec 등) | $15–30 (추정) | LNA 전원. 또는 DC 패스 포트가 있는 분배기 + V4의 내장 바이어스-T 사용 |
| 4분배기 | **5–2400 MHz** 대역, DC 패스 1포트 (위성방송용 분배기도 수신 용도엔 실사용 가능, 75 Ω) / 50 Ω 계측용(Mini-Circuits 등) | 위성용 수천원~1만원 (추정) / Mini-Circuits $100 이상 | ⚠️ **Mini-Circuits ZFSC-4-1은 1 GHz까지만 지원** → 1090 MHz 불가. 반드시 **1090 MHz를 포함하는 모델**을 고르세요 |
| ADS-B 필터 | **Uputronics ADS-B 1090 MHz Filtered Preamp** (게인 ≥14 dB, NF 0.75 dB) 또는 **RTL-SDR Blog ADS-B Triple Filtered LNA** | £44.40 ([The Pi Hut](https://thepihut.com/products/ads-b-1090mhz-filtered-preamplifier)) / $39.95 (재고 수시 품절) | 1090 분기에 장착. 바이어스-T 급전 |
| 에어밴드 BPF ×2 | **GPIO Labs Airband Bandpass Filter 118–138 MHz** (FM 대역 차단 우수) | Tindie 페이지 확인 (추정 $20–30) | [Tindie](https://www.tindie.com/products/gpio/airband-bandpass-filter-118-138-mhz) |
| 50 Ω 더미로드 | SMA 50 Ω 종단기 | 개당 3~5천원 (추정) | 안 쓰는 분배 포트에 장착 |

> UHF 군용(225–400 MHz)도 들으려면 예비 포트에 에어밴드 BPF **없이** SDR을 하나 더 연결하세요(FM 노치는 이미 앞단에 있음).

- **3단계 예상 비용**: 약 50~70만원 (안테나 D-130NJ + 프런트엔드 + 케이블 + 필터 + 배송/관세 포함)

---

## 4단계 — 안정화 · 원격 운용

| 품목 | 추천 | 가격 | 이유 |
|---|---|---|---|
| 유전원 USB 허브 | 개별 전원 스위치형 USB 3.0 4포트, 어댑터 5V 3A 이상 (ORICO, UGREEN 등) | 2~4만원 (추정) | SDR 3대 이상이면 Pi USB 전력 부족 → 동글이 끊김 |
| USB 연장/페라이트 | 짧은 USB 연장선 + 페라이트 코어 | 1만원 (추정) | 동글끼리 붙어 발열·간섭 방지 |
| 저장장치 업그레이드 | USB SSD 128–256GB 또는 Pi 5용 NVMe HAT + SSD | 4~8만원 (추정) | microSD 장기 운용 시 손상 위험 |
| 무정전 | 소형 UPS 또는 Pi용 UPS HAT | 4~10만원 (추정) | 정전 후 자동 복구·SD 손상 방지 |
| 인터넷(현장) | LTE 라우터 + 데이터 유심 | 라우터 5~10만원 (추정) | 집 Wi-Fi가 없는 설치 장소 |
| 원격 접속 | **Tailscale** (개인 무료 플랜) | 무료 | 포트포워딩 없이 접속 |

---

## 5. 구성별 총비용 요약 (대략)

| 구성 | 내용 | 예상 총액 |
|---|---|---|
| **입문** | Pi 5 + V3 ×3 + 기본 다이폴/소형 디스콘(실내·창가) + FM 노치 + 유전원 허브 | **약 55~65만원** |
| **권장 (이 문서의 표준)** | Pi 5 + V3 ×3 + D-130NJ + FM노치 + 광대역 LNA + 바이어스-T + 4분배기 + 1090 프리앰프 + 에어밴드 BPF ×2 + LMR-400/5D-FB + 낙뢰보호 + 허브/SSD | **약 100~120만원** |
| **고급** | 권장 + Airspy Mini ×2 (ADS-B·ATC1) + 8D-FB/LMR-400 + UPS + LTE | **약 140~170만원** |

---

## 6. 구매 방법 & 해외직구 체크리스트

1. **국내 구매**: 라즈베리파이·전원·케이스·SD·USB 허브 — 디바이스마트, 엘레파츠, 아이씨뱅큐, element14 KR, RS코리아, 쿠팡/네이버.
2. **해외 공식 구매**
   - RTL-SDR Blog(V3, FM 노치, LNA): [rtl-sdr.com 공식 스토어](https://www.rtl-sdr.com/) 또는 [공식 eBay](https://www.ebay.com/str/rtlsdrblog) — 대부분 국가 무료배송.
   - Airspy: [airspy.com](https://airspy.com/airspy-mini/)의 공식 리셀러 목록에서 구매. 매년 **여름(6월 말–7월 초) 20%**, **블랙프라이데이 15%** 세일이 있어 이때가 저렴합니다. ([2026 여름 세일](https://www.rtl-sdr.com/airspy-2026-summer-sale-20-off-all-airspy-products/))
   - GPIO Labs 필터/LNA: [Tindie](https://www.tindie.com/products/gpio/airband-bandpass-filter-118-138-mhz) — 국제배송 가능 여부를 상품 페이지에서 확인.
   - Uputronics 1090 프리앰프: [The Pi Hut(영국)](https://thepihut.com/products/ads-b-1090mhz-filtered-preamplifier).
   - Diamond 안테나: 국내 아마추어무선 용품점 먼저 확인 → 없으면 [DX Engineering](https://www.dxengineering.com/parts/dmn-d130j)/[WiMo](https://www.wimo.com/fr/diamond-d-130j-discone-antenne). 길이 1.7 m 장척물이라 **배송비가 큽니다** — 배송비 포함 비교 필수.
3. **관세·통관**
   - 자가사용 목록통관 면세 한도: **물품가 150달러 이하, 미국발 200달러 이하**(국제배송비 제외). 우편·특송별 적용이 다를 수 있으니 [관세청 예상세액 조회](https://www.customs.go.kr/kcs/ad/tax/BuyTaxCalculation.do?mi=2853)에서 확인.
   - **합산과세 주의**: 같은 판매자에게 같은 날 결제한 물건을 나눠 받아도 합산되어 한도를 넘으면 전액 과세됩니다. 공식 스토어 주문은 한도 안에서 나눠 날짜를 달리하세요.
   - **개인통관고유부호**: 2026년부터 유효기간이 생겼습니다(신규 발급 시 1년). 주문 전 유효한지 확인.
   - **전파 적합성평가**: 수신 전용 장치의 자가사용 직구 취급은 품목별로 다를 수 있습니다. 대량·재판매가 아닌 개인 1대 사용이 원칙이며, 확실하지 않으면 국립전파연구원에 확인하세요.

---

## 7. 단계별 체크리스트

- [ ] **1단계**: Pi 5 + V3 1대로 `install.sh` 설치, 창가 다이폴로 121.5 MHz / tar1090 지도 확인
- [ ] **2단계**: V3(또는 Airspy) 추가, 시리얼 `1090`/`AIR1`/`AIR2` 기록, `rtl_test -t`로 3대 인식 확인
- [ ] **3단계**: D-130NJ 설치 → 낙뢰보호 → FM 노치 → LNA(방수함) → 동축 → 바이어스-T → 4분배 → 분기별 필터
  - 설치 후 비교: LNA 전원 ON/OFF 상태에서 tar1090의 메시지 수·최대 거리, ATC 잡음 수준 확인
  - 포화 증상(잡음 증가, 유령 신호) → SDR 게인을 30 dB 이하로 낮춤
- [ ] **4단계**: 유전원 허브, SSD, UPS, Tailscale 접속 확인, 재부팅 후 자동 복구 확인

## 참고 출처
- RTL-SDR Blog V3: [공식 eBay 스토어](https://www.ebay.com/str/rtlsdrblog), [V4 단종 공지](https://www.rtl-sdr.com/rtl-sdr-blog-v4-end-of-line/), [Hackster.io 보도](https://www.hackster.io/news/rtl-sdr-com-announces-the-end-of-the-line-for-its-popular-rtl-sdr-blog-v4-software-defined-radio-76f628f18e0d)
- Airspy: [Airspy Mini](https://airspy.com/airspy-mini/), [Airspy R2](https://airspy.com/airspy-r2/), [2026 여름 세일](https://www.rtl-sdr.com/airspy-2026-summer-sale-20-off-all-airspy-products/), [Airspy Mini 리뷰](https://www.rtl-sdr.com/review-airspy-mini/)
- FlightAware Pro Stick Plus: [The Pi Hut](https://thepihut.com/products/flightaware-pro-stick-plus-usb-sdr-ads-b-receiver/), [Pro Stick vs Plus 리뷰](https://www.rtl-sdr.com/flightaware-prostick-vs-flightaware-prostick-plus-review/)
- Diamond D-130J: [DX Engineering](https://www.dxengineering.com/parts/dmn-d130j), [WiMo](https://www.wimo.com/fr/diamond-d-130j-discone-antenne), [ScannerMaster D130NJ](https://scannermaster.com/D130NJ_Diamond_Super_Discone_Antenna_p/48-541857.htm), [제조사 사양](https://diamond-ant.co.jp/english/amateur/antenna/ante_6dis.html)
- 필터/LNA: [RTL-SDR Blog FM 노치](https://www.rtl-sdr.com/product/rtl-sdr-blog-broadcast-fm-band-stop-filter/), [RTL-SDR Blog Wideband LNA](https://www.rtl-sdr.com/product/rtl-sdr-blog-wideband-lna-bias-tee-powered/), [RTL-SDR Blog ADS-B Triple Filtered LNA](https://www.rtl-sdr.com/product/rtl-sdr-blog-ads-b-triple-filtered-lna-bias-tee-powered/), [ADS-B 1090 Filtered Preamp (The Pi Hut)](https://thepihut.com/products/ads-b-1090mhz-filtered-preamplifier), [GPIO Labs 에어밴드 BPF](https://www.tindie.com/products/gpio/airband-bandpass-filter-118-138-mhz), [GPIO Labs 에어밴드 LNA](https://www.tindie.com/products/gpio/airband-pre-filtered-lna-w-bias-tee-118-140-mhz)
- 분배기: [Mini-Circuits ZFSC-4-1 (DigiKey)](https://www.digikey.com.au/en/products/detail/mini-circuits/ZFSC-4-1-S/21727833)
- Raspberry Pi 5: [디바이스마트](https://www.devicemart.co.kr/goods/view?no=15392299), [element14 KR](https://kr.element14.com/raspberry-pi/rpi5-8gb-single/rpi-5-board-2-4ghz-8gb-arm-cortex/dp/4256000)
- 통관: [관세청 예상세액 조회](https://www.customs.go.kr/kcs/ad/tax/BuyTaxCalculation.do?mi=2853), [2026 직구 면세·합산과세 정리](https://braindetox.kr/posts/black_friday_2026_overseas_direct_purchase_customs_limit.html)
