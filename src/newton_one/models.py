# -*- coding: utf-8 -*-

"""Konstanty a definice sloupců pro newton_one."""

import csv

# Unicode znaky, které by mohly být mezernatami v číslech (např. U+00A0 nbsp, U+2007 thin space)
UNICODE_WHITESPACE = "\xa0\u2007\u2008\u2009\u200a\u205f\u3000"

# =============================================================================
# Konstanty
# =============================================================================

CSV_SEP = ";"                                                  # odliovník sloupců v NewtonOne CSV
ENCODING = "utf-8"                                             # kódování vstupního souboru
JSONL_ENCODING = "utf-8"                                       # kódování výstupního souboru
OUTPUT_DELIMITER = "\t"                                        # oddělovač klíčů v JSON (pro determinismus)

# Sloupci, které budeme extrahovat z CSV
SLoupce = [
    {"nazev": "Kód článku",            "typ": str},
    {"nazev": "Datum publikování",     "typ": str},
    {"nazev": "Název",                "typ": str},
    {"nazev": "Zdroj",                 "typ": str},
    {"nazev": "Země",                  "typ": str},
    {"nazev": "Typ média",             "typ": str},
    {"nazev": "Anotace",               "typ": str},
    {"nazev": "Plné znění",            "typ": str},
    {"nazev": "Paywall",               "typ": str},
    {"nazev": "Originální internetový zdroj", "typ": str, "strip_space": True},
    {"nazev": "Typ zprávy",            "typ": str},
    {"nazev": "Sentiment",             "typ": str},
    {"nazev": "Dosah",                 "typ": int, "strip_space": True},
]

# Maximum retry count pro LLM API volání (Phase 5)
MAX_LLM_RETRY = 3
