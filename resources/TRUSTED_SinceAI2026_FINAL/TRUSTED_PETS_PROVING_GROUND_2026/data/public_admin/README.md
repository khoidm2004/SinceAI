# Public administration — citizen service requests and building permits (synthetic)

Service requests to the fictional Southwest Joint Service Centre (Turku, Kaarina, Raisio, Naantali, Lieto), 2024-2025, and building permit decisions. Weather is synthetic: snowfall drives snow-removal requests.

## Tables

| table | rows | content |
|---|---|---|
| service_requests | 31,653 | request, free-text description, reporter contact, location, handler, status, reply |
| building_permits | 2,731 | applicant, property id, address, project, cost, decision |

Ground truth: `metadata/field_catalog.csv`, `metadata/pii_spans/public_admin__service_requests__description.jsonl` and `__response_text.jsonl`, `truth/public_admin__*.csv`.

## Sharing scenarios

- **PUB-S1 Open data publication of citizen feedback** — Publish requests with category, time, area, status and the text so residents and journalists can follow service quality. Utility tasks: PUB-U1, PUB-U2, PUB-U3, PUB-U4.
- **PUB-S2 Internal analytics team** — Dashboards on workload, response times and repeat issues. Utility tasks: PUB-U1, PUB-U2, PUB-U5, PUB-U6.
- **PUB-S3 Research group studying service equity** — Do response times differ between areas and languages? Utility tasks: PUB-U1, PUB-U2, PUB-U3.

## Utility tasks (pets_eval.utility.public_admin)

- PUB-U1 requests by area (3-digit postcode) × category × month
- PUB-U2 median resolution time by category
- PUB-U3 hotspot agreement: top-50 1 km grid cells
- PUB-U4 category classifier trained on protected text, tested on original text
- PUB-U5 share of requests from repeat reporters (needs a stable reporter key)
- PUB-U6 permits by municipality × project type × quarter

## Attacker knowledge

- `adversary/neighbourhood_forum_posts.csv` (1,400 posts): residents talking about requests they made.
- The building permit table itself is public information in Finland.
- An insider-knowledge attacker is held by the organisers.

## Things to watch

- The reporter is not the only person in a request.
- The city's reply leaks as much as the request.
- Two public tables can be joined.
- Some people are very active.
