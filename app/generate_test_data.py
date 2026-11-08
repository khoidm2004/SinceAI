#!/usr/bin/env python3
"""Deterministic synthetic Health + Finance test pack for Mosaic (standard library only).

One shared fictional population is generated first; Health (ED visits, lab results, clinical
notes) and Finance (customers, cards, card transactions) records are then derived from it, so
cross-domain linkage exists only through the generator's own relationships. The output is a
custom "pack root" laid out like the official TrustED pack (data/, metadata/, adversary/, truth/,
holdout/) so that Mosaic modules and the official pets-eval toolkit resolve it with --root.

Schemas, roles, scenarios and attack specs are copied from the official metadata (copied, never
edited). Identifier conventions follow the pack's NOTICE.md: HETU individual numbers 900-999 with a
valid check character, checksum-valid IBANs with a bank id starting with 9, payment cards on the
public test BINs with a valid Luhn digit, e-mail on reserved .example domains, Finnish-format
mobile numbers generated at random. No real person, record or public dataset is used.

The manifest is computed by re-reading the written files (observed values), not from the targets.
"""
from __future__ import annotations

from python_version import require_python

require_python()
import argparse
import bisect
import csv
import json
import math
import random
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalize_hetu, normalize_phone  # noqa: E402
from synth_common import (  # noqa: E402
    DEFAULT_GENERATED_ROOT, OFFICIAL_PACK, peak_memory_bytes, read_csv, read_header, refuse_forbidden,
    sha256_file, sha256_text, utf8_stdout, write_csv, write_json,
)

GENERATOR_VERSION = "mosaic-synth-health-finance/1.0.0"
REF_DATE = date(2025, 12, 31)  # pets-eval age reference (attacks.py REF, parse.py)
HEALTH_YEAR = 2025
FIN_START, FIN_END = datetime(2025, 7, 1), datetime(2025, 12, 31, 23, 59, 59)

PROFILES: Dict[str, Dict[str, Any]] = {
    # smoke: schema/determinism/integration only - too small for meaningful privacy or utility numbers
    "smoke": {"people": 400, "tx_per_card": 12, "holdout_share": 0.05, "fraud_card_share": 0.012},
    # demo: 2,500 people (team decision: 10k was too heavy). Volumes sized for the pets-eval task minimums:
    # H-U7 >=30 joined CRP rows (per diagnosis group for the group term), FIN-U1 >=10 labelled frauds in
    # Jul-Oct and positives in Nov-Dec, FIN-U4 >=50 cards, FIN-U6 >=10 customers per income x age cell.
    # The fraud-card share is raised from the official ~1.1% to 2.5% so FIN-U1 keeps enough positives at
    # this smaller size; it is recorded in the manifest config.
    "demo": {"people": 2500, "tx_per_card": 28, "holdout_share": 0.04, "fraud_card_share": 0.025},
    "bench": {"people": 2500, "tx_per_card": 28, "holdout_share": 0.04, "fraud_card_share": 0.025},
}


@dataclass
class Config:
    people: int = 2500
    seed: int = 20261107
    share_both: float = 0.20          # people in Health AND Finance
    share_health_only: float = 0.40
    share_finance_only: float = 0.15  # remainder: in neither domain (only in public adversary data)
    finance_phone_same: float = 0.88  # shared person keeps the same mobile number in both domains
    health_phone_missing: float = 0.25
    finance_phone_missing: float = 0.035
    health_hetu_missing: float = 0.01  # identified patient registered without HETU
    nonresident_visit_share: float = 0.017
    tx_per_card: float = 28.0
    fraud_card_share: float = 0.012
    holdout_share: float = 0.04
    profile: str = "demo"


# --------------------------------------------------------------------------- reference values
# Geography only (real municipality / postcode names of Southwest Finland, as in the official pack).
MUNICIPALITIES: List[Tuple[str, int, List[str]]] = [
    ("Turku", 18313, "20100 20200 20210 20240 20250 20300 20320 20360 20380 20400 20460 20500 20520 20540 20610 20700 20720 20730 20740 20750 20800 20810 20880 20900 20960 21330 21340".split()),
    ("Salo", 4916, "24100 24130 24240 24260 24280 24800 24910 25110 25170 25250 25330 25360 25390 25410 25460 25500 25560 25610 25640 25660".split()),
    ("Kaarina", 3149, "20660 20760 20780 21500 21620".split()),
    ("Raisio", 2481, "21120 21200 21210 21220 21260 21280".split()),
    ("Lieto", 1986, "21350 21360 21410 21420 21430 21450".split()),
    ("Naantali", 1880, "21100 21110 21130 21140 21150 21160 21180 21195".split()),
    ("Uusikaupunki", 1478, "23450 23500 23600 23660 23930".split()),
    ("Loimaa", 1413, "31960 32200 32210 32250 32260 32270 32280 32300 32410 32430 32440 32450 32560".split()),
    ("Parainen", 1399, "21600 21610 21630 21650 21660 21670 21680 21710 21720 21740 21750 21760 21770 23390".split()),
    ("Paimio", 961, "21510 21520 21530 21540 21555".split()),
    ("Masku", 930, "21230 21240 21250".split()),
    ("Mynämäki", 812, "23100 23120 23140".split()),
    ("Pöytyä", 780, "21800 21820 21840 21860 21870 21880 21890 21900 21930".split()),
    ("Somero", 766, "31400 31410 31450 31460 31470 31490 31520 31530".split()),
    ("Laitila", 758, "23800 23840 23880".split()),
    ("Kemiönsaari", 581, "25650 25700 25710 25730 25760 25810 25820 25830 25840 25860 25870 25900 25910 25930 25940".split()),
    ("Rusko", 531, "21290 21310".split()),
    ("Nousiainen", 455, ["21270"]),
    ("Aura", 352, "21370 21380".split()),
    ("Sauvo", 300, "21570 21590".split()),
    ("Koski Tl", 245, ["31500"]),
    ("Marttila", 210, "21480 21490 21560".split()),
    ("Vehmaa", 199, "23200 23210 23260".split()),
    ("Pyhäranta", 198, "23950 23960 27320 27340".split()),
    ("Taivassalo", 171, ["23310"]),
    ("Oripää", 124, "32500 32520".split()),
    ("Kustavi", 89, ["23360"]),
]
AMBULANCE_BASE = {"Turku": "TKU", "Salo": "SLO", "Kaarina": "KAA", "Raisio": "RSO", "Lieto": "LIE", "Uusikaupunki": "UKI",
                  "Loimaa": "LMA", "Naantali": "NAA", "Parainen": "PAR", "Masku": "MAS", "Paimio": "PAI", "Mynämäki": "MYN",
                  "Laitila": "LAI", "Somero": "SOM", "Kemiönsaari": "KEM", "Pöytyä": "PÖY"}
# Approximate centroids (for POS terminals only); generated jitter, not real addresses.
MUNI_CENTROID = {"Turku": (60.45, 22.27), "Salo": (60.38, 23.13), "Kaarina": (60.41, 22.37), "Raisio": (60.49, 22.17),
                 "Lieto": (60.50, 22.45), "Naantali": (60.47, 22.03), "Uusikaupunki": (60.80, 21.41), "Loimaa": (60.85, 23.06),
                 "Parainen": (60.30, 22.30), "Paimio": (60.46, 22.69)}

# ICD-10 primary codes = the 50 keys of pets_eval utility/health.py DIAGNOSIS_GROUPS, official frequencies.
ICD_PRIMARY: List[Tuple[str, int]] = [
    ("R07.4", 3781), ("R10.4", 3066), ("N39.0", 2727), ("J10.1", 2319), ("A08.4", 2112), ("S52.5", 1993), ("F10.0", 1895),
    ("J18.9", 1894), ("S06.0", 1473), ("R51", 1471), ("S93.4", 1465), ("R55", 1392), ("J06.9", 1335), ("Z03.9", 1298),
    ("I48.9", 1293), ("M54.5", 1250), ("U07.1", 1146), ("S61.0", 1132), ("N20.0", 1048), ("S01.8", 1023), ("F41.0", 846),
    ("R50.9", 788), ("H66.9", 756), ("J45.9", 755), ("J21.0", 741), ("K80.2", 687), ("G40.9", 578), ("I63.9", 566),
    ("J44.1", 512), ("L03.1", 456), ("K35.8", 427), ("S82.6", 395), ("I50.9", 387), ("I21.4", 351), ("T63.4", 349),
    ("F32.9", 347), ("S42.0", 312), ("G45.9", 284), ("T78.2", 276), ("T23.2", 240), ("I26.9", 224), ("S72.0", 194),
    ("S05.1", 119), ("E87.1", 115), ("F05.9", 115), ("O20.0", 97), ("A41.9", 89), ("E10.1", 82), ("F20.0", 49), ("O21.0", 34),
]
ICD_SECONDARY = [("I10", 7335), ("J45.9", 2874), ("E11.9", 2443), ("F33.9", 1800), ("I48.9", 1043), ("J44.9", 759),
                 ("K90.0", 674), ("I50.9", 472), ("S00.8", 356), ("N18.4", 312), ("G30.9", 281), ("E10.9", 224)]
INFECTIOUS = {"J10.1", "J18.9", "J06.9", "A08.4", "U07.1", "R50.9", "J21.0", "A41.9", "N39.0", "L03.1", "K35.8", "H66.9", "J44.1"}
CHEST = {"R07.4", "I21.4", "I48.9", "I50.9", "I26.9", "I63.9"}
ABDOMINAL = {"R10.4", "K80.2", "K35.8", "N20.0", "A08.4"}
INJURY = {"S52.5", "S06.0", "S93.4", "S61.0", "S01.8", "S82.6", "S42.0", "S72.0", "S05.1", "T23.2", "T63.4", "T78.2"}
TRIAGE_W = {"A": 705, "B": 4977, "C": 15958, "D": 17333, "E": 7425}
DISPO_BY_TRIAGE = {  # official triage x disposition counts (cancelled_duplicate handled separately)
    "A": {"admitted_ward": 357, "died": 17, "home": 183, "icu": 80, "transfer": 65},
    "B": {"admitted_ward": 2106, "died": 2, "home": 2437, "icu": 116, "transfer": 306},
    "C": {"admitted_ward": 3972, "home": 11340, "icu": 191, "transfer": 416},
    "D": {"admitted_ward": 1805, "home": 14790, "icu": 114, "left_without_being_seen": 396, "transfer": 188},
    "E": {"admitted_ward": 612, "home": 6492, "icu": 38, "left_without_being_seen": 197, "transfer": 64},
}
LOS_MEDIAN = {"A": 302, "B": 348, "C": 314, "D": 221, "E": 157}
LOS_FACTOR = {"admitted_ward": 1.6, "transfer": 2.2, "icu": 0.8, "home": 0.95, "left_without_being_seen": 0.7, "died": 0.5}
HOUR_W_HEALTH = [1215, 961, 751, 611, 552, 510, 784, 1499, 2154, 2702, 2893, 2918, 2762, 2495, 2652, 2611, 2871, 2853, 2778, 2683, 2370, 1847, 1604, 1322]
MONTH_W_HEALTH = [4340, 4661, 3932, 3263, 3400, 3686, 3802, 3636, 3565, 3684, 3679, 4750]
VISITS_PER_PATIENT = [(1, 16070), (2, 5476), (3, 2199), (4, 1024), (5, 525), (6, 267), (7, 151), (8, 83), (9, 55), (10, 25)]

