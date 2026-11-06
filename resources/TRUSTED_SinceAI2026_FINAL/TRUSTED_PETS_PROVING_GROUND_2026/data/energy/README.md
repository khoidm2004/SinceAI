# Energy — hourly smart-meter data (synthetic)

**Controller (fictional):** Lounaisvirta Verkko Oy, an electricity distribution system operator (DSO) in Southwest Finland.
**Period:** 1 Dec 2025 – 28 Feb 2026, hourly. Local time (Europe/Helsinki); no daylight-saving change in this period.
Everything is synthetic. Postcodes are real; households, consumption and weather are generated.

## Tables
| table | rows | what it is |
|---|---|---|
| customers.csv | 757 | one row per household contract: contact details, address, heating, EV, PV, payment status, operator notes |
| meter_readings_hourly.csv | 1,635,120 | net kWh per metering point and hour, with quality flag |
| weather_hourly.csv | 2,160 | **synthetic** Turku-area temperature, wind and cloud cover (context; not personal data) |

Join: `meter_readings_hourly.metering_point_id` → `customers.metering_point_id`.

## How the load was generated
Appliance load follows household size and a daily/weekly profile. Heating load is `UA × (indoor − outdoor)` divided by a
temperature-dependent COP for heat pumps; direct-electric storage heating buys most energy at night. Sauna sessions (mostly
Saturday evening), EV charging (some price-optimised at 01–03), Christmas absences and visitors, the ski-holiday week
(14–22 Feb 2026), night-shift households and meter faults are included. A cold spell on 6–13 Jan 2026 drives the peak.

## Sharing scenarios
- **ENERGY-S1 — Open data: neighbourhood electricity load.** Anyone (municipal open-data portal). Utility: ENERGY-U1, ENERGY-U2, ENERGY-U3.
- **ENERGY-S2 — Row-level hourly data to a flexibility aggregator.** Demand-response aggregator (processor under contract). Utility: ENERGY-U2, ENERGY-U4, ENERGY-U5, ENERGY-U6.
- **ENERGY-S3 — Energy-poverty research dataset.** University research group (controlled research environment). Utility: ENERGY-U3, ENERGY-U4, ENERGY-U7.

## Utility tasks (pets_eval.utility.energy)
- ENERGY-U1 mean load per 3-digit postcode area × hour of day
- ENERGY-U2 system peak hours (top 50) and daily peak hour
- ENERGY-U3 temperature sensitivity (kWh per °C) by heating type
- ENERGY-U4 heating-type classifier trained on protected data, tested on original
- ENERGY-U5 load-profile clusters (shape agreement)
- ENERGY-U6 day-ahead forecast of mean load per meter
- ENERGY-U7 winter consumption by late-payment group (energy poverty)

## Things to watch
Identifiers that encode attributes, sensitive information in operational flags and free text, and the fact that an hourly
load curve is itself a behavioural fingerprint (who is home, when, and what they run). Rare equipment combinations in small
postcodes. Meter faults are real-world messiness, not personal data.
