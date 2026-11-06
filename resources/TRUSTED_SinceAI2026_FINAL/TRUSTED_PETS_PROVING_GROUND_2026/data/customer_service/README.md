# Customer service — Aallokko Telecom Oy (fictional) contact centre, 2025

Chats, phone-call transcripts (speech-recognition output) and e-mail threads between customers and agents of a
fictional Finnish telecom that also sells electricity. Languages: Finnish, English, Swedish. Every person,
number and address is synthetic.

## Tables
| file | rows | what |
|---|---|---|
| customers.csv | 9,591 | customer master extract: name, ID code, contact details, products, payment flags |
| conversations.csv | 11,943 | one row per contact: channel, language, intent, sentiment, CSAT, handle time, agent, **agent_note** (free text) |
| turns.csv | 140,345 | utterances; **text** is free text |

`conversations.split`: `train` (8,981 conversations) has public PII span labels in
`metadata/pii_spans/customer_service__turns__text.jsonl` and `..._conversations__agent_note.jsonl`.
`eval` (2,962) has the same kind of text but its labels are held by the organisers:
it measures how well your redaction generalises.

## Span labels (train + eval, all text fields)
| label | spans |
|---|---|
| PERSON | 38,401 |
| ACCOUNT_NUMBER | 11,600 |
| NATIONAL_ID | 10,031 |
| PHONE | 6,143 |
| DATE | 3,995 |
| ADDRESS | 3,173 |
| EMAIL | 2,698 |
| IBAN | 1,977 |
| ORG | 1,787 |
| LOCATION | 1,698 |
| HEALTH | 1,207 |
| PAYMENT_CARD | 1,143 |
| DEVICE_ID | 764 |
| AGE | 695 |
| SECRET | 621 |
| URL | 578 |
| IP_ADDRESS | 462 |
| PROPERTY_ID | 140 |
| USERNAME | 81 |
| LICENSE_PLATE | 39 |

Guidelines: `metadata/pii_span_guidelines.md`.

## Sharing scenarios
- **CS-S1** transcripts to an external LLM analytics vendor
- **CS-S2** train an internal intent model / chatbot
- **CS-S3** quality-audit samples to an outsourced BPO

## Utility tasks (pets_eval.utility.customer_service)
CS-U1 intent classifier trained on protected train, tested on original eval · CS-U2 sentiment–CSAT relationship ·
CS-U3 intent mix · CS-U4 handle time by intent · CS-U5 ordinary vocabulary retained · CS-U6 channel × language volumes ·
CS-U7 resolution rate by intent.

## Watch out for
Spoken numbers, identifiers split over two turns, spelled-out e-mails, secrets, health remarks inside billing
calls, relatives' details, agent names, and the agent notes. Not every number is personal (router 192.168.1.1, prices).
