# Cyber: Meridian Logistics Oy security logs (synthetic)

Two weeks (2–15 March 2026) of telemetry from the security operations centre of **Meridian Logistics Oy**, a fictional
logistics company in Turku with ~1,100 staff in offices and warehouses. Every person, address, IP address and domain is synthetic.
Columns ending `_utc` are UTC; Finland is UTC+2 in this period. Domains end in `.example`; public IPs come from
documentation and shared ranges, mapped to countries by the synthetic `geoip_ranges.csv`.

| table | rows |
|---|---|
| `signin_logs.csv` | 41,252 |
| `vpn_logs.csv` | 3,804 |
| `email_gateway.csv` | 30,254 |
| `proxy_logs.csv` | 137,024 |
| `dns_logs.csv` | 75,606 |
| `edr_alerts.csv` | 448 |
| `incident_tickets.csv` | 315 |
| `identity.csv` | 994 |
| `geoip_ranges.csv` | 16 |

`identity` is the directory export. The log tables join on `upn`, internal IPs (`src_ip`, `assigned_ip`, `client_ip`,
`device_ip`) and host names. `incident_tickets.description` is free text with exact PII spans in
`metadata/pii_spans/cyber__incident_tickets__description.jsonl`.

## Labelled attacks (ground truth for self-assessment)
Columns `attack_label` (MITRE ATT&CK technique ids) and `campaign_id`:
- **C1** phishing link → credential theft → impossible travel and MFA fatigue → VPN → lateral movement → password-protected archive → upload to cloud storage.
- **C2** password spray from hosting IPs.
- **C3** an employee who resigned downloads customer files and sends them out.
Benign look-alikes are included on purpose: business travel from hotel networks, a large daytime upload to the same cloud
storage, IT admins running PowerShell, service accounts.

## Why this is hard
Detections need joins across logs. If the same user becomes different tokens in different tables, or internal IPs are
replaced by random values, the attack chain disappears. If the protection is too weak, user names leak through UPNs,
host names, URLs, file paths, e-mail subjects and ticket text.

## Sharing scenarios
CYBER-S1 external MSSP · CYBER-S2 indicator sharing with the national CERT · CYBER-S3 public research dataset
(details in `metadata/scenarios.json`). Utility tasks CYBER-U1…U11 are in `pets_eval/utility/cyber.py`; the reference
detection rules there can be run on your protected logs.

## Attacker knowledge
`adversary/company_website_staff.csv` lists staff visible on the company website and a professional network (names,
titles, departments, sites; some entries are stale). Evaluation also uses a stronger private OSINT/breach file.

## Holdout
`holdout/cyber/` holds identity and sign-in rows of employees removed from the data (non-members) for
membership-inference tests on synthetic logs.
