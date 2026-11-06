# Mobility — Aura Transit boardings and city-bike trips (synthetic)

Fictional operator **Aura Transit** serving Turku, Kaarina, Raisio, Naantali, Lieto and Rusko. Period **6 Oct – 2 Nov 2025**
(4 weeks, including the autumn school break in week 42). All riders, cards and trips are synthetic; stops are synthetic
placements on real postcode geography.

| Table | Rows | What it is |
|---|---|---|
| `stops.csv` | 602 | Stops with Finnish/Swedish names, coordinates, district/area, lines |
| `cards.csv` | 22,619 | Travel-card registry; ~65 % personalised (holder name, birth date, email, phone) |
| `taps.csv` | 942,781 | Boardings (tap-on only, no tap-off), card id, stop, line, vehicle, fare |
| `bike_trips.csv` | 57,831 | City-bike trips with GPS start/end (season ends 31 Oct) |
| `bike_stations.csv` | 75 | Virtual bike parking zones |

**Patterns you can rely on:** morning (07–09) and afternoon (15–17) weekday peaks, transfers at the Kauppatori hub,
shift workers boarding around 05:20/13:20/21:20, Friday/Saturday night lines N1–N4, fewer school trips in week 42,
fewer bike trips on rainy and colder days.

**Destinations are not recorded.** Infer them by trip chaining: the next boarding of the same card is usually near the
previous trip's destination; the last trip of the day returns to the first boarding stop.

## Sharing scenarios
- **MOB-S1** open-data OD matrices (public) · **MOB-S2** planning consultancy, row-level under contract · **MOB-S3** academic research

## Utility tasks (pets_eval)
MOB-U1 OD matrix area×area×hour band · MOB-U2 ridership line×hour · MOB-U3 daily boardings time series ·
MOB-U4 bike trip duration distribution · MOB-U5 home→work area commuting flows · MOB-U6 bike zone demand ·
MOB-U7 bike distance distribution · MOB-U8 card-type mix.
`taps` utility tasks also accept an aggregate table named `od_matrix` with columns
`origin_area, destination_area, hour_band, trips` if you publish aggregates instead of rows.

## Things to watch
- A card id is a persistent pseudonym: the full 4-week trajectory behind it is the real risk.
  De Montjoye et al. (2013) showed that 4 spatio-temporal points single out ~95 % of people in mobile-phone data.
  Measure it here: for each card, sample k of its (stop, hour) points and count how many cards match all k
  (`pets_eval` has a unicity helper; try k = 2, 3, 4 before and after your transformation).
- Look closely at who the contact details in `cards` belong to, at the fare categories, and at the bike GPS start points.
- Some people have more than one card.
