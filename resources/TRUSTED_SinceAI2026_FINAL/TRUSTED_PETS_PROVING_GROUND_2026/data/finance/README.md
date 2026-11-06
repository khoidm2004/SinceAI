# Finance — retail banking (synthetic)

**Controller (fictional):** Saaristo Bank, a regional bank in Southwest Finland. **Period:** 1 Jul – 31 Dec 2025.
All customers, cards, merchants and payments are synthetic. Card numbers use public test BINs; IBANs use a bank code not used in Finland.

## Tables
| table | rows | what it is |
|---|---|---|
| customers.csv | 6,315 | KYC record: identity, contact, income band, occupation, employer, PEP flag, risk rating |
| cards.csv | 6,969 | payment cards per customer (debit/credit; cards reissued after fraud) |
| card_transactions.csv | 398,408 | card authorisations: time, amount, merchant, MCC, location, channel, device/IP, fraud label |
| transfers.csv | 86,590 | account transfers: salaries, pensions, rent, loans, e-invoices, memberships, person-to-person with free-text messages |

Joins: `card_transactions.card_pan` → `cards.card_pan` → `cards.customer_id` → `customers.customer_id`;
`transfers.from_iban`/`to_iban` ↔ `customers.iban`.

## What is inside
Spending follows category preferences, local merchants, hour/weekday profiles, paydays (15th or last banking day; pensions
on the first banking day), July holidays, Black Friday (28 Nov 2025) and Christmas. About 14 % of customers travel abroad.
Fraud: card testing + cash-out, account takeover, skimming abroad (impossible travel) and lost/stolen contactless.
Labels are realistic: some fraud was never reported. Transfers include two money-laundering patterns that are **not** labelled.

## Sharing scenarios
- **FIN-S1 — Cross-bank fraud consortium.** Fraud data-sharing consortium of several banks. Utility: FIN-U1, FIN-U5.
- **FIN-S2 — External AI vendor builds a fraud / spending model.** AI vendor (processor). Utility: FIN-U1, FIN-U4, FIN-U6.
- **FIN-S3 — Statistics office: consumer spending statistics.** National statistics office / public release. Utility: FIN-U2, FIN-U3, FIN-U6.

## Utility tasks (pets_eval.utility.finance)
- FIN-U1 fraud model trained on protected Jul–Oct, tested on original Nov–Dec (PR-AUC relative to an original-data model)
- FIN-U2 spend by MCC group × merchant city × month
- FIN-U3 payday effect (spend by day of month)
- FIN-U4 customer (card) segmentation agreement
- FIN-U5 AML rule hits (structuring, rapid pass-through)
- FIN-U6 monthly spend by income band × age band

## Things to watch
Card numbers, IBANs and reference numbers are structured identifiers with check digits. Merchants and payees reveal
special categories of data (health, religion, politics, trade-union membership). Free-text messages carry names and IDs
of third parties, including children. Some columns mix persons and organisations.
