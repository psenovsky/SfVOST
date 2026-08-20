# -*- coding: utf-8 -*-

"""Načtení CSV a zápis JSONL – data I/O pro newton_one."""

import csv as _csv
import os


from src.newton_one.models import (
    CSV_SEP,
    ENCODING,
    JSONL_ENCODING,
    OUTPUT_DELIMITER,
    SLoupce,
)
from src.newton_one.utils import parse_datum, strip_unicode_whitespace


def nacti_csv(cesta_csv):
    """
    Načte semicolon-delimited CSV soubor a vrací seznam slovníků.

    Parameters
    ----------
    cesta_csv : str
        Cesta k vstupnímu CSV souboru.

    Vrací
    -----
    list[dict[str, str]]
        Seznam řádků jako slovníky s klíči odpovídajícími názvům sloupců v CSV.
    """
    if not os.path.exists(cesta_csv):
        print(f"❌ Vstupní CSV soubor neexistuje: {cesta_csv}")
        return []

    radky = []
    with open(cesta_csv, "r", encoding=ENCODING, newline="") as f:
        reader = _csv.DictReader(f, delimiter=CSV_SEP)
        for jazyk in reader:
            if not jazyk or all(not v.strip() for v in jazyk.values()):
                continue
            radky.append(jazyk)

    print(f"✅ Načteno {len(radky)} řádků z souboru {cesta_csv}")
    return radky


def pretvorit_radku(radka):
    """
    Přetvoří jeden řádek CSV na JSON objekt podle definice SLoupce.

    Parameters
    ----------
    radka : dict[str, str]
        Jeden řádek z CSV (klíče jsou názvy sloupců).

    Vrací
    -----
    dict[str, str]
        Přetvořený řádek s vypsáním hodnot a formátováním dat.
    """
    vysledek = {}
    for sloupec in SLoupce:
        nazev = sloupec["nazev"]
        hodnota = radka.get(nazev, "")

        # Strhání mezernat ze všech hodnot (včetně Unicode whitespace)
        if sloupec.get("strip_space"):
            hodnota = strip_unicode_whitespace(hodnota)

        if not hodnota:
            hodnota = ""

        if nazev == "URL článku" and sloupec.get("strip_space"):
            hodnota = strip_unicode_whitespace(hodnota)

        # Datum publikování formátujeme na YYYY-MM-DD
        if nazev == "Datum publikování":
            hodnota = parse_datum(hodnota) or hodnota

        # Dosah → integer
        if nazev == "Dosah" and sloupec.get("typ") == int:
            try:
                hodnota = int(float(hodnota))  # float→int pro případ desetinných čísel
            except (ValueError, TypeError):
                hodnota = ""

        vysledek[nazev] = hodnota

    return vysledek


def ulozit_jsonl(radky, cesta_output):
    """
    Uloží řádky do JSONL souboru se sorted keys pro determinismus.

    Parameters
    ----------
    radky : list[dict[str, str]]
        Seznam přetvořených řádků.
    cesta_output : str
        Cesta k výstupnímu JSONL souboru.

    Vrací
    -----
    int
        Počet zapsaných řádků.
    """
    if not radky:
        print("⚠️ Žádné data pro zápis.")
        return 0

    # Zkontrolovat, zda soubor již existuje
    if os.path.exists(cesta_output):
        velkost_input = os.path.getsize(cesta_output)
        if velkost_input != 0:
            print(f"⚠️ Výstupní soubor {cesta_output} již existuje ({velkost_input} B). Přepisuji ho.")

    # Uložit
    count = 0
    with open(cesta_output, "w", encoding=JSONL_ENCODING) as f:
        for radka in radky:
            json_str = __import__("json").dumps(radka, ensure_ascii=False, sort_keys=True)
            f.write(json_str + "\n")
            count += 1

    return count
