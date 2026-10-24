# WS-2000 / WH31L public samples

Research date: 2026-10-23. These are public reference examples, NOT data collected from Bobby's station. No station account, API key, radio hardware, or production system was accessed. Repository/Drive planning artifacts were not changed.

## Files and evidentiary status

### ambient_official_api_excerpt.json
A ten-field excerpt, preserving names and values, from Ambient Weather's official `Query Device Data` JSON example. The original is dated 2018-01-08 and is generic: it does not identify a WS-2000 or include lightning. This excerpt is not a complete schema.
Source: https://github.com/ambient-weather/api-docs/blob/master/apiary.apib
Reference: https://ambientweather.docs.apiary.io/

### wh65b_upstream_fixture.json
Complete, unchanged 276-byte expected-decoder-output fixture from the rtl_433 project's public test repository. Content was retrieved through the GitHub connector and independently checked against Git blob SHA-1 `2e686a5d0e84f7a1c24e653f9c366c59814b49e0` using Git's blob framing. This is a sensor-family regression fixture, not a capture from the user's WS-2000. Its `time` is an offset within a recording, NOT UTC. No RF replay was performed here.
Source: https://github.com/merbanan/rtl_433_tests/blob/master/tests/fineoffset/fineoffset_wh65b/01/g001_915.05M_250k.json
Companion capture/readme directory: https://github.com/merbanan/rtl_433_tests/tree/master/tests/fineoffset/fineoffset_wh65b/01

### wh31l_reconstructed_from_upstream_packet.json
DERIVED example, not a verbatim JSON capture. Reconstructed from the nine-byte sample `57 81 05 c8 05 81 01 df 0b` published in the upstream WH31L decoder. Its CRC-8 (polynomial 0x31, initialization 0) over the first eight bytes and additive checksum were independently checked in Python. Bit-field extraction follows the cited decoder. This is NOT evidence that rtl_433 has been executed successfully on the user's detector.
Source: https://github.com/merbanan/rtl_433/blob/master/src/devices/fineoffset_wh31l.c
Source license: GPL-2.0-or-later; Copyright (C) 2021 Christian W. Zuckschwerdt, based on protocol analysis by @MksRasp.
`flags` is numeric here; hexadecimal presentation is 0x8058. `battery_ok=1.0` is the decoder's normalized level value, not a claimed battery-charge percentage. The raw eight-bit counter is NOT automatically a daily/hourly count. No UTC strike timestamp is present in this sample packet. The decoder omits `storm_dist_km` when the encoded distance is 63 (invalid/no strike).

## Manufacturer sample with lightning
WH31L manual, page 6, Figure 4: displayed count 10, distance 26 km, last strike 3 minutes ago. This is a manufacturer illustration, not a downloaded time series. Manual page 6 describes a daily count; newer WS-2000 manual page 24 describes hourly strikes. Preserve the declared count window rather than silently treating these as identical.
https://ambientweather.com/mwdownloads/download/link/id/587

## Controlling external references
- Official WS-2000 manual v2.20 (2025), page 24 display inventory and page 69 archive header inventory: https://ambientweather.com/mwdownloads/download/link/id/1113
- Manufacturer CSV field reference, including WH31L columns 35/36 in the accessory archive: https://ambientweather.com/faqs/question/view/id/1567/
- Official API field dictionary (all compatible devices, not a WS-2000-specific guarantee): https://github.com/ambient-weather/api-docs/wiki/Device-Data-Specs
- WS-2000 hardware description: https://ambientweather.com/ws-2000-smart-weather-station
- WH31L capabilities and limitations: https://ambientweather.com/wh31l-lightning-detector

## Integration cautions
API, console CSV and raw RF are distinct representations. In particular, the API `uv` is an index, but the WH65B decoder's `uv` is a raw UV value and its `uvi` is the index. `light_lux` is not the same unit as API `solarradiation` (W/m2). Rain counters require time-window calculations for rates and totals. Pressure in the standard WS-2000 system comes from its separate indoor WH32B sensor, not the WH65B outdoor packet. The WH31L is a separate transmitter and does not supply strike direction or coordinates. A temperature/humidity-derived lightning icon is not a detected strike.

No fully populated, device-identified WS-2000 + WH31L cloud payload was verified during this research. The files intentionally do not fabricate such a combined record.