LAB_TESTS = {  # code: (name, unit, ref_range)
    "P-CRP": ("C-reactive protein", "mg/l", "<10"), "B-Hb": ("Haemoglobin", "g/l", None), "B-Leuk": ("Leukocytes", "E9/l", "3.4-8.2"),
    "P-K": ("Potassium", "mmol/l", "3.3-4.9"), "P-Na": ("Sodium", "mmol/l", "137-145"), "P-Krea": ("Creatinine", "µmol/l", None),
    "P-TnT": ("Troponin T (high-sensitivity)", "ng/l", "<15"), "P-Amyl": ("Pancreatic amylase", "U/l", "<65"),
    "InfAB-NhO": ("Influenza A/B PCR", "", "NEG"), "SARSCoV2-NhO": ("SARS-CoV-2 PCR", "", "NEG"),
    "fP-Gluk": ("Glucose", "mmol/l", "4.0-6.0"), "P-Etanol": ("Ethanol", "‰", "0"), "P-proBNP": ("NT-proBNP", "ng/l", "<450"),
    "fP-D-Dimer": ("D-dimer", "mg/l", "<0.5"), "U-hCG": ("Urine hCG (pregnancy test)", "", "NEG"),
}

INCOME_BANDS = ["<15k", "15-30k", "30-45k", "45-60k", "60-90k", "90k+"]
INCOME_BY_OCC = {
    "Retired": [8, 60, 22, 7, 3, 0], "Student": [80, 18, 2, 0, 0, 0], "Unemployed": [55, 40, 5, 0, 0, 0],
    "On parental leave": [25, 50, 20, 5, 0, 0], "Professional": [0, 5, 15, 25, 45, 10], "Manager": [0, 0, 5, 15, 30, 50],
    "Technician / associate professional": [0, 10, 35, 35, 18, 2], "Service and sales worker": [5, 50, 35, 8, 2, 0],
    "Craft worker": [0, 25, 45, 25, 5, 0], "Machine operator": [0, 25, 50, 20, 5, 0], "Clerical worker": [0, 30, 50, 15, 5, 0],
    "Elementary occupation": [10, 60, 25, 5, 0, 0],
}
NO_EMPLOYER = {"Retired", "Student", "Unemployed", "On parental leave"}
EMAIL_DOMAINS = ["inbox", "nordmail", "webmail", "kotiposti", "nettiposti", "mailbox", "postilaatikko", "aurapost"]
TEST_BINS = ["411111", "400000", "424242", "555555", "510510", "222300"]  # public test BINs (NOTICE.md)
MCC_W = [("5411", 123061), ("5814", 36450), ("5812", 25342), ("5499", 22036), ("5813", 20829), ("4111", 18182), ("5999", 17911),
         ("5651", 13133), ("5968", 12637), ("5541", 11787), ("5311", 11382), ("5912", 11240), ("6011", 11178), ("5921", 9110),
         ("5251", 8177), ("8011", 5512), ("5732", 5511), ("7997", 5346), ("4121", 4576), ("5816", 4278), ("4814", 3529),
         ("7832", 2768), ("5942", 2652), ("7011", 2329), ("7995", 2037), ("5995", 2030), ("4511", 1984), ("8021", 1752), ("7538", 1228)]
MCC_MEDIAN = {"4111": 3.1, "5499": 6.96, "5411": 23.85, "6011": 50.0, "4511": 155.9, "7011": 147.0, "5814": 9.5, "5812": 28.0,
              "5813": 18.0, "5541": 45.0, "5999": 19.0, "5732": 89.0, "5251": 32.0, "7997": 35.0, "4121": 21.0, "5816": 9.9,
              "4814": 25.0, "5968": 22.0, "7995": 15.0, "8011": 60.0, "8021": 75.0, "7832": 14.0, "5942": 21.0, "5995": 18.0,
              "5651": 39.0, "5311": 27.0, "5912": 17.0, "5921": 24.0, "7538": 120.0}
ECOM_ONLY = {"4814", "5816", "5968", "7995"}
FOREIGN = [("SE", "Stockholm", "SEK", 11.6, (59.33, 18.06)), ("DE", "Berlin", "EUR", 1.0, (52.52, 13.40)),
           ("NL", "Amsterdam", "EUR", 1.0, (52.37, 4.90)), ("IE", "Dublin", "EUR", 1.0, (53.35, -6.26)),
           ("EE", "Tallinn", "EUR", 1.0, (59.44, 24.75)), ("ES", "Málaga", "EUR", 1.0, (36.72, -4.42)),
           ("MT", "Sliema", "EUR", 1.0, (35.91, 14.50)), ("US", "New York", "USD", 1.08, (40.71, -74.01)),
           ("GB", "London", "GBP", 0.85, (51.51, -0.13))]
FRAUD_TYPES = [("card_testing", 0.5), ("skimming", 0.19), ("lost_stolen", 0.13), ("cnp_cashout", 0.11), ("account_takeover", 0.07)]

# Fictional name material (syllable-composed surnames; given names are common forenames, not people).
GIVEN_M = "Aleksi Antti Eero Elias Ilmari Jaakko Janne Joel Juho Kalle Lauri Leo Matias Mikko Niko Oskari Otto Pekka Sami Tapio Tuomas Valtteri Veikko Ville".split()
GIVEN_F = "Aino Anna Eeva Elina Emilia Helmi Ilona Iida Johanna Kaisa Laura Linnea Maria Minna Noora Oona Pia Riikka Sanna Satu Sofia Tiina Venla Viivi".split()
SUR_A = "Aho Haka Hirvi Ilo Jär Kalli Karhu Kivi Koski Kuusi Lahti Lehti Leppä Linna Mäki Niemi Nurmi Ojala Paju Rauta Salmi Sarja Suo Talvi Tuuli Vaara Valko Vuori".split()
SUR_B = "nen la lä mo nen vaara mäki koski salo niemi lahti ranta".split()
STREET_A = "Aalto Haapa Kanerva Kataja Kotka Lehmus Lumme Mansikka Pihlaja Puolukka Ruusu Saarni Tammi Tuomi Vaahtera Vesi".split()
STREET_B = "katu tie kuja polku rinne".split()
FOREIGN_CITIES = ["Stockholm", "Tallinn", "Berlin", "Riga", "Oslo"]
OCCUPATIONS = list(INCOME_BY_OCC)


# --------------------------------------------------------------------------- small helpers
def wchoice(rng: random.Random, items: Sequence[Tuple[Any, float]]) -> Any:
    vals, ws = zip(*items)
    return rng.choices(vals, weights=ws, k=1)[0]


class Weighted:
    """Fast repeated weighted choice (cumulative weights + bisect)."""

    def __init__(self, items: Sequence[Tuple[Any, float]]):
        self.vals = [v for v, _ in items]
        self.cum, s = [], 0.0
        for _, w in items:
            s += w
            self.cum.append(s)

    def __call__(self, rng: random.Random) -> Any:
        return self.vals[bisect.bisect_right(self.cum, rng.random() * self.cum[-1])]


def hetu_check(ddmmyy: str, nnn: str) -> str:
    return "0123456789ABCDEFHJKLMNPRSTUVWXY"[int(ddmmyy + nnn) % 31]


def make_hetu(bd: date, sex: str, nnn: int) -> str:
    ddmmyy = bd.strftime("%d%m%y")
    sign = "-" if bd.year < 2000 else "A"
    return f"{ddmmyy}{sign}{nnn:03d}{hetu_check(ddmmyy, f'{nnn:03d}')}"


