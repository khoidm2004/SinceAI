# Smart city — city-centre Wi-Fi sensors, footfall and car parks (synthetic)

Fictional operator **Southwest Joint Service Centre**. Twenty Wi-Fi sensors in central Turku and six car parks with
number-plate cameras. Period **17–30 Nov 2025**: Black Friday on 28 Nov, Christmas market opening on the Old Great
Square on Sat 29 Nov. All devices, plates and people are synthetic; sensor locations are approximate real places.

| Table | Rows | What it is |
|---|---|---|
| `sensors.csv` | 20 | Sensor id, location, zone, coordinates |
| `wifi_probes.csv` | 585,525 | One row per Wi-Fi probe request heard: time, MAC, signal, probed network name |
| `footfall_15min.csv` | 26,880 | Distinct devices per sensor per 15 minutes (the operator's published metric); -1 = outage |
| `anpr_parking.csv` | 48,676 | Car-park entry/exit by plate, fee, payment method, masked card, app phone |

**Patterns:** weekday commuter arrivals 07–08, lunch walks around 11:30, shopping peaks in the afternoon and on
Saturdays, a Black Friday surge in the shopping zone, a crowd at WS15 (Old Great Square) on 29 Nov, a sensor outage
on WS07 (20 Nov 09–12). Most phones randomise their MAC address; a minority do not.

## Sharing scenarios
- **CITY-S1** open-data footfall · **CITY-S2** retail association (contract) · **CITY-S3** a police/enforcement request (purpose limitation)

## Utility tasks (pets_eval)
CITY-U1 footfall by zone × hour × day type · CITY-U2 dwell-time distribution · CITY-U3 car-park occupancy curve ·
CITY-U4 repeat-visitor (plate) share · CITY-U5 Black Friday uplift · CITY-U6 parking-duration distribution.

## Things to watch
- Which MACs are randomised and which are not, and what the network names in directed probes reveal.
- Small night-time counts in the aggregates.
- Every column of the parking table that can be linked to a person or another dataset.