def luhn_digit(body: str) -> str:
    total = 0
    for i, ch in enumerate(reversed(body)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def luhn_ok(s: str) -> bool:
    return luhn_digit(s[:-1]) == s[-1]


def make_iban(bban14: str) -> str:
    check = 98 - int(bban14 + "151800") % 97  # "FI00" -> F=15, I=18
    return f"FI{check:02d}{bban14}"


def iban_ok(s: str) -> bool:
    s = s.replace(" ", "")
    return int("".join(str(int(c, 36)) for c in s[4:] + s[:4])) % 97 == 1


def hetu_ok(s: str) -> bool:
    return len(s) == 11 and s[6] in "-+ABCDEFUVWXY" and 900 <= int(s[7:10]) <= 999 and hetu_check(s[:6], s[7:10]) == s[10]


def phone_formats(n: str) -> List[str]:
    """Finnish formats seen in the official health data for one 10-digit national number 0XXYYYYYYY."""
    return ["+358" + n[1:], n, f"{n[:3]} {n[3:6]} {n[6:]}", f"{n[:3]}-{n[3:]}", f"{n[:3]} {n[3:7]} {n[7:]}",
            f"+358 {n[1:3]} {n[3:6]} {n[6:]}", "00358" + n[1:]]


def fmt_amount(x: float) -> str:
    s = f"{x:.2f}"
    if s.endswith("00"):
        s = s[:-3] + ".01"  # official amounts are never integers
    return s.rstrip("0")


def ts_health(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:00")


def ts_fin(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def age_at(bd: date, at: date) -> int:
    return at.year - bd.year - ((at.month, at.day) < (bd.month, bd.day))


class IdPool:
    """Unique random ids from a numeric space, shared by main and holdout tables."""

    def __init__(self, rng: random.Random, prefix: str, digits: int, lo: int = 1):
        self.rng, self.prefix, self.digits, self.lo, self.used = rng, prefix, digits, lo, set()

    def new(self) -> str:
        hi = 10 ** self.digits - 1
        while True:
            v = self.rng.randint(self.lo, hi)
            if v not in self.used:
                self.used.add(v)
                return f"{self.prefix}{v:0{self.digits}d}"


class SpanText:
    """Build free text piecewise while recording exact [start, end) PII spans."""

    def __init__(self):
        self.parts: List[str] = []
        self.spans: List[Dict[str, Any]] = []
        self.n = 0

    def add(self, s: str) -> "SpanText":
        self.parts.append(s)
        self.n += len(s)
        return self

    def pii(self, s: str, label: str) -> "SpanText":
        self.spans.append({"end": self.n + len(s), "label": label, "start": self.n, "text": s})
        return self.add(s)

    def text(self) -> str:
        return "".join(self.parts)


def validate_spans(text: str, spans: List[Dict[str, Any]]) -> List[str]:
    errs, last_end = [], -1
    for sp in sorted(spans, key=lambda s: s["start"]):
        if not (0 <= sp["start"] < sp["end"] <= len(text)):
            errs.append(f"offset out of range {sp['start']}-{sp['end']}")
        elif text[sp["start"]:sp["end"]] != sp["text"]:
            errs.append("span text does not match offsets")
        if sp["start"] < last_end:
            errs.append("overlapping spans")
        last_end = max(last_end, sp["end"])
    return errs


# --------------------------------------------------------------------------- population
@dataclass
class Person:
    pid: str
    sex: str
    birth: date
    hetu: str
    given: List[str]
    surname: str
    municipality: str
    postcode: str
    street: str
    phone: str                       # canonical national 10-digit mobile number
    membership: str                  # both / health / finance / none / holdout_health / holdout_finance
    finance_phone: str = ""
    health_has_phone: bool = True
    health_has_hetu: bool = True
    language: str = "fi"
    occupation: str = ""
    income: str = ""
    employer: str = ""
    email: str = ""
    iban: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def calling(self) -> str:
        return f"{self.given[0]} {self.surname}"


class Generator:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.s = cfg.seed
        self.used_hetu: set = set()
        self.used_phone: set = set()
        self.used_iban: set = set()
        self.used_pan: set = set()
        self.muni_pick = Weighted([(m, w) for m, w, _ in MUNICIPALITIES])
        self.post_by_muni = {m: pcs for m, _, pcs in MUNICIPALITIES}
        self.employers = [self._org(random.Random(f"{self.s}:emp:{i}")) for i in range(max(40, cfg.people // 25))]

    def rng(self, stage: str) -> random.Random:
        return random.Random(f"{self.s}:{stage}")

    # -- identity building blocks
    def _surname(self, r: random.Random) -> str:
        return r.choice(SUR_A) + r.choice(SUR_B)

    def _org(self, r: random.Random) -> str:
        return f"{r.choice(SUR_A)}{r.choice(['tek', 'pro', 'line', 'data', 'logi', 'met'])} {r.choice(['Oy', 'Oy', 'Oy', 'Ab', 'Ky', 'Tmi'])}"

    def _street(self, r: random.Random) -> str:
        base = f"{r.choice(STREET_A)}{r.choice(STREET_B)} {r.randint(1, 60)}"
        return base + (f" {r.choice('ABCD')} {r.randint(1, 30)}" if r.random() < 0.65 else "")

    def _unique_phone(self, r: random.Random) -> str:
        while True:
            n = "0" + r.choice(["40", "41", "44", "45", "46", "50"]) + f"{r.randint(0, 9999999):07d}"
            if n not in self.used_phone:
                self.used_phone.add(n)
                return n

    def _hetu(self, r: random.Random, bd: date, sex: str) -> str:
        for _ in range(200):
            nnn = r.randrange(901 if sex == "M" else 900, 1000, 2)  # odd = male
            h = make_hetu(bd, sex, nnn)
            if h not in self.used_hetu:
                self.used_hetu.add(h)
                return h
        raise RuntimeError("HETU space exhausted for a birth date")

    def _iban(self, r: random.Random) -> str:
        while True:
            iban = make_iban("9" + f"{r.randint(0, 99):02d}" + f"{r.randint(0, 10**11 - 1):011d}")
            if iban not in self.used_iban:
                self.used_iban.add(iban)
                return iban

    def _pan(self, r: random.Random) -> str:
        while True:
            body = r.choice(TEST_BINS) + f"{r.randint(0, 10**9 - 1):09d}"
            pan = body + luhn_digit(body)
            if pan not in self.used_pan:
                self.used_pan.add(pan)
                return pan

    def make_person(self, r: random.Random, pid: str, membership: str) -> Person:
        decade = wchoice(r, [(0, 10), (1, 10), (2, 12), (3, 12), (4, 12), (5, 12), (6, 13), (7, 12), (8, 6), (9, 1)])
        if membership in ("both", "finance", "holdout_finance"):
            decade = max(decade, 2) if r.random() < 0.9 else max(decade, 1)
        age_days = int((decade * 10 + r.random() * 10) * 365.25)
        bd = REF_DATE - timedelta(days=age_days)
        if membership in ("both", "finance", "holdout_finance") and age_at(bd, REF_DATE) < 18:
            bd = REF_DATE - timedelta(days=int((18 + r.random() * 40) * 365.25))
        sex = r.choice("MF")
        muni = self.muni_pick(r)
        p = Person(pid=pid, sex=sex, birth=bd, hetu=self._hetu(r, bd, sex),
                   given=r.sample(GIVEN_M if sex == "M" else GIVEN_F, 2 if r.random() < 0.75 else 1),
                   surname=self._surname(r), municipality=muni, postcode=r.choice(self.post_by_muni[muni]),
                   street=self._street(r), phone=self._unique_phone(r), membership=membership)
        p.language = "sv" if (muni in ("Parainen", "Kemiönsaari") and r.random() < 0.6) or r.random() < 0.03 else ("en" if r.random() < 0.045 else "fi")
        age = age_at(bd, REF_DATE)
        occ = ("Retired" if age >= 65 and r.random() < 0.9 else "Student" if age < 24 and r.random() < 0.7
               else wchoice(r, [(o, w) for o, w in zip(OCCUPATIONS, [2, 3, 6, 2, 10, 2, 9, 11, 5, 5, 4, 4])]))
        p.occupation = occ
        p.income = wchoice(r, list(zip(INCOME_BANDS, INCOME_BY_OCC[occ])))
        p.employer = "" if occ in NO_EMPLOYER else self.employers[min(int(r.paretovariate(1.2)) - 1, len(self.employers) - 1)]
        p.health_has_phone = r.random() >= self.cfg.health_phone_missing
        p.health_has_hetu = r.random() >= self.cfg.health_hetu_missing
        if membership in ("both", "finance", "holdout_finance"):
            p.finance_phone = "" if r.random() < self.cfg.finance_phone_missing else (
                p.phone if (membership == "both" and r.random() < self.cfg.finance_phone_same) else
                (self._unique_phone(r) if membership == "both" else p.phone))
            local = f"{p.given[0].lower()}.{p.surname.lower()}" if r.random() < 0.6 else f"{p.given[0].lower()}{r.randint(1, 999)}"
            local = local.replace("ä", "a").replace("ö", "o")
            p.email = "" if r.random() < 0.075 else f"{local}@{r.choice(EMAIL_DOMAINS)}.example"
            p.iban = self._iban(r)
        return p

    def population(self) -> Tuple[List[Person], List[Person]]:
        r = self.rng("population")
        c = self.cfg
        ids = list(range(1, int(c.people * (1 + c.holdout_share * 2)) + 2))
        r.shuffle(ids)
        people = []
        cuts = [c.share_both, c.share_both + c.share_health_only, c.share_both + c.share_health_only + c.share_finance_only]
        for i in range(c.people):
            u = r.random()
            m = "both" if u < cuts[0] else "health" if u < cuts[1] else "finance" if u < cuts[2] else "none"
            people.append(self.make_person(r, f"P{ids[i]:06d}", m))
        hold = []
        n_hold = max(10, int(c.people * c.holdout_share))
        for j in range(n_hold):
            m = "holdout_health" if j % 2 == 0 else "holdout_finance"
            hold.append(self.make_person(r, f"P{ids[c.people + j]:06d}", m))
        return people, hold

    # -- health
    def health(self, persons: List[Person], ids: Dict[str, IdPool], stage: str, nonresident: bool) -> Dict[str, Any]:
        r = self.rng(f"health:{stage}")
        icd = Weighted(ICD_PRIMARY)
        icd2 = Weighted(ICD_SECONDARY)
        hour = Weighted(list(enumerate(HOUR_W_HEALTH)))
        month = Weighted([(m + 1, w) for m, w in enumerate(MONTH_W_HEALTH)])
        nvis = Weighted(VISITS_PER_PATIENT)
        physicians = [(f"STAFF-{10000 + i * 37:05d}", f"{r.choice(GIVEN_M + GIVEN_F)} {self._surname(r)}") for i in range(max(12, len(persons) // 150))]
        nurses = [(f"STAFF-{30000 + i * 41:05d}", f"{r.choice(GIVEN_M + GIVEN_F)} {self._surname(r)}") for i in range(max(20, len(persons) // 80))]
        visits: List[Dict[str, Any]] = []
        patients = [p for p in persons]
        if nonresident:  # non-resident visitors: no HETU, no postcode, no person in truth
            n_nr = int(len(patients) * 1.75 * self.cfg.nonresident_visit_share)
            for k in range(n_nr):
                rr = random.Random(f"{self.s}:nr:{stage}:{k}")
                bd = REF_DATE - timedelta(days=int((20 + rr.random() * 50) * 365.25))
                sex = rr.choice("MF")
                patients.append(Person(pid="", sex=sex, birth=bd, hetu="", given=[rr.choice(GIVEN_M if sex == "M" else GIVEN_F)],
                                       surname=self._surname(rr), municipality="non-resident", postcode="",
                                       street=f"{rr.choice(STREET_A)}gatan {rr.randint(1, 80)}, {rr.choice(FOREIGN_CITIES)}",
                                       phone="", membership="nonresident", health_has_hetu=False,
                                       extra={"foreign_phone": f"+46 7{rr.randint(0, 9)} {rr.randint(100, 999)} {rr.randint(10, 99)} {rr.randint(10, 99)}" if rr.random() < 0.5 else ""}))
        for p in patients:
            k = 1 if p.membership == "nonresident" else nvis(r) if r.random() < 0.97 else r.randint(11, 16)
            arrivals = []
            for _ in range(k):
                m = month(r)
                d = date(HEALTH_YEAR, m, r.randint(1, 28 if m == 2 else 30 if m in (4, 6, 9, 11) else 31))
                if d <= p.birth:  # never before birth (infants born during 2025)
                    span = (date(HEALTH_YEAR, 12, 31) - p.birth).days
                    d = p.birth + timedelta(days=r.randint(1, max(1, span)))
                arrivals.append(datetime(d.year, d.month, d.day, hour(r), r.randint(0, 59)))
            arrivals.sort()
            for i in range(1, len(arrivals)):  # revisit clustering: some returns within 30 days
                if r.random() < 0.38:
                    cand = arrivals[i - 1] + timedelta(hours=r.uniform(8, 24 * 28))
                    if cand.year == HEALTH_YEAR and cand.date() > p.birth:
                        arrivals[i] = cand.replace(second=0, microsecond=0)
            arrivals.sort()
            fmt_pool = phone_formats(p.phone) if p.phone else []
            for a in arrivals:
                code = icd(r)
                mm = a.month
                if code in ("J10.1",) and mm not in (1, 2, 3, 12) and r.random() < 0.7:
                    code = icd(r)
                if code == "J21.0" and mm not in (11, 12, 1, 2) and r.random() < 0.7:
                    code = icd(r)
                age = age_at(p.birth, a.date())
                if code.startswith("O") and (p.sex != "F" or not 16 <= age <= 46):
                    code = "R10.4"
                if code in ("I21.4", "I63.9", "I26.9", "A41.9") or (code in CHEST and r.random() < 0.3):
                    tri = r.choice("AB") if r.random() < 0.75 else "C"
                else:
                    tri = wchoice(r, list(TRIAGE_W.items()))
                cancelled = r.random() < 0.0025
                disp = "cancelled_duplicate" if cancelled else wchoice(r, list(DISPO_BY_TRIAGE[tri].items()))
                mode = ("helicopter" if tri in "AB" and r.random() < 0.004 else
                        "ambulance" if r.random() < {"A": 0.75, "B": 0.55, "C": 0.27, "D": 0.21, "E": 0.17}[tri] else
                        "police" if (code in ("F10.0", "T63.4") or code.startswith("S")) and r.random() < 0.05 else "walk-in")
                unit = (f"MEDHELI-{r.choice([3, 4])}" if mode == "helicopter" else
                        f"AU-{AMBULANCE_BASE.get(p.municipality, 'TKU') if r.random() < 0.8 else r.choice(list(AMBULANCE_BASE.values()))}-{r.randint(11, 54)}" if mode == "ambulance" else "")
                los = 0 if cancelled else max(5, int(r.lognormvariate(math.log(LOS_MEDIAN[tri] * LOS_FACTOR.get(disp, 1.0)), 0.5)))
                los = min(los, 2880)
                infectious = code in INFECTIOUS
                temp = round(r.gauss(38.4, 0.7) if infectious else r.gauss(36.9, 0.35), 1)
                bad_discharge = (not cancelled) and r.random() < 0.0014
                discharge = a + timedelta(minutes=los) if not bad_discharge else a - timedelta(minutes=r.randint(10, 120))
                sys_bp = int(r.gauss(138, 22)) if r.random() > 0.104 else None
                vis = {
                    "person": p, "arrival": a, "discharge": discharge, "code": code, "triage": tri, "disp": disp, "mode": mode,
                    "unit": unit, "los": "" if bad_discharge else los, "temp": temp, "infectious": infectious, "age": age,
                    "physician": r.choice(physicians), "cancelled": cancelled,
                    "row": {
                        "visit_id": ids["visit"].new(),
                        "patient_hetu": p.hetu if (p.health_has_hetu and p.hetu) else "",
                        "patient_name": (f"{p.surname.upper()} {' '.join(p.given)}" if r.random() < 0.03 else f"{p.surname} {' '.join(p.given)}"),
                        "date_of_birth": "" if r.random() < 0.004 else p.birth.isoformat(),
                        "sex": p.sex,
                        "phone": (r.choice(fmt_pool) if (p.health_has_phone and fmt_pool) else p.extra.get("foreign_phone", "")),
                        "home_address": p.street, "postcode": p.postcode, "municipality": p.municipality,
                        "arrival_ts": ts_health(a), "arrival_mode": mode, "ambulance_unit": unit, "triage": tri,
                        "chief_complaint": "", "icd10_primary": "" if r.random() < 0.0025 else code,
                        "icd10_secondary": "|".join(sorted({icd2(r) for _ in range(r.choice([1, 1, 2]))})) if r.random() < 0.31 else "",
                        "systolic_bp": "" if sys_bp is None else sys_bp, "diastolic_bp": "" if sys_bp is None else int(sys_bp * r.uniform(0.55, 0.7)),
                        "heart_rate": "" if r.random() < 0.031 else int(r.gauss(98 if infectious else 88, 16)),
                        "resp_rate": "" if r.random() < 0.22 else max(8, int(r.gauss(20 if infectious else 17, 3))),
                        "temp_c": "" if r.random() < 0.079 else temp,
                        "spo2": "" if r.random() < 0.051 else min(100, int(r.gauss(94 if code in ("J18.9", "J44.1", "U07.1") else 97, 2))),
                        "pain_nrs": "" if r.random() < 0.2 else r.randint(0, 10),
                        "attending_physician_id": "", "attending_physician_name": "",
                        "discharge_ts": ts_health(discharge), "los_minutes": "", "disposition": disp, "readmit_30d": "",
                    },
                }
                vis["row"]["attending_physician_id"], vis["row"]["attending_physician_name"] = vis["physician"]
                vis["row"]["los_minutes"] = vis["los"]
                vis["row"]["chief_complaint"], vis["cc_spans"] = self._chief_complaint(r, code, p)
                visits.append(vis)
        # readmit_30d: next arrival of the same identified patient within 30 days of this discharge
        by_person: Dict[str, List[Dict[str, Any]]] = {}
        for v in visits:
            if v["person"].pid and v["row"]["patient_hetu"]:
                by_person.setdefault(v["person"].pid, []).append(v)
        for vs in by_person.values():
            vs.sort(key=lambda v: v["arrival"])
            for i, v in enumerate(vs):
                if v["cancelled"]:
                    continue
                nxt = vs[i + 1]["arrival"] if i + 1 < len(vs) else None
                v["row"]["readmit_30d"] = 1 if (nxt and timedelta(0) <= nxt - v["discharge"] <= timedelta(days=30)) else 0
        visits.sort(key=lambda v: (v["arrival"], v["row"]["visit_id"]))
        labs = self._labs(r, visits, ids)
        notes = self._notes(r, visits, ids, nurses)
        return {"visits": visits, "labs": labs, "notes": notes}

    def _chief_complaint(self, r: random.Random, code: str, p: Person) -> Tuple[str, List[Dict[str, Any]]]:
        base_fi = {"R07.4": "rintakipu", "R10.4": "vatsakipu", "N39.0": "kirvely virtsatessa", "J10.1": "kuume ja yskä",
                   "A08.4": "oksentelu ja ripuli", "F10.0": "päihtynyt", "R51": "päänsärky", "R55": "pyörtyminen",
                   "J18.9": "hengenahdistus ja kuume", "I48.9": "sydämentykytys", "M54.5": "selkäkipu", "U07.1": "kuume, kurkkukipu"}
        base_en = {"R07.4": "chest pain", "R10.4": "abdominal pain", "J10.1": "fever and cough", "R51": "headache"}
        lang = "en" if r.random() < 0.06 else "fi"
        if code in INJURY:
            txt = "fell and hurt " + r.choice(["wrist", "ankle", "head"]) if lang == "en" else "kaatui, " + r.choice(["ranne", "nilkka", "pää"]) + " kipeä"
        else:
            txt = (base_en.get(code) if lang == "en" else base_fi.get(code)) or ("feeling unwell" if lang == "en" else "yleiskunnon lasku")
        st = SpanText().add(txt)
        u = r.random()
        if u < 0.007:   # official chief_complaint spans are LOCATION / ORG only (non-identifying)
            st.add(" kaupungilla " if lang == "fi" else " in ").pii(p.municipality if p.municipality != "non-resident" else "Turku", "LOCATION")
        elif u < 0.011:
            st.add(" töissä " if lang == "fi" else " at work at ").pii(self.employers[r.randrange(len(self.employers))], "ORG")
        return st.text(), st.spans

    def _labs(self, r: random.Random, visits: List[Dict[str, Any]], ids: Dict[str, IdPool]) -> List[Dict[str, Any]]:
        out = []
        for v in visits:
            if v["cancelled"] or r.random() > {"A": 0.95, "B": 0.85, "C": 0.65, "D": 0.45, "E": 0.25}[v["triage"]]:
                continue
            code, p = v["code"], v["person"]
            tests = ["B-Hb", "B-Leuk", "P-K", "P-Na", "P-Krea"][: r.randint(2, 5)]
            if v["infectious"] or code in ABDOMINAL or r.random() < 0.45:
                tests.append("P-CRP")
            if code in CHEST:
                tests.append("P-TnT")
            if code in ("R10.4", "K80.2", "K35.8"):
                tests.append("P-Amyl")
            if code in ("J10.1", "J06.9", "R50.9"):
                tests.append("InfAB-NhO")
            if code in ("U07.1", "J06.9"):
                tests.append("SARSCoV2-NhO")
            if code == "E10.1":
                tests.append("fP-Gluk")
            if code in ("F10.0", "T63.4") or (code.startswith("S06") and r.random() < 0.3):
                tests.append("P-Etanol")
            if code == "I50.9":
                tests.append("P-proBNP")
            if code == "I26.9":
                tests.append("fP-D-Dimer")
            if code.startswith("O"):
                tests.append("U-hCG")
            for t in tests:
                val, flag = self._lab_value(r, t, v, p)
                name, unit, ref = LAB_TESTS[t]
                if ref is None:
                    ref = ("117-155" if p.sex == "F" else "134-167") if t == "B-Hb" else ("50-90" if p.sex == "F" else "60-100")
                sampled = v["arrival"] + timedelta(minutes=r.randint(15, 94))
                out.append({"row": {"lab_id": ids["lab"].new(), "visit_id": v["row"]["visit_id"], "test_code": t, "test_name": name,
                                    "value": val, "unit": unit, "ref_range": ref, "abnormal_flag": flag, "sampled_ts": ts_health(sampled)},
                            "person": p})
        out.sort(key=lambda x: x["row"]["lab_id"])
        return out

    def _lab_value(self, r: random.Random, t: str, v: Dict[str, Any], p: Person) -> Tuple[str, str]:
        if t == "P-CRP":
            if v["infectious"] or v["temp"] >= 37.8:
                x = int(min(606, max(4, math.exp(math.log(25) + 1.4 * (v["temp"] - 37.0) + r.gauss(0, 0.6)))))
            elif r.random() < 0.55:
                return "<3", ""
            else:
                x = int(min(120, max(4, math.exp(r.gauss(math.log(8), 0.6)))))
            return str(x), "H" if x >= 10 else ""
        if t == "B-Hb":
            x = int(r.gauss(136 if p.sex == "F" else 150, 13))
            lo, hi = (117, 155) if p.sex == "F" else (134, 167)
            return str(x), "L" if x < lo else "H" if x > hi else ""
        if t == "B-Leuk":
            x = round(max(0.8, r.gauss(11.5 if v["infectious"] else 7.0, 3.0)), 1)
            return str(x), "H" if x > 8.2 else "L" if x < 3.4 else ""
        if t == "P-K":
            return str(round(r.uniform(3.3, 4.9) if r.random() < 0.95 else r.uniform(2.7, 5.4), 1)), ""
        if t == "P-Na":
            return str(int(r.gauss(140, 3))), ""
        if t == "P-Krea":
            return str(int(max(39, r.lognormvariate(math.log(75), 0.3)))), ""
        if t == "P-TnT":
            return ("<5", "") if r.random() < 0.08 else (str(int(max(5, r.lognormvariate(math.log(14 if v["code"] != "I21.4" else 400), 0.9)))), "")
        if t == "P-Amyl":
            return str(int(max(8, r.lognormvariate(math.log(35), 0.4)))), ""
        if t in ("InfAB-NhO", "SARSCoV2-NhO"):
            pos = r.random() < (0.62 if t == "InfAB-NhO" and v["code"] == "J10.1" else 0.7 if v["code"] == "U07.1" else 0.15)
            return ("POS", "A") if pos else ("NEG", "")
        if t == "fP-Gluk":
            return str(round(r.uniform(2.0, 30.0), 1)), ""
        if t == "P-Etanol":
            return f"{r.uniform(0.77, 4.63):.2f}", "H"
        if t == "P-proBNP":
            return str(int(r.lognormvariate(math.log(3000), 1.0))), ""
        if t == "fP-D-Dimer":
            return f"{r.uniform(0.68, 21.8):.2f}", "H"
        return "POS", "A"  # U-hCG

    def _notes(self, r: random.Random, visits: List[Dict[str, Any]], ids: Dict[str, IdPool], nurses) -> List[Dict[str, Any]]:
        out = []
        for v in visits:
            if v["cancelled"] or r.random() > 0.57:
                continue
            p, a = v["person"], v["arrival"]
            kinds = ["physician"] if r.random() < 0.725 else ["nurse_triage"] if r.random() < 0.51 else ["nurse_triage", "physician"]
            for kind in kinds:
                lang = p.language if p.language in ("fi", "sv", "en") else "fi"
                if kind == "nurse_triage":
                    staff = r.choice(nurses)
                    written = a + timedelta(minutes=r.randint(3, 24))
                    st = SpanText()
                    if lang == "en":
                        st.add("Triage: ").pii(str(v["age"]), "AGE").add(f"-year-old, {v['row']['chief_complaint']}, triage {v['triage']}.")
                    elif lang == "sv":
                        st.add("Triage: ").pii(str(v["age"]), "AGE").add(f" år, {v['row']['chief_complaint']}, triage {v['triage']}.")
                    else:
                        st.add("Triage: ").pii(str(v["age"]), "AGE").add(f"-vuotias, {v['row']['chief_complaint']}, kiireellisyys {v['triage']}.")
                else:
                    staff = v["physician"]
                    written = a + timedelta(minutes=r.randint(19, 399))
                    st = self._physician_note(r, v, p, lang, staff)
                errs = validate_spans(st.text(), st.spans)
                if errs:
                    raise AssertionError(f"internal span error: {errs[:2]}")
                out.append({"row": {"note_id": ids["note"].new(), "visit_id": v["row"]["visit_id"], "note_type": kind,
                                    "author_staff_id": staff[0], "author_name": staff[1], "written_ts": ts_health(written),
                                    "language": lang, "note_text": st.text()}, "spans": st.spans, "person": p})
        out.sort(key=lambda x: x["row"]["note_id"])
        return out

    def _physician_note(self, r: random.Random, v: Dict[str, Any], p: Person, lang: str, staff) -> SpanText:
        st = SpanText()
        name = f"{' '.join(p.given)} {p.surname}" if p.pid else f"{p.given[0]} {p.surname}"
        cd = v["arrival"] + timedelta(days=r.randint(7, 30))
        ctrl = f"{cd.day}.{cd.month}.{cd.year}"  # D.M.YYYY, platform-independent
        L = {"fi": ("Potilas: ", "Tulosyy: ", "Esitiedot: ", "Nykytila: ", "Status: ", "Arvio: ", "-vuotias", " Puh. ", " Kontrolli ", "Osoite: "),
             "sv": ("Patient: ", "Kontaktorsak: ", "Anamnes: ", "Status: ", "Status: ", "Bedömning: ", " år", " Tel. ", " Kontroll ", "Adress: "),
             "en": ("Patient: ", "Reason for visit: ", "History: ", "Exam: ", "Exam: ", "Assessment: ", "-year-old", " Tel. ", " Follow-up ", "Address: ")}[lang]
        if r.random() < 0.3 or not p.hetu:
            st.add(L[0]).pii(name, "PERSON")
            if p.hetu and v["row"]["patient_hetu"] and r.random() < 0.6:
                st.add(", ").pii(p.hetu, "NATIONAL_ID")
            st.add("\n")
        st.add(L[1] + v["row"]["chief_complaint"] + "\n")
        st.add(L[2]).pii(str(v["age"]), "AGE").add(L[6] + (", " + r.choice(["verenpainetauti", "astma", "diabetes", "ei perussairauksia"]) if lang == "fi" else "") + ".\n")
        st.add(L[3] + ("kuumeinen, " if v["infectious"] else "") + ("hoitava lääkäri tavattu." if lang == "fi" else "seen by physician."))
        if v["row"]["phone"] and r.random() < 0.18:
            st.add(L[7]).pii(v["row"]["phone"], "PHONE")
        if r.random() < 0.05 and p.street:
            st.add(" " + L[9]).pii(p.street, "ADDRESS")
        st.add("\n" + L[4] + f"T {v['temp']}, RR {v['row']['systolic_bp'] or '-'}/{v['row']['diastolic_bp'] or '-'}\n")
        st.add(L[5] + f"{v['code']}." + L[8]).pii(ctrl, "DATE").add(".\n")
        st.pii(staff[1], "PERSON")
        return st

    # -- finance
    def finance(self, customers: List[Person], ids: Dict[str, IdPool], stage: str) -> Dict[str, Any]:
        r = self.rng(f"finance:{stage}")
        mcc_pick = Weighted(MCC_W)
        hour = Weighted(list(enumerate([2624, 1735, 686, 238, 149, 381, 2886, 8132, 12521, 15461, 20427, 28029, 30849,
                                         27689, 26346, 30448, 34917, 38903, 35821, 29732, 22568, 15079, 8232, 4555])))
        merchants: Dict[str, List[Tuple[str, str]]] = {}
        for i in range(max(60, len(customers) // 12)):
            rr = random.Random(f"{self.s}:merchant:{i}")
            mcc = mcc_pick(rr)
            muni = self.muni_pick(rr)
            merchants.setdefault(mcc, []).append((f"{rr.choice(STREET_A)} {rr.choice(['Market', 'Shop', 'Kauppa', 'Store', 'Bar', 'Center', 'Point'])} {i}", muni))
        days = [(FIN_START + timedelta(days=d)).date() for d in range((FIN_END - FIN_START).days + 1)]
        day_w = []
        for d in days:
            w = 1.0 + (0.15 if d.day in (1, 15, 16) else 0) + (0.12 if d.weekday() >= 5 else 0) + (0.6 if d == date(2025, 11, 28) else 0) + (0.2 if d.month == 12 and d.day < 24 else 0) - (0.15 if d.month == 7 else 0)
            day_w.append(w)
        day_pick = Weighted(list(zip(days, day_w)))
        cust_rows, card_rows, tx_rows = [], [], []
        card_owner: Dict[str, Person] = {}
        for p in customers:
            cid = ids["customer"].new()
            p.extra["customer_id"] = cid
            open_min = date(p.birth.year + 15, max(1, p.birth.month), 1)
            open_d = open_min + timedelta(days=r.randint(0, max(1, (date(2025, 6, 24) - open_min).days))) if open_min < date(2025, 6, 24) else date(2025, 6, 24)
            cust_rows.append({"customer_id": cid, "hetu": p.hetu, "full_name": f"{' '.join(p.given)} {p.surname}", "birth_date": p.birth.isoformat(),
                              "street_address": p.street, "postcode": p.postcode, "city": p.municipality, "email": p.email,
                              "phone": ("+358" + p.finance_phone[1:]) if p.finance_phone else "", "iban": p.iban, "income_band": p.income,
                              "occupation": p.occupation, "employer": p.employer, "pep_flag": "True" if r.random() < 0.004 else "False",
                              "kyc_risk": "", "account_open_date": min(open_d, date(2025, 6, 24)).isoformat(), "preferred_language": p.language})
            cust_rows[-1]["kyc_risk"] = "high" if cust_rows[-1]["pep_flag"] == "True" else wchoice(r, [("low", 86), ("medium", 12), ("high", 2)])
            if r.random() > 0.94:
                continue  # customer without a card
            n_cards = wchoice(r, [(1, 83), (2, 16), (3, 1)])
            activity = r.lognormvariate(0, 0.45)
            travels = r.random() < 0.14
            for _ in range(n_cards):
                pan = self._pan(r)
                card = {"card_ref_id": ids["card"].new(), "customer_id": cid, "card_pan": pan, "card_type": "credit" if r.random() < 0.14 else "debit",
                        "issued_date": (date(2021, 8, 31) + timedelta(days=r.randint(0, 1400))).isoformat(),
                        "expiry": f"{r.randint(1, 12):02d}/{r.randint(26, 30)}", "status": "active"}
                card_rows.append(card)
                card_owner[pan] = p
                fraud = r.random() < self.cfg.fraud_card_share
                incident = None
                if fraud:
                    incident = datetime.combine(day_pick(r), datetime.min.time()) + timedelta(hours=hour(r), minutes=r.randint(0, 59))
                    if incident < datetime(2025, 8, 1):
                        incident += timedelta(days=31)
                n_tx = max(1, int(r.gauss(self.cfg.tx_per_card * activity / max(1, n_cards ** 0.5), 6)))
                for _ in range(n_tx):
                    d = day_pick(r)
                    ts = datetime(d.year, d.month, d.day, hour(r), r.randint(0, 59), r.randint(0, 59))
                    if incident and ts >= incident:
                        continue  # card closed after the fraud incident
                    tx_rows.append(self._tx(r, ids, pan, ts, mcc_pick, merchants, p, travels, None))
                if incident:
                    ftype = wchoice(r, FRAUD_TYPES)
                    n_f = {"card_testing": r.randint(3, 8), "skimming": r.randint(1, 3), "lost_stolen": r.randint(2, 5),
                           "cnp_cashout": r.randint(1, 3), "account_takeover": r.randint(1, 2)}[ftype]
                    for j in range(n_f):
                        tx_rows.append(self._tx(r, ids, pan, incident + timedelta(minutes=j * r.randint(1, 40)), mcc_pick, merchants, p, travels, ftype))
                    card["status"] = "closed_fraud"
                    repl = self._pan(r)
                    card_rows.append({"card_ref_id": ids["card"].new(), "customer_id": cid, "card_pan": repl, "card_type": card["card_type"],
                                      "issued_date": (incident.date() + timedelta(days=r.randint(3, 10))).isoformat(),
                                      "expiry": f"{r.randint(1, 12):02d}/{r.randint(29, 30)}", "status": "active"})
                    card_owner[repl] = p
                    for _ in range(max(1, n_tx // 4)):
                        d = day_pick(r)
                        ts = datetime(d.year, d.month, d.day, hour(r), r.randint(0, 59), r.randint(0, 59))
                        if ts > incident + timedelta(days=10):
                            tx_rows.append(self._tx(r, ids, repl, ts, mcc_pick, merchants, p, travels, None))
        tx_rows.sort(key=lambda t: (t["ts"], t["tx_id"]))
        cust_rows.sort(key=lambda c: c["customer_id"])
        return {"customers": cust_rows, "cards": card_rows, "tx": tx_rows, "card_owner": card_owner}

    def _device(self, p: Person, pan: str, r: random.Random) -> str:
        """1-3 stable 36-char device ids per card (UUID shape, generated)."""
        devs = p.extra.setdefault("devices", {}).setdefault(pan, [])
        if not devs or (len(devs) < 3 and r.random() < 0.05):
            h = f"{r.getrandbits(128):032x}"
            devs.append(f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}")
        return r.choice(devs)

    def _tx(self, r, ids, pan, ts, mcc_pick, merchants, p: Person, travels: bool, ftype: Optional[str]) -> Dict[str, Any]:
        country, city, cur, rate, coord = "FI", p.municipality, "EUR", 1.0, None
        if ftype == "card_testing":
            mcc, channel, amount = r.choice(["5999", "5816"]), "ecom", r.uniform(0.5, 1.99)
            country, city, cur, rate, coord = wchoice(r, [(f, 1) for f in FOREIGN if f[0] in ("US", "NL", "GB")])
            city = ""
        elif ftype == "skimming":
            mcc, channel, amount = "6011", "chip", r.uniform(100, 399)
            country, city, cur, rate, coord = r.choice([f for f in FOREIGN if f[0] in ("US", "ES", "MT")])
        elif ftype == "lost_stolen":
            mcc, channel, amount = r.choice(["5411", "5812", "5541"]), "contactless", r.uniform(16, 50)
        elif ftype == "cnp_cashout":
            mcc, channel, amount = r.choice(["5732", "5999"]), "ecom", r.uniform(151, 906)
        elif ftype == "account_takeover":
            mcc, channel, amount = r.choice(["5732", "4511"]), "ecom", r.uniform(409, 1448)
        else:
            mcc = mcc_pick(r)
            channel = "ecom" if mcc in ECOM_ONLY else "chip" if mcc == "6011" else ("contactless" if r.random() < 0.67 else "chip") if r.random() > 0.08 else "ecom"
            amount = max(0.33, r.lognormvariate(math.log(MCC_MEDIAN.get(mcc, 22.0)), 0.75))
            if travels and r.random() < 0.06:
                country, city, cur, rate, coord = r.choice(FOREIGN)
            elif r.random() < 0.08:
                city = "Helsinki"
        name, mcity = r.choice(merchants.get(mcc) or [(f"Merchant {mcc}", "Turku")])
        if country == "FI" and city != "Helsinki":
            city = mcity if r.random() < 0.6 else p.municipality
        lat = lon = ""
        if channel != "ecom":
            c = coord or MUNI_CENTROID.get(city, (60.1 if city == "Helsinki" else 60.5, 24.9 if city == "Helsinki" else 22.5))
            lat, lon = f"{c[0] + r.uniform(-0.05, 0.05):.6f}", f"{c[1] + r.uniform(-0.08, 0.08):.6f}"
        fraud_ip = ftype in ("card_testing", "cnp_cashout", "account_takeover")
        return {"tx_id": ids["tx"].new(), "card_pan": pan, "ts": ts_fin(ts), "amount_eur": fmt_amount(amount),
                "original_amount": fmt_amount(amount * rate), "currency": cur, "merchant_name": name, "mcc": mcc,
                "merchant_city": city, "merchant_country": country, "channel": channel, "pos_lat": lat, "pos_lon": lon,
                "device_id": self._device(p, pan, r) if channel == "ecom" else "",
                "ip_address": ((r.choice(["203.0.113.", "198.51.100.", "192.0.2."]) + str(r.randint(1, 254))) if fraud_ip else f"100.{r.randint(64, 127)}.{r.randint(0, 255)}.{r.randint(1, 254)}") if channel == "ecom" else "",
                "is_fraud": 1 if ftype else 0, "fraud_type": ftype or "", "_ts": ts}

    # -- adversary knowledge tied to the synthetic identities
    def adversaries(self, people: List[Person], health: Dict[str, Any], fin: Dict[str, Any], ids_rng: random.Random) -> Dict[str, Any]:
        r = self.rng("adversary")
        out: Dict[str, Any] = {}
        # public_directory: subset of the population, partly stale, mostly without phone
        rows, truth = [], []
        listed = [p for p in people if r.random() < 0.45]
        for i, p in enumerate(listed, 1):
            name = p.calling if r.random() > 0.05 else f"{p.given[0][0]}. {p.surname}"
            post = p.postcode if r.random() > 0.06 else r.choice(self.post_by_muni[p.municipality])
            street = p.street if r.random() > 0.15 else self._street(r)
            phone = r.choice(phone_formats(p.phone)) if r.random() < 0.29 else ""
            aid = f"DIRP{i:06d}"
            rows.append([aid, name, street, post, p.municipality, phone])
            truth.append([aid, p.pid])
        out["public_directory"] = (["adv_row_id", "name", "street_address", "postcode", "city", "phone"], rows, truth)
        # news_clips_health: notable ED visits of identified residents (+ decoys)
        vis = [v for v in health["visits"] if v["person"].pid and (v["code"] in INJURY or v["code"] in ("I21.4", "I63.9", "T63.4"))]
        r.shuffle(vis)
        rows, truth = [], []
        sample = vis[: max(5, int(len(health["visits"]) * 0.005))]
        decoys = [p for p in people if p.membership in ("finance", "none")][: max(1, len(sample) // 10)]
        for i, v in enumerate(sample + [None] * len(decoys), 1):
            p = v["person"] if v else decoys[i - len(sample) - 1]
            a = v["arrival"] if v else datetime(2025, r.randint(1, 12), r.randint(1, 28), r.randint(0, 23))
            age = age_at(p.birth, a.date())
            aid = f"NEWS{i:05d}"
            rows.append([aid, (a.date() + timedelta(days=r.randint(0, 2))).isoformat(), r.choice(["Onnettomuus", "Kaatuminen", "Tapaturma", "Ensihoito hälytettiin"]),
                         "Paikallinen uutinen kertoo tapahtumasta; henkilö vietiin päivystykseen.", a.date().isoformat() if r.random() < 0.53 else "",
                         p.municipality if r.random() < 0.93 else "", "" if r.random() < 0.06 else str(age + r.randint(-6, 4)), p.sex,
                         p.calling if r.random() < 0.12 else ""])
            truth.append([aid, p.pid])
        out["news_clips_health"] = (["adv_row_id", "published_date", "headline", "text", "event_date", "place", "age_mentioned", "sex_mentioned", "name_mentioned"], rows, truth)
        # social_posts_health: a few patients post shortly after arrival (+ decoys)
        vis = [v for v in health["visits"] if v["person"].pid]
        r.shuffle(vis)
        rows, truth = [], []
        sample = vis[: max(10, int(len(vis) * 0.02))]
        decoys = [p for p in people if p.membership in ("finance", "none")][: max(1, len(sample) // 10)]
        for i, v in enumerate(sample + [None] * len(decoys), 1):
            p = v["person"] if v else decoys[i - len(sample) - 1]
            posted = (v["arrival"] + timedelta(hours=r.uniform(1, 15))) if v else datetime(2025, r.randint(1, 12), r.randint(1, 28), r.randint(0, 23))
            aid = f"POST{i:05d}"
            rows.append([aid, r.choice(["PhotoShare", "MicroPost", "Forum"]), f"{p.given[0].lower()}{r.randint(10, 99999)}",
                         "" if r.random() < 0.3 else (p.calling if r.random() < 0.6 else p.given[0]), "" if r.random() < 0.4 else p.municipality,
                         posted.strftime("%Y-%m-%d %H:%M:%S"), r.choice(["Päivystyksessä odottelua...", "Taas sairaalassa", "Long wait at the ER"]),
                         "Aurajoki Regional Hospital" if r.random() < 0.7 else ""])
            truth.append([aid, p.pid])
        out["social_posts_health"] = (["adv_row_id", "platform", "handle", "display_name", "profile_city", "posted_ts", "text", "place_tag"], rows, truth)
        # receipt_photos_ocr: shared receipts that match real (synthetic) transactions (+ non-matching)
        txs = [t for t in fin["tx"] if not t["is_fraud"] and t["merchant_country"] == "FI"]
        r.shuffle(txs)
        rows, truth = [], []
        sample = txs[: max(10, min(1500, int(len(txs) * 0.012)))]
        for i, t in enumerate(sample, 1):
            owner = fin["card_owner"][t["card_pan"]]
            ts = t["_ts"] + timedelta(seconds=r.randint(-60, 119))
            amount = float(t["amount_eur"]) if r.random() < 0.88 else float(t["amount_eur"]) * r.uniform(0.6, 1.4)
            last4 = t["card_pan"][-4:]
            aid = f"RCP{i:05d}"
            rows.append([aid, f"@{owner.given[0].lower()}{r.randint(1, 99)}" if r.random() < 0.6 else f"{owner.given[0]} {owner.surname[0]}.",
                         t["merchant_name"], ts.strftime("%d.%m.%Y"), ts.strftime("%H:%M"), f"{amount:.2f}".replace(".", ",") + " €",
                         ("************" + last4) if r.random() < 0.6 else ("XXXX XXXX XXXX " + last4),
                         "Visa" if t["card_pan"].startswith("4") else "Mastercard", r.choice(["", "Jaetaan lasku", "Kulukorvaus", "Takuukuitti talteen"])])
            truth.append([aid, owner.pid])
        out["receipt_photos_ocr"] = (["adv_row_id", "posted_by", "merchant_name", "receipt_date", "receipt_time", "total", "card_masked", "card_brand", "context"], rows, truth)
        return out


# --------------------------------------------------------------------------- writing
ED_COLS = ["visit_id", "patient_hetu", "patient_name", "date_of_birth", "sex", "phone", "home_address", "postcode", "municipality",
           "arrival_ts", "arrival_mode", "ambulance_unit", "triage", "chief_complaint", "icd10_primary", "icd10_secondary", "systolic_bp",
           "diastolic_bp", "heart_rate", "resp_rate", "temp_c", "spo2", "pain_nrs", "attending_physician_id", "attending_physician_name",
           "discharge_ts", "los_minutes", "disposition", "readmit_30d"]
LAB_COLS = ["lab_id", "visit_id", "test_code", "test_name", "value", "unit", "ref_range", "abnormal_flag", "sampled_ts"]
NOTE_COLS = ["note_id", "visit_id", "note_type", "author_staff_id", "author_name", "written_ts", "language", "note_text"]
CUST_COLS = ["customer_id", "hetu", "full_name", "birth_date", "street_address", "postcode", "city", "email", "phone", "iban", "income_band",
             "occupation", "employer", "pep_flag", "kyc_risk", "account_open_date", "preferred_language"]
CARD_COLS = ["card_ref_id", "customer_id", "card_pan", "card_type", "issued_date", "expiry", "status"]
TX_COLS = ["tx_id", "card_pan", "ts", "amount_eur", "original_amount", "currency", "merchant_name", "mcc", "merchant_city", "merchant_country",
           "channel", "pos_lat", "pos_lon", "device_id", "ip_address", "is_fraud", "fraud_type"]
SCHEMA = {("health", "ed_visits"): ED_COLS, ("health", "lab_results"): LAB_COLS, ("health", "clinical_notes"): NOTE_COLS,
          ("finance", "customers"): CUST_COLS, ("finance", "cards"): CARD_COLS, ("finance", "card_transactions"): TX_COLS}
GENERATED_ADVERSARIES = ("public_directory", "news_clips_health", "social_posts_health", "receipt_photos_ocr")


def official_headers(official: Path) -> Dict[Tuple[str, str], List[str]]:
    return {k: read_header(official / "data" / k[0] / f"{k[1]}.csv") for k in SCHEMA if (official / "data" / k[0] / f"{k[1]}.csv").is_file()}


def write_metadata(pack: Path, official: Path) -> Dict[str, Any]:
    md = pack / "metadata"
    md.mkdir(parents=True, exist_ok=True)
    rows, header = read_csv(official / "metadata" / "field_catalog.csv")
    keep = [rw for rw in rows if rw["dataset"] in ("health", "finance")]
    write_csv(md / "field_catalog.csv", header, ([rw[h] for h in header] for rw in keep))
    scen = [s for s in json.loads((official / "metadata" / "scenarios.json").read_text(encoding="utf-8")) if s["id"] in ("HEALTH-S1", "FIN-S2")]
    write_json(md / "scenarios.json", scen)
    specs = json.loads((official / "metadata" / "attack_specs.json").read_text(encoding="utf-8"))
    attacks = [a for a in specs["attacks"] if a["dataset"] in ("health", "finance") and a["adversary"] in GENERATED_ADVERSARIES]
    write_json(md / "attack_specs.json", {"version": specs.get("version"), "description": "Copied verbatim from the official pack for the health/finance attacks "
                                          "whose adversary files are regenerated synthetically for this test pack.", "attacks": attacks, "trajectories": []})
    for name in ("pii_span_guidelines.md", "taxonomy.md"):
        if (official / "metadata" / name).is_file():
            shutil.copyfile(official / "metadata" / name, md / name)
    return {"catalog_rows": len(keep), "scenarios": [s["id"] for s in scen], "attacks": [(a["adversary"], a["dataset"], a["table"]) for a in attacks]}


def generate(cfg: Config, pack: Path, private: Path, official: Path = OFFICIAL_PACK) -> Dict[str, Any]:
    refuse_forbidden(pack, "test pack")
    refuse_forbidden(private, "private ground truth")
    if pack.exists() and any(pack.iterdir()):
        raise ValueError(f"pack directory is not empty: {pack}")
    t0 = time.perf_counter()
    g = Generator(cfg)
    people, hold = g.population()
    idr = random.Random(f"{cfg.seed}:ids")
    ids = {"visit": IdPool(idr, "ED25-", 6, 2), "lab": IdPool(idr, "LAB", 7), "note": IdPool(idr, "N", 7),
           "customer": IdPool(idr, "SB", 8, 10_000_000), "card": IdPool(idr, "CRD", 7), "tx": IdPool(idr, "TX", 10)}
    health = g.health([p for p in people if p.membership in ("both", "health")], ids, "main", nonresident=True)
    fin = g.finance([p for p in people if p.membership in ("both", "finance")], ids, "main")
    h_hold = g.health([p for p in hold if p.membership == "holdout_health"], ids, "holdout", nonresident=False)
    f_hold = g.finance([p for p in hold if p.membership == "holdout_finance"], ids, "holdout")
    adv = g.adversaries(people, health, fin, idr)

    data = pack / "data"
    def ed_rows(h):
        return ([v["row"][c] for c in ED_COLS] for v in h["visits"])
    write_csv(data / "health" / "ed_visits.csv", ED_COLS, ed_rows(health))
    write_csv(data / "health" / "lab_results.csv", LAB_COLS, ([x["row"][c] for c in LAB_COLS] for x in health["labs"]))
    write_csv(data / "health" / "clinical_notes.csv", NOTE_COLS, ([x["row"][c] for c in NOTE_COLS] for x in health["notes"]))
    write_csv(data / "finance" / "customers.csv", CUST_COLS, ([c[k] for k in CUST_COLS] for c in fin["customers"]))
    write_csv(data / "finance" / "cards.csv", CARD_COLS, ([c[k] for k in CARD_COLS] for c in fin["cards"]))
    write_csv(data / "finance" / "card_transactions.csv", TX_COLS, ([t[k] for k in TX_COLS] for t in fin["tx"]))
    hd = pack / "holdout"
    write_csv(hd / "health" / "ed_visits.csv", ED_COLS, ed_rows(h_hold))
    write_csv(hd / "health" / "lab_results.csv", LAB_COLS, ([x["row"][c] for c in LAB_COLS] for x in h_hold["labs"]))
    write_csv(hd / "health" / "clinical_notes.csv", NOTE_COLS, ([x["row"][c] for c in NOTE_COLS] for x in h_hold["notes"]))
    write_csv(hd / "finance" / "customers.csv", CUST_COLS, ([c[k] for k in CUST_COLS] for c in f_hold["customers"]))
    write_csv(hd / "finance" / "cards.csv", CARD_COLS, ([c[k] for k in CARD_COLS] for c in f_hold["cards"]))
    write_csv(hd / "finance" / "card_transactions.csv", TX_COLS, ([t[k] for k in TX_COLS] for t in f_hold["tx"]))
    # truth (record -> person): read by pets-eval by column position
    tr = pack / "truth"
    write_csv(tr / "health__ed_visits.csv", ["record_id", "person_id"], ([v["row"]["visit_id"], v["person"].pid] for v in health["visits"]))
    write_csv(tr / "health__lab_results.csv", ["record_id", "person_id"], ([x["row"]["lab_id"], x["person"].pid] for x in health["labs"]))
    write_csv(tr / "health__clinical_notes.csv", ["record_id", "person_id"], ([x["row"]["note_id"], x["person"].pid] for x in health["notes"]))
    write_csv(tr / "health__holdout_ed_visits.csv", ["record_id", "person_id"], ([v["row"]["visit_id"], v["person"].pid] for v in h_hold["visits"]))
    pid_by_cid = {p.extra["customer_id"]: p.pid for p in people if "customer_id" in p.extra}
    write_csv(tr / "finance__customers.csv", ["record_id", "person_id"], ([c["customer_id"], pid_by_cid[c["customer_id"]]] for c in fin["customers"]))
    write_csv(tr / "finance__cards.csv", ["record_id", "person_id"], ([c["card_ref_id"], pid_by_cid[c["customer_id"]]] for c in fin["cards"]))
    write_csv(tr / "finance__card_transactions.csv", ["record_id", "person_id"], ([t["tx_id"], fin["card_owner"][t["card_pan"]].pid] for t in fin["tx"]))
    for name, (hdr, rows, truth) in adv.items():
        write_csv(pack / "adversary" / f"{name}.csv", hdr, rows)
        write_csv(tr / f"adversary__{name}.csv", ["adv_row_id", "person_id"], truth)
    # PII spans (official record layout; offsets [start, end) into the exact field value)
    sp = pack / "metadata" / "pii_spans"
    sp.mkdir(parents=True, exist_ok=True)
    with open(sp / "health__ed_visits__chief_complaint.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for v in health["visits"]:
            if v["cc_spans"]:
                f.write(json.dumps({"record_id": v["row"]["visit_id"], "spans": [dict(sorted(s.items())) for s in v["cc_spans"]]}, ensure_ascii=False) + "\n")
    with open(sp / "health__clinical_notes__note_text.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for x in health["notes"]:
            f.write(json.dumps({"record_id": x["row"]["note_id"], "spans": [dict(sorted(s.items())) for s in x["spans"]]}, ensure_ascii=False) + "\n")
    meta = write_metadata(pack, official)
    (pack / "README.md").write_text(
        "# Synthetic Health + Finance test pack (Mosaic)\n\nFully synthetic, generated by "
        f"`app/generate_test_data.py` ({GENERATOR_VERSION}). Not the official TrustED pack; no real person is represented.\n"
        "Layout mirrors the official pack so pets-eval can be run with `--root` pointing here.\n", encoding="utf-8")
    # private ground truth (population) - never part of a public export
    private.mkdir(parents=True, exist_ok=True)
    write_csv(private / "population.csv", ["person_id", "membership", "sex", "birth_date", "municipality", "has_health_phone", "same_finance_phone"],
              ([p.pid, p.membership, p.sex, p.birth.isoformat(), p.municipality, int(p.health_has_phone), int(bool(p.finance_phone) and p.finance_phone == p.phone)]
               for p in people + hold))
    gen_seconds = round(time.perf_counter() - t0, 3)
    manifest = build_manifest(cfg, pack, private, meta, official)
    manifest["runtime"] = {"generation_seconds": gen_seconds, "peak_memory_bytes": peak_memory_bytes()}
    return manifest


# --------------------------------------------------------------------------- manifest (observed)
def build_manifest(cfg: Config, pack: Path, private: Path, meta: Dict[str, Any], official: Path) -> Dict[str, Any]:
    tables: Dict[str, Any] = {}
    off = official_headers(official)
    for (ds, tb), cols in SCHEMA.items():
        for area in ("data", "holdout"):
            p = pack / area / ds / f"{tb}.csv"
            hdr = read_header(p)
            with open(p, encoding="utf-8", newline="") as f:
                n = sum(1 for _ in csv.reader(f)) - 1
            tables[f"{area}/{ds}/{tb}"] = {"rows": n, "columns": hdr, "schema_sha256": sha256_text(",".join(hdr)), "file_sha256": sha256_file(p),
                                           "bytes": p.stat().st_size, "matches_official_header": off.get((ds, tb)) == hdr}
    ed, _ = read_csv(pack / "data" / "health" / "ed_visits.csv")
    cu, _ = read_csv(pack / "data" / "finance" / "customers.csv")
    labs, _ = read_csv(pack / "data" / "health" / "lab_results.csv")
    notes, _ = read_csv(pack / "data" / "health" / "clinical_notes.csv")
    cards, _ = read_csv(pack / "data" / "finance" / "cards.csv")
    tx, _ = read_csv(pack / "data" / "finance" / "card_transactions.csv")
    t_ed = {r["record_id"]: r["person_id"] for r in read_csv(pack / "truth" / "health__ed_visits.csv")[0]}
    t_cu = {r["record_id"]: r["person_id"] for r in read_csv(pack / "truth" / "finance__customers.csv")[0]}
    h_persons = {p for p in t_ed.values() if p}
    f_persons = set(t_cu.values())
    h_hetu = {normalize_hetu(r["patient_hetu"]) for r in ed} - {""}
    f_hetu = {normalize_hetu(r["hetu"]) for r in cu} - {""}
    h_phone = {normalize_phone(r["phone"]) for r in ed} - {""}
    f_phone = {normalize_phone(r["phone"]) for r in cu} - {""}
    # accidental collisions: a shared identifier value that maps to two different people
    h_hetu_p = {normalize_hetu(r["patient_hetu"]): t_ed.get(r["visit_id"]) for r in ed if r["patient_hetu"]}
    f_hetu_p = {normalize_hetu(r["hetu"]): t_cu[r["customer_id"]] for r in cu if r["hetu"]}
    h_ph_p = {normalize_phone(r["phone"]): t_ed.get(r["visit_id"]) for r in ed if r["phone"]}
    f_ph_p = {normalize_phone(r["phone"]): t_cu[r["customer_id"]] for r in cu if r["phone"]}
    visit_ids = {r["visit_id"] for r in ed}
    cust_ids = {r["customer_id"] for r in cu}
    pans = {r["card_pan"] for r in cards}
    span_errs = 0
    n_spans = 0
    texts = {r["note_id"]: r["note_text"] for r in notes}
    with open(pack / "metadata" / "pii_spans" / "health__clinical_notes__note_text.jsonl", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            n_spans += len(rec["spans"])
            span_errs += len(validate_spans(texts.get(rec["record_id"], ""), rec["spans"]))
    cc = {r["visit_id"]: r["chief_complaint"] for r in ed}
    with open(pack / "metadata" / "pii_spans" / "health__ed_visits__chief_complaint.jsonl", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            n_spans += len(rec["spans"])
            span_errs += len(validate_spans(cc.get(rec["record_id"], ""), rec["spans"]))
    adv = {}
    for name in GENERATED_ADVERSARIES:
        rows, hdr = read_csv(pack / "adversary" / f"{name}.csv")
        adv[name] = {"rows": len(rows), "columns": hdr}
    return {
        "generator_version": GENERATOR_VERSION, "seed": cfg.seed, "profile": cfg.profile,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config_targets": cfg.__dict__,
        "population": {"size": cfg.people, "health_subjects": len(h_persons), "finance_customers": len(cu), "finance_persons": len(f_persons),
                       "shared_subjects": len(h_persons & f_persons), "nonresident_visits": sum(1 for v in t_ed.values() if not v)},
        "overlaps": {
            "hetu_overlap": len(h_hetu & f_hetu), "phone_overlap_normalised": len(h_phone & f_phone),
            "hetu_collisions_between_different_people": sum(1 for k in h_hetu & f_hetu if h_hetu_p[k] != f_hetu_p[k]),
            "phone_collisions_between_different_people": sum(1 for k in h_phone & f_phone if h_ph_p[k] != f_ph_p[k]),
            "normalisation": {"hetu": "app/normalize.normalize_hetu", "phone": "app/normalize.normalize_phone"},
        },
        "missing_identifiers": {
            "ed_visits_rows_without_hetu": sum(1 for r in ed if not r["patient_hetu"]), "ed_visits_rows_without_phone": sum(1 for r in ed if not r["phone"]),
            "customers_without_phone": sum(1 for r in cu if not r["phone"]), "customers_without_email": sum(1 for r in cu if not r["email"]),
        },
        "relationships": {
            "visits_per_patient_mean": round(len([v for v in t_ed.values() if v]) / max(1, len(h_persons)), 3),
            "lab_results_resolving_to_ed_visits": sum(1 for r in labs if r["visit_id"] in visit_ids), "lab_results": len(labs),
            "clinical_notes_resolving_to_ed_visits": sum(1 for r in notes if r["visit_id"] in visit_ids), "clinical_notes": len(notes),
            "cards_resolving_to_customers": sum(1 for r in cards if r["customer_id"] in cust_ids), "cards": len(cards),
            "transactions_resolving_to_cards": sum(1 for r in tx if r["card_pan"] in pans), "transactions": len(tx),
            "cards_per_customer_mean": round(len(cards) / max(1, len(cu)), 3),
            "fraud_transactions": sum(1 for r in tx if r["is_fraud"] == "1"),
            "fraud_before_2025_11_01": sum(1 for r in tx if r["is_fraud"] == "1" and r["ts"] < "2025-11-01"),
            "fraud_from_2025_11_01": sum(1 for r in tx if r["is_fraud"] == "1" and r["ts"] >= "2025-11-01"),
            "crp_results": sum(1 for r in labs if r["test_code"] == "P-CRP"),
        },
        "pii_spans": {"spans": n_spans, "offset_or_overlap_errors": span_errs},
        "tables": tables, "adversary": adv, "metadata": meta,
        "official_reference_pack": str(official),
    }


def parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a deterministic synthetic Health + Finance test pack")
    p.add_argument("--profile", choices=sorted(PROFILES), default="demo")
    p.add_argument("--people", type=int, default=None)
    p.add_argument("--seed", type=int, default=20261107)
    p.add_argument("--out-root", type=Path, default=DEFAULT_GENERATED_ROOT, help="runs are created as <out-root>/<run_id>/")
    p.add_argument("--run-id", default=None)
    for name, default in (("share-both", 0.20), ("share-health-only", 0.40), ("share-finance-only", 0.15), ("finance-phone-same", 0.88),
                          ("health-phone-missing", 0.25), ("finance-phone-missing", 0.035), ("health-hetu-missing", 0.01)):
        p.add_argument(f"--{name}", type=float, default=default)
    return p.parse_args(argv)


def config_from_args(a: argparse.Namespace) -> Config:
    prof = PROFILES[a.profile]
    return Config(people=a.people or prof["people"], seed=a.seed, share_both=a.share_both, share_health_only=a.share_health_only,
                  share_finance_only=a.share_finance_only, finance_phone_same=a.finance_phone_same, health_phone_missing=a.health_phone_missing,
                  finance_phone_missing=a.finance_phone_missing, health_hetu_missing=a.health_hetu_missing,
                  tx_per_card=prof["tx_per_card"], holdout_share=prof["holdout_share"], fraud_card_share=prof["fraud_card_share"],
                  profile=a.profile)


def main(argv: Optional[Sequence[str]] = None) -> int:
    utf8_stdout()
    a = parse_args(argv)
    cfg = config_from_args(a)
    run_id = a.run_id or f"{cfg.profile}-n{cfg.people}-s{cfg.seed}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run = (a.out_root if a.out_root.is_absolute() else Path.cwd() / a.out_root) / run_id
    refuse_forbidden(run, "run directory")
    if run.exists():
        print(f"error: run directory already exists (never overwritten): {run}", file=sys.stderr)
        return 2
    m = generate(cfg, run / "pack", run / "private")
    write_json(run / "evidence" / "manifest.json", m)
    print(f"run: {run}")
    print(f"population {m['population']['size']} | health subjects {m['population']['health_subjects']} | finance customers "
          f"{m['population']['finance_customers']} | shared {m['population']['shared_subjects']}")
    print(f"HETU overlap {m['overlaps']['hetu_overlap']} | phone overlap {m['overlaps']['phone_overlap_normalised']} | "
          f"collisions {m['overlaps']['hetu_collisions_between_different_people']}/{m['overlaps']['phone_collisions_between_different_people']}")
    print("rows: " + ", ".join(f"{k.split('/', 1)[1]}={v['rows']}" for k, v in m["tables"].items() if k.startswith("data/")))
    print(f"spans {m['pii_spans']['spans']} (errors {m['pii_spans']['offset_or_overlap_errors']}) | generation {m['runtime']['generation_seconds']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
